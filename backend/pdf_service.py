from __future__ import annotations

from io import BytesIO
from math import ceil

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .image_service import ensure_card_image
from .models import Card, Deck


def build_deck_pdf(deck: Deck) -> bytes:
    packet = BytesIO()
    pdf = canvas.Canvas(packet, pagesize=A4)
    page_width, page_height = A4
    cols = 3
    rows = 3
    card_width = 63 * mm
    card_height = 88 * mm
    gap = 0
    margin_x = (page_width - (card_width * cols) - (gap * (cols - 1))) / 2
    margin_y = (page_height - (card_height * rows) - (gap * (rows - 1))) / 2

    expanded_cards: list[Card] = []
    for item in deck.items:
        expanded_cards.extend([item.card] * item.quantity)

    for page_index in range(max(ceil(len(expanded_cards) / 9), 1)):
        chunk = expanded_cards[page_index * 9:(page_index + 1) * 9]
        for index, card in enumerate(chunk):
            row = index // cols
            col = index % cols
            x = margin_x + (card_width + gap) * col
            y = page_height - margin_y - card_height - (card_height + gap) * row
            draw_card(pdf, card, x, y, card_width, card_height)
        pdf.showPage()

    pdf.save()
    return packet.getvalue()


def draw_card(pdf: canvas.Canvas, card: Card, x: float, y: float, width: float, height: float) -> None:
    pdf.rect(x, y, width, height, stroke=1, fill=0)

    image_path = None
    try:
        image_path = ensure_card_image(card)
    except Exception:
        image_path = None

    if image_path:
        pdf.drawImage(
            ImageReader(str(image_path)),
            x,
            y,
            width,
            height,
            preserveAspectRatio=False,
            mask="auto",
        )
    else:
        pdf.setFillColorRGB(1, 1, 1)
        pdf.rect(x, y, width, height, stroke=0, fill=1)
        pdf.rect(x, y, width, height, stroke=1, fill=0)
