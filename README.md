# Yu-Gi-Oh! Hand Simulator

Copyright (c) 2026 Alex-xyc

This application is an opening-hand simulator and probability calculator for Yu-Gi-Oh! decks. It lets you load a deck from a `.ydk` file or paste a `ydke://` deck code, draw simulated opening hands, and view probabilities for drawing engine pieces, handtraps (non-engine), or 'brick' cards.

What this repository contains

```
src/
  gui.py                  Starts the desktop app (also the PyInstaller entry script)
  web.py                  Starts the web app (API + built front end)
  main.py                 Starts the console version
  decklists/  icons/      Example decks and the app icon
  ygo_calc/
    paths.py              Where icons/decklists live (source checkout or .exe)
    deck_loading.py       Loading a deck code (shared by the desktop and web apps)
    core/                 Pure logic, no UI or network code
      deck.py               YuGiOhDeck
      deck_parser.py        Card IDs from ydke:// codes and .ydk files
      deck_builder.py       Building a deck from card IDs + names
      categories.py         Brick / non-engine / engine tags per card copy
      probability.py        Hypergeometric maths
      simulation.py         Drawing hands
      report.py             The "Probabilities & Statistics" text
      stats.py              The same statistics as data (for the web app)
      comparison.py         The "Compare Decks" odds (text and data)
    cards/                Card names and images
      ygoprodeck.py         YGOPRODeck API (primary)
      edopro.py             EDOPro card databases (fallback)
      images.py             Which image URLs to try for a card
      cache.py  http.py     Shared caches and HTTP helpers
    ui/                   The desktop app
      app.py                Main window: builds the panels and wires up the deck state
      deck_input_panel.py   ydke code / .ydk file loading
      counts_panel.py       Category counts, buttons and deck status
      hand_panel.py         Test hand: card images and the text under them
      stats_panel.py        Probabilities & statistics
      split_view.py         Resizable split between the two panels (with drag preview)
      advanced_view.py      "Show Decklist" overlay for tagging cards
      compare_view.py       "Compare Decks" overlay: two decks side by side
      text_layout.py        Deck-list columns and text font fitting
      image_loader.py       Downloading and resizing card images
      window.py  theme.py   Window setup helpers, colours and fonts
    web/                  The web app's server
      server.py             FastAPI: deck lookup, stats, draws, comparison, card images
      images.py             Card images, downloaded once and served from a disk cache
    cli/
      console.py            The console simulator
web/                      The web front end (React + TypeScript, Vite)
  src/App.tsx               Page layout and state
  src/useDeckSetup.ts       A deck with its typed counts or decklist tags
  src/components/           Deck loading, hand, statistics, tagging and compare views
tests/                    Unit tests (python -m unittest discover -s tests)
Dockerfile  compose.yaml  Builds and runs the web app with Docker
```

Quick start

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run the GUI:

```bash
python src/gui.py
```

Or the console version: `python src/main.py`

Web app

The web app is a FastAPI server around the same core code, with a React front end.
The server keeps no per-user state; card images are fetched once and served from its
own disk cache (YGOPRODeck asks sites not to hotlink their images).

Run it locally:

```bash
python -m pip install -r requirements-web.txt
cd web && npm install && npm run build && cd ..
python src/web.py            # http://127.0.0.1:8000  (API docs at /api/docs)
```

While working on the front end, run `python src/web.py` and `cd web && npm run dev`
side by side: Vite serves the page with hot reload and forwards /api to the server.

Deploy on a server with Docker Compose (from the project folder):

```bash
docker compose up -d --build     # build and start; run again after changes to restart with them
docker compose logs -f           # server log
docker compose down              # stop (the image cache volume is kept)
```

Settings (environment variables): `HOST` / `PORT` (default 127.0.0.1:8000, the Docker
image uses 0.0.0.0), `YGO_CACHE_DIR` (image cache), `YGO_WEB_DIST` (built front end),
`YGO_API_DOCS=1` (serve the interactive API docs at /api/docs; off by default).
Put it behind a reverse proxy such as Caddy or nginx for HTTPS.

Security (src/ygo_calc/web/security.py): every response carries security headers (a strict
Content-Security-Policy, no framing, no MIME sniffing), request bodies are limited to 64 KB,
and each client is rate limited per minute (30 deck lookups, 600 card images, 300 other API
calls). Behind a reverse proxy or hosting platform, set `FORWARDED_ALLOW_IPS` to the proxy's
address (or `*` when only the platform can reach the app) so the limits apply to each real
visitor rather than to the proxy. The Docker image runs as an unprivileged user.

Notes

- The project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) — see the `LICENSE` file.

```
Copyright (C) 2026 Alex-xyc

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```
  
Ownership
This project and its source code are authored and maintained by Alex-xyc. See `LICENSE` for permitted uses.

Contributing
If you'd like to contribute, please open an issue or a pull request and include tests or a short description of changes.

Contact
For questions about ownership or licensing, contact the repository owner.


