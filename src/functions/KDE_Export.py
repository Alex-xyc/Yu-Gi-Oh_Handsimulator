"""
Export Yu-Gi-Oh! decks to Konami KDE decklist PDF format.

This module provides a function to export a deck (from a YuGiOhDeck object)
to a PDF file in the official Konami decklist format, and opens a preview in the default browser.
"""

import os
import tempfile
import webbrowser
from pdfrw import PdfReader, PdfWriter, PdfDict

def fill_kde_decklist_pdf(deck, deck_name: str = "My Deck", output_path: str = None, form_path: str = None) -> str:
    """
    Fill the official KDE_DeckList.pdf with deck data and open a preview in the default browser.
    Returns the path to the generated PDF.
    """
    if form_path is None:
        form_path = os.path.join(os.path.dirname(__file__), '../forms/KDE_DeckList.pdf')
    form_path = os.path.abspath(form_path)
    if not os.path.exists(form_path):
        raise FileNotFoundError(f"KDE_DeckList.pdf not found at {form_path}")

    # Read the PDF form
    template_pdf = PdfReader(form_path)

    # Prepare deck sections (simple: all in Main Deck)
    main_deck = []
    for card, count in deck.cards.items():
        main_deck.append((card, count))

    # KDE form has 60 main, 15 extra, 15 side slots (usually)
    main_fields = [f"Main {i+1}" for i in range(60)]
    # You may want to split extra/side if you have that info
    extra_fields = [f"Extra {i+1}" for i in range(15)]
    side_fields = [f"Side {i+1}" for i in range(15)]

    # Flatten deck for filling
    main_flat = []
    for card, count in main_deck:
        for _ in range(count):
            main_flat.append(card)
    # Fill fields
    annotations = template_pdf.pages[0]["/Annots"]
    field_map = {}
    for annot in annotations:
        if annot["/Subtype"] == "/Widget" and annot.get("/T"):
            key = annot["/T"][1:-1]  # Remove parentheses
            field_map[key] = annot
    # Fill main deck
    for i, card in enumerate(main_flat[:60]):
        fname = f"Main {i+1}"
        if fname in field_map:
            field_map[fname].update(PdfDict(V=card))
    # Optionally fill deck name
    if "Deck Name" in field_map:
        field_map["Deck Name"].update(PdfDict(V=deck_name))
    # Save PDF
    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".pdf", prefix="kde_filled_")
        os.close(fd)
    PdfWriter().write(output_path, template_pdf)
    webbrowser.open(f'file://{os.path.abspath(output_path)}')
    return output_path
