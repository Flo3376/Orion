"""
🎨 Styles pour l'onglet Configuration
=====================================

Tous les styles QSS (Qt Style Sheets) pour config_tab.py
Séparation style/logique pour une meilleure maintenabilité.
"""

# === STYLES DES BOUTONS ===
BUTTON_STYLES = {
    "primary": """
        QPushButton {
            background: #00d1ff;
            border: 2px solid #00d1ff;
            border-radius: 4px;
            color: black;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 8px;
            min-width: 60px;
            max-height: 28px;
        }
        QPushButton:hover {
            background: #33d9ff;
            border-color: #33d9ff;
        }
        QPushButton:pressed {
            background: #00a8cc;
        }
    """,
    
    "secondary": """
        QPushButton {
            background: #ff9f1c;
            border: 2px solid #ff9f1c;
            border-radius: 4px;
            color: black;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 8px;
            min-width: 60px;
            max-height: 28px;
        }
        QPushButton:hover {
            background: #ffb347;
        }
        QPushButton:pressed {
            background: #e8890b;
        }
    """,
    
    "danger": """
        QPushButton {
            background: #ff4444;
            border: 2px solid #ff4444;
            border-radius: 4px;
            color: white;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 8px;
            min-width: 60px;
            max-height: 28px;
        }
        QPushButton:hover {
            background: #ff6666;
        }
    """
}

# === STYLES DES SLIDERS ===
SLIDER_CUSTOM = """
    QSlider::groove:horizontal {
        border: 1px solid #999999;
        height: 8px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e1e1e, stop:1 #3e3e3e);
        margin: 2px 0;
        border-radius: 4px;
    }
    QSlider::handle:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d1ff, stop:1 #0099cc);
        border: 1px solid #5c5c5c;
        width: 18px;
        margin: -2px 0;
        border-radius: 9px;
    }
    QSlider::handle:horizontal:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #33d9ff, stop:1 #00b3e6);
    }
    QSlider::handle:horizontal:pressed {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff9f1c, stop:1 #e8890b);
    }
    QSlider::sub-page:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #00d1ff, stop:1 #0099cc);
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
    }
    QSlider::add-page:horizontal {
        background: #404040;
        border: 1px solid #777;
        height: 10px;
        border-radius: 4px;
    }
"""

# === STYLES DES COMBOBOX ===
COMBOBOX_STYLE = """
    QComboBox {
        background: #0b0f17;
        border: 2px solid #00d1ff;
        padding: 6px 10px;
        border-radius: 8px;
        font-weight: 600;
        color: #e6e6e6;
        min-height: 16px;
    }
    QComboBox:hover {
        background: #1a1f2e;
        border-color: #ff9f1c;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 2px solid #00d1ff;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
        background: #ff9f1c;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 3px solid transparent;
        border-right: 3px solid transparent;
        border-top: 5px solid black;
        margin: 2px;
    }
    QComboBox QAbstractItemView {
        background: #0b0f17;
        border: 2px solid #00d1ff;
        border-radius: 6px;
        selection-background-color: #ff9f1c;
        selection-color: black;
        color: #e6e6e6;
        padding: 2px;
    }
    QComboBox QAbstractItemView::item {
        background: transparent;
        padding: 6px 10px;
        border-radius: 4px;
        margin: 1px;
    }
    QComboBox QAbstractItemView::item:hover {
        background: rgba(255,159,28,0.3);
        color: white;
    }
    QComboBox QAbstractItemView::item:selected {
        background: #ff9f1c;
        color: black;
    }
"""

# === STYLES DES SECTIONS ===
SECTION_HEADER = """
    QLabel {
        background: rgba(0, 209, 255, 0.2);
        border-left: 4px solid #00d1ff;
        color: #00d1ff;
        font-weight: 700;
        font-size: 12px;
        letter-spacing: 1px;
        padding: 6px 12px;
        margin: 4px 0px;
    }
"""

SUBSECTION_CONTAINER = """
    QWidget {
        background: rgba(255, 159, 28, 0.05);
        border: 1px solid rgba(255, 159, 28, 0.2);
        border-radius: 6px;
        padding: 8px;
         margin-left: 12px;
     }
"""

SUBSECTION_CONTAINER_ALT = """
    QWidget {
         background: rgba(76, 175, 80, 0.05);
         border: 1px solid rgba(76, 175, 80, 0.2);
         border-radius: 6px;
         padding: 8px;
         margin-left: 12px;
     }
"""

SUBSECTION_HEADER_NORMAL = """
    QLabel {
        background: rgba(255, 159, 28, 0.15);
        border-left: 3px solid #ff9f1c;
        color: #ff9f1c;
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.5px;
        padding: 4px 8px;
        margin: 8px 0px 4px 0px;
        border-radius: 4px;
    }
"""

SUBSECTION_HEADER_ALT = """
    QLabel {
        background: rgba(76, 175, 80, 0.15);
        border-left: 3px solid #4caf50;
        color: #4caf50;
        font-weight: 600;
        font-size: 11px;
        letter-spacing: 0.5px;
        padding: 4px 8px;
        margin: 8px 0px 4px 0px;
        border-radius: 4px;
    }
"""

# === STYLES DES LABELS ===
VALUE_LABEL = """
    QLabel {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(0,209,255,0.3);
        border-radius: 4px;
        padding: 2px 4px;
        font-weight: 600;
        font-size: 11px;
    }
"""

FIELD_LABEL = """
    QLabel {
        color: #e6e6e6;
        font-weight: 600;
        font-size: 13px;
    }
    QLabel:hover {
        color: #ff9f1c;
    }
"""

# === STYLES DES CONTENEURS ===
MAIN_HEADER = """
    QLabel {
        background: #ff9f1c;
        color: black;
        font-weight: 900;
        font-size: 14px;
        letter-spacing: 2px;
        padding: 8px;
        border-radius: 8px;
        margin: 0px;
    }
"""

FIELDS_CONTAINER = """
    QWidget {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(0, 209, 255, 0.3);
        border-radius: 8px;
        padding: 4px;
    }
    QToolTip {
        background-color: #1a1f2e;
        color: #e6e6e6;
        border: 2px solid #ff9f1c;
        border-radius: 8px;
        padding: 8px;
        font-size: 12px;
        max-width: 300px;
    }
"""

BROWSE_BUTTON = """
    QPushButton {
        background: #ff9f1c;
        border: 2px solid #ff9f1c;
        border-radius: 6px;
        color: black;
        font-weight: 700;
        font-size: 14px;
        padding: 4px;
    }
    QPushButton:hover {
        background: #ffb347;
    }
"""