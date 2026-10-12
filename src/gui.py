"""Start the Yu-Gi-Oh! Hand Simulator desktop app (also the PyInstaller entry script).

The app itself lives in the ygo_calc package; see ygo_calc/ui/app.py.

Copyright (c) 2026 Alex-xyc
"""

from ygo_calc.ui.app import YuGiOhHandSimulator, main

__all__ = ["YuGiOhHandSimulator", "main"]

if __name__ == "__main__":
    main()
