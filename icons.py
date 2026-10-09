#!/usr/bin/env python3
"""
Vector SVG Icon System for Notchgent.
Provides pixel-crisp, resolution-independent vector icons for both
PyQt6 desktop UI and Mobile Web PWA.
"""

from io import BytesIO
from typing import Optional

try:
    from PyQt6.QtSvg import QSvgRenderer
    from PyQt6.QtGui import QPainter, QPixmap, QIcon, QColor
    from PyQt6.QtCore import QByteArray, Qt
    HAS_PYQT = True
except ImportError:
    QSvgRenderer = None
    QPainter = None
    QPixmap = None
    QIcon = None
    QColor = None
    QByteArray = None
    Qt = None
    HAS_PYQT = False


# SVG Path definitions (24x24 viewBox, stroke-width 2, stroke-linecap round, stroke-linejoin round)
SVG_PATHS = {
    "phone": """<rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>""",
    "clapperboard": """<path d="M4 11v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8H4z"/><path d="m4 11 3-6h4l-3 6"/><path d="m11 5 3 6"/><path d="m14 5 3 6"/><path d="m17 5 3 6"/><path d="M2 11h20"/>""",
    "terminal": """<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>""",
    "file_edit": """<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>""",
    "file_plus": """<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>""",
    "help_circle": """<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>""",
    "check": """<polyline points="20 6 9 17 4 12"/>""",
    "x": """<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>""",
    "copy": """<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>""",
    "rotate": """<path d="M21.5 2v6h-6"/><path d="M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>""",
    "wifi": """<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>""",
    "zap": """<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>""",
    "shield_check": """<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>""",
    "globe": """<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>""",
    "external_link": """<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>"""
}



def build_svg_xml(name: str, color: str = "#ffffff", stroke_width: float = 2.0) -> str:
    """Build full XML for a vector SVG icon."""
    inner = SVG_PATHS.get(name, SVG_PATHS["zap"])
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round">{inner}</svg>"""


def get_svg_pixmap(name: str, color: str = "#ffffff", size: int = 16, stroke_width: float = 2.0):
    """Render an SVG icon into a high-DPI crisp QPixmap."""
    if not HAS_PYQT:
        return None
    xml = build_svg_xml(name, color, stroke_width)
    renderer = QSvgRenderer(QByteArray(xml.encode("utf-8")))

    # Render at 2x pixel ratio for retina sharpness
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def get_svg_icon(name: str, color: str = "#ffffff", size: int = 16, stroke_width: float = 2.0):
    """Create a QIcon from a vector SVG definition."""
    if not HAS_PYQT:
        return None
    pix = get_svg_pixmap(name, color, size, stroke_width)
    return QIcon(pix)


def get_html_svg(name: str, color: str = "currentColor", size: int = 16, stroke_width: float = 2.0, extra_class: str = "") -> str:
    """Generate inline SVG for mobile HTML templates."""
    inner = SVG_PATHS.get(name, SVG_PATHS["zap"])
    cls_attr = f' class="svg-icon {extra_class}"' if extra_class else ' class="svg-icon"'
    style_attr = f'style="width:{size}px;height:{size}px;vertical-align:middle;stroke:{color};display:inline-block;"'
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" stroke-linejoin="round"{cls_attr} {style_attr}>{inner}</svg>"""
