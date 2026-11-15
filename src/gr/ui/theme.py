"""Win11-flavoured dark palette + global stylesheet."""

from __future__ import annotations

BG = "#1F1F1F"
CARD = "#272729"
CARD_ALT = "#2E2E31"
BORDER = "#3A3A3D"
TEXT = "#F5F5F5"
TEXT_MUTED = "#A6A6AA"
TEXT_DIM = "#7A7A80"
ACCENT = "#4CC2FF"
ACCENT_PRESSED = "#3AA9E0"
ACCENT_DIM = "#1E4E63"
GOOD = "#6CCB5F"
WARN = "#FCE100"
BAD = "#FF99A4"

FONT_FAMILY = '"Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif'
MONO_FAMILY = '"Cascadia Mono", "Consolas", monospace'


def stylesheet() -> str:
    return f"""
    * {{
        font-family: {FONT_FAMILY};
        outline: none;
    }}
    QMainWindow, QWidget#Root {{
        background: {BG};
        color: {TEXT};
    }}
    QLabel {{
        color: {TEXT};
        background: transparent;
    }}
    QLabel[role="h1"] {{ font-size: 17px; font-weight: 600; }}
    QLabel[role="h2"] {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
    QLabel[role="sub"] {{ font-size: 11px; color: {TEXT_MUTED}; }}
    QLabel[role="mono"] {{ font-family: {MONO_FAMILY}; font-size: 11px; color: {TEXT_MUTED}; }}
    QLabel[role="big"] {{ font-size: 30px; font-weight: 600; }}
    QLabel[role="value"] {{ font-family: {MONO_FAMILY}; font-size: 12px; color: {TEXT}; }}

    QFrame#Card {{
        background: {CARD};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}
    QFrame#Card[armed="true"] {{
        border: 1px solid {ACCENT};
    }}
    QFrame#CardAlt {{
        background: {CARD_ALT};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QFrame#Divider {{
        background: {BORDER};
        max-height: 1px;
        border: none;
    }}

    QPushButton {{
        background: {CARD_ALT};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 7px 14px;
        font-size: 12px;
    }}
    QPushButton:hover {{ background: #35353A; }}
    QPushButton:pressed {{ background: #2A2A2E; }}
    QPushButton:disabled {{ color: {TEXT_DIM}; border-color: #313134; background: #242427; }}
    QPushButton:checked {{
        background: #14384A;
        border: 1px solid {ACCENT};
        color: {ACCENT};
        font-weight: 600;
    }}
    QPushButton[variant="accent"] {{
        background: {ACCENT};
        color: #0B2230;
        border: none;
        font-weight: 600;
    }}
    QPushButton[variant="accent"]:hover {{ background: #63CBFF; }}
    QPushButton[variant="accent"]:pressed {{ background: {ACCENT_PRESSED}; }}
    QPushButton[variant="ghost"] {{
        background: transparent;
        border: 1px solid transparent;
        color: {TEXT_MUTED};
        padding: 6px 10px;
    }}
    QPushButton[variant="ghost"]:hover {{ background: {CARD_ALT}; color: {TEXT}; }}
    QPushButton#Segment {{
        background: transparent;
        border: none;
        border-radius: 5px;
        padding: 5px 14px;
        color: {TEXT_MUTED};
        font-size: 12px;
    }}
    QPushButton#Segment:checked {{
        background: #3A3A3F;
        color: {TEXT};
        font-weight: 600;
    }}
    QPushButton#Segment:hover:!checked {{ color: {TEXT}; }}

    QPlainTextEdit {{
        background: #1B1B1D;
        border: 1px solid #303033;
        border-radius: 8px;
        color: #CFCFD4;
        font-family: {MONO_FAMILY};
        font-size: 11px;
        padding: 8px;
        selection-background-color: #2E5F76;
    }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 4px 2px 4px 0;
    }}
    QScrollBar::handle:vertical {{
        background: #46464B; border-radius: 4px; min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #57575D; }}
    QScrollBar::add-line, QScrollBar::sub-line,
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none; height: 0; width: 0; border: none;
    }}

    QProgressBar {{
        background: #34343A;
        border: none;
        border-radius: 3px;
        height: 6px;
        text-align: center;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {ACCENT};
        border-radius: 3px;
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: #34343A;
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT};
        border-radius: 2px;
    }}
    QSlider::add-page:horizontal {{
        background: #34343A;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -6px 0;
        border-radius: 7px;
        background: #FFFFFF;
        border: 1px solid #6A6A70;
    }}
    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
        border: 1px solid {ACCENT};
    }}

    QToolTip {{
        background: #303034;
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 5px 8px;
    }}

    QDialog {{
        background: {BG};
        color: {TEXT};
    }}
    QTableWidget {{
        background: #232326;
        border: 1px solid #303033;
        border-radius: 8px;
        gridline-color: transparent;
        color: {TEXT};
        font-size: 12px;
        selection-background-color: #2E5F76;
    }}
    QTableWidget::item {{
        padding: 7px 9px;
        border-bottom: 1px solid #2C2C30;
    }}
    QTableWidget::item:selected {{
        background: #2E5F76;
        color: #FFFFFF;
    }}
    QHeaderView::section {{
        background: #26262A;
        color: {TEXT_MUTED};
        border: none;
        padding: 7px 9px;
        font-size: 11px;
        font-weight: 600;
    }}
    QCheckBox {{
        color: {TEXT};
        font-size: 12px;
        spacing: 6px;
    }}
    QCheckBox::indicator {{
        width: 14px;
        height: 14px;
        border-radius: 4px;
        border: 1px solid #5A5A60;
        background: #2A2A2E;
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
    }}
    QCheckBox::indicator:checked:disabled {{
        background: #4A4A50;
        border-color: #4A4A50;
    }}

    QMenu {{
        background: #2A2A2E;
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px;
    }}
    QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 4px; font-size: 12px; }}
    QMenu::item:selected {{ background: #3A3A40; }}
    QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}
    """
