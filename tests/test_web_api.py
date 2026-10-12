"""Tests for the web app's API (card name lookups are mocked, so no network is used)."""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

try:
    from fastapi.testclient import TestClient
except ImportError:  # The web dependencies are optional (requirements-web.txt)
    TestClient = None

from ygo_calc.core.categories import BRICK, ENGINE, NON_ENGINE
from ygo_calc.core.stats import opening_stats
from ygo_calc.core.probability import probability_at_least

YDK = "#main\n" + "\n".join(["100"] * 3 + ["200"] * 2 + [str(300 + i) for i in range(35)]) + "\n#extra\n!side\n"


def fake_names(card_ids, verbose=True):
    return {cid: f"Card {cid}" for cid in card_ids}


def setup_body(**extra):
    cards = [{"name": "Card 100", "copies": 3}, {"name": "Card 200", "copies": 2}]
    cards += [{"name": f"Card {300 + i}", "copies": 1} for i in range(35)]
    return {"name": "Deck", "cards": cards, **extra}


class TestOpeningStats(unittest.TestCase):
    def test_counts_and_odds(self):
        pool = [("A", ENGINE)] * 12 + [("B", NON_ENGINE)] * 9 + [("C", BRICK)] * 4 + [("D", "")] * 15
        stats = opening_stats(pool)
        self.assertEqual(stats["counts"], {BRICK: 4, NON_ENGINE: 9, ENGINE: 12, "untagged": 15})
        self.assertAlmostEqual(stats["at_least"][ENGINE][0], probability_at_least(40, 12, 5, 1))
        cells = [p for row in stats["matrix"] for p in row if p is not None]
        self.assertAlmostEqual(sum(cells), 1.0)
        self.assertIsNone(stats["sixth_card"])

    def test_sixth_card_uses_hand(self):
        pool = [("A", ENGINE)] * 12 + [("D", "")] * 28
        stats = opening_stats(pool, hand_categories=[ENGINE, ENGINE, "", "", ""])
        self.assertEqual(stats["sixth_card"][ENGINE]["remaining"], 10)
        self.assertAlmostEqual(stats["sixth_card"][ENGINE]["probability"], 10 / 35)

    def test_ungrouped_card_odds(self):
        stats = opening_stats([("A", ENGINE)] * 3 + [("B", "")] * 37, grouped=False)
        self.assertEqual({card["group"] for card in stats["cards"]}, {"untagged"})


@unittest.skipIf(TestClient is None, "fastapi is not installed")
class TestWebApi(unittest.TestCase):
    def setUp(self):
        from ygo_calc.web.server import app
        self.client = TestClient(app)
        patcher = patch('ygo_calc.deck_loading.fetch_multiple_card_names', side_effect=fake_names)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_deck(self):
        response = self.client.post("/api/decks", json={"code": YDK})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["size"], 40)
        self.assertEqual(data["cards"][0], {"name": "Card 100", "id": "100", "copies": 3})

    def test_load_bad_deck(self):
        response = self.client.post("/api/decks", json={"code": "#main\n#extra\n"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No main deck cards", response.json()["detail"])

    def test_stats_with_counts(self):
        body = setup_body(counts={"brick": 4, "non_engine": 9, "engine": 12})
        stats = self.client.post("/api/stats", json=body).json()
        self.assertEqual(stats["counts"][ENGINE], 12)

    def test_counts_over_deck_size(self):
        body = setup_body(counts={"brick": 30, "non_engine": 9, "engine": 12})
        response = self.client.post("/api/stats", json=body)
        self.assertEqual(response.status_code, 400)
        self.assertIn("exceed deck size", response.json()["detail"])

    def test_too_many_copies(self):
        body = setup_body()
        body["cards"].append({"name": "Card 100", "copies": 1})
        self.assertEqual(self.client.post("/api/stats", json=body).status_code, 400)

    def test_draw_with_tags(self):
        tags = [ENGINE] * 20 + [NON_ENGINE] * 10 + [BRICK] * 5 + [""] * 5
        data = self.client.post("/api/draw", json={"deck": setup_body(tags=tags)}).json()
        self.assertEqual(len(data["hand"]), 5)
        self.assertIsNotNone(data["sixth"])
        self.assertIsNotNone(data["stats"]["sixth_card"])

    def test_tags_must_match_deck(self):
        response = self.client.post("/api/draw", json={"deck": setup_body(tags=[ENGINE] * 3)})
        self.assertEqual(response.status_code, 400)

    def test_stats_going_second(self):
        body = setup_body(counts={"brick": 4, "non_engine": 9, "engine": 12})
        first = self.client.post("/api/stats", json=body).json()
        second = self.client.post("/api/stats?hand_size=6", json=body).json()
        self.assertEqual((first["hand_size"], second["hand_size"]), (5, 6))
        self.assertEqual(len(second["at_least"]["engine"]), 6)
        self.assertGreater(second["bricks"]["open"], first["bricks"]["open"])
        self.assertAlmostEqual(first["averages"]["engine"], 5 * 12 / 40)
        labels = [row["label"] for row in first["combinations"]]
        self.assertIn("No bricks", labels)
        self.assertNotIn("At least 1 engine", labels)  # already in at_least
        self.assertEqual(self.client.post("/api/stats?hand_size=7", json=body).status_code, 422)

    def test_compare(self):
        a = setup_body(counts={"brick": 4, "non_engine": 9, "engine": 12})
        b = setup_body(name="Other", counts={"brick": 2, "non_engine": 9, "engine": 15})
        data = self.client.post("/api/compare", json={"decks": [a, b], "hand_size": 6}).json()
        self.assertEqual(data["hand_size"], 6)
        first = data["odds"][0]
        self.assertEqual(first["label"], "At least 1 engine")
        self.assertEqual(first["better"], 2)
        # The main page's statistics too: at least 1..6 of each category, and the brick odds
        self.assertEqual([group["key"] for group in data["at_least"]], ["engine", "non_engine", "brick"])
        self.assertTrue(all(len(group["rows"]) == 6 for group in data["at_least"]))
        brick_1 = data["at_least"][2]["rows"][0]
        self.assertEqual(brick_1["label"], "At least 1 brick")
        self.assertEqual(brick_1["better"], 2)  # fewer bricks in the other deck
        self.assertEqual([row["label"] for row in data["bricks"]],
                         ["Open with a brick", "Draw one 7th", "See one in the first 7 cards"])
        self.assertAlmostEqual(data["bricks"][0]["a"], brick_1["a"])

    def test_image_rejects_bad_ids(self):
        self.assertEqual(self.client.get("/api/cards/abc/image").status_code, 404)


if __name__ == '__main__':
    unittest.main()
