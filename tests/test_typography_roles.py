from gui.design.typography_roles import TypographyRole, font_for_role
from gui.design.loader import load_tokens
from PyQt6.QtWidgets import QApplication
import sys


def test_font_for_each_role():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    tokens = load_tokens()
    roles = [
        TypographyRole.TITLE,
        TypographyRole.SUBTITLE,
        TypographyRole.BODY,
        TypographyRole.CAPTION,
    ]
    fonts = []
    for r in roles:
        f = font_for_role(r)
        assert f.pixelSize() > 0
        fonts.append(f)
    # Title should be >= subtitle >= body >= caption
    assert (
        fonts[0].pixelSize() >= fonts[1].pixelSize() >= fonts[2].pixelSize() >= fonts[3].pixelSize()
    )
