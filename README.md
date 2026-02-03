# Yu-Gi-Oh! Hand Simulator

Copyright (c) 2026 Alex-xyc

This application is an opening-hand simulator and probability calculator for Yu-Gi-Oh! decks. It lets you load a deck from a `.ydk` file or paste a `ydke://` deck code, draw simulated opening hands, and view probabilities for drawing engine pieces, handtraps (non-engine), or 'brick' cards.

What this repository contains

- A simple GUI (CustomTkinter) to load decks and draw test hands (`src/gui.py`).
- Deck parsing and probability utilities (`src/main.py`).
- Example decklists in `src/decklists/` and icon assets in `src/icons/`.

Quick start

1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run the GUI:

```bash
python src/gui.py
```

Notes

- The project is licensed under the MIT License — see the `LICENSE` file.
- On Windows the app attempts to use `src/icons/ghattic.ico` for the taskbar icon.

Ownership
This project and its source code are authored and maintained by Alex-xyc. See `LICENSE` for permitted uses.

Contributing
If you'd like to contribute, please open an issue or a pull request and include tests or a short description of changes.

Contact
For questions about ownership or licensing, contact the repository owner.
