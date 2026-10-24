"""YGO Calc package.

Layout:
    core/   Deck model, deck-code parsing, categories, probability maths, simulation and
            the statistics report text. Pure Python, no UI or network code.
    cards/  Card names and image URLs from YGOPRODeck, with EDOPro as the fallback.
    ui/     The CustomTkinter desktop app: the main window plus one module per panel.
    cli/    The text-based console simulator.

Copyright (c) 2026 Alex-xyc
"""
