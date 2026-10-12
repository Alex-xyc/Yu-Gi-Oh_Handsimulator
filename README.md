# Yu-Gi-Oh! Hand Simulator

Copyright (c) 2026 Alex-xyc

This application is an opening-hand simulator and probability calculator for Yu-Gi-Oh! decks. It lets you load a deck from a `.ydk` file or paste a `ydke://` deck code, draw simulated opening hands, and view probabilities for drawing engine pieces, handtraps (non-engine), or 'brick' cards.

What this repository contains

```
src/
  gui.py                  Starts the desktop app (also the PyInstaller entry script)
  main.py                 Starts the console version
  decklists/  icons/      Example decks and the app icon
  ygo_calc/
    paths.py              Where icons/decklists live (source checkout or .exe)
    core/                 Pure logic, no UI or network code
      deck.py               YuGiOhDeck
      deck_parser.py        Card IDs from ydke:// codes and .ydk files
      deck_builder.py       Building a deck from card IDs + names
      categories.py         Brick / non-engine / engine tags per card copy
      probability.py        Hypergeometric maths
      simulation.py         Drawing hands
      report.py             The "Probabilities & Statistics" text
      comparison.py         The "Compare Decks" odds table
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
      deck_loading.py       Loading a deck code (shared by both views)
      text_layout.py        Deck-list columns and text font fitting
      image_loader.py       Downloading and resizing card images
      window.py  theme.py   Window setup helpers, colours and fonts
    cli/
      console.py            The console simulator
tests/                    Unit tests (python -m unittest discover -s tests)
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

Notes

- The project is licensed under the MIT License — see the `LICENSE` file.
  
Ownership
This project and its source code are authored and maintained by Alex-xyc. See `LICENSE` for permitted uses.

Contributing
If you'd like to contribute, please open an issue or a pull request and include tests or a short description of changes.

Contact
For questions about ownership or licensing, contact the repository owner.


