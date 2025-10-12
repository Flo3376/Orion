# /core/interface/lcars_style.py
"""
Module de style LCARS pour l'interface Orion
"""

# Couleurs LCARS
LCARS_BG = "#0b0f17"      # deep space
LCARS_ACCENT = "#ff9f1c"  # amber panel
LCARS_ACCENT2 = "#00d1ff" # cyan glow
LCARS_TEXT = "#e6e6e6"
LCARS_SUCCESS = "#00ff00" # vert pour les status OK
LCARS_WARNING = "#ffff00" # jaune pour les alertes
LCARS_ERROR = "#ff4444"   # rouge pour les erreurs

# Style principal pour toute l'application
MAIN_STYLE = f"""
* {{
    font-family: Segoe UI, Roboto, Arial, sans-serif;
    color: {LCARS_TEXT};
}}

QWidget {{
    background: {LCARS_BG};
}}

/* Fenêtre principale */
QMainWindow {{
    background: {LCARS_BG};
}}

/* Onglets */
QTabWidget::pane {{
    border: 2px solid {LCARS_ACCENT2};
    border-radius: 8px;
    background: {LCARS_BG};
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar::tab {{
    background: rgba(255,255,255,0.05);
    border: 2px solid {LCARS_ACCENT2};
    padding: 10px 20px;
    margin-right: 4px;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    font-weight: 600;
    letter-spacing: 1px;
}}

QTabBar::tab:selected {{
    background: {LCARS_ACCENT};
    color: black;
    font-weight: 700;
}}

QTabBar::tab:hover {{
    background: rgba(255,159,28,0.3);
}}

/* GroupBox */
QGroupBox {{
    border: 0px solid transparent;
    margin-top: 16px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 2px 6px;
    background: {LCARS_ACCENT};
    border-radius: 10px;
    color: black;
    font-weight: 700;
}}

/* Labels */
QLabel {{
    font-size: 14px;
    letter-spacing: 0.5px;
}}

/* Boutons */
QPushButton {{
    background: {LCARS_ACCENT};
    color: black;
    border: none;
    padding: 10px 16px;
    border-radius: 14px;
    font-weight: 700;
    letter-spacing: 1px;
}}

QPushButton:hover {{ 
    background: #ffb347;
}}

QPushButton:pressed {{
    background: #e6890f;
}}

QPushButton[status="success"] {{
    background: {LCARS_SUCCESS};
    color: black;
}}

QPushButton[status="warning"] {{
    background: {LCARS_WARNING};
    color: black;
}}

QPushButton[status="error"] {{
    background: {LCARS_ERROR};
    color: white;
}}

/* ScrollArea */
QScrollArea {{
    border: none;
    background: {LCARS_BG};
}}

QScrollBar:vertical {{
    background: rgba(255,255,255,0.1);
    width: 12px;
    border-radius: 6px;
}}

QScrollBar::handle:vertical {{
    background: {LCARS_ACCENT2};
    border-radius: 6px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {LCARS_ACCENT};
}}
/* ComboBox corrigé - fond opaque */
QComboBox {{
    background: {LCARS_BG};  /* Fond opaque au lieu de rgba */
    border: 2px solid {LCARS_ACCENT2};
    padding: 8px 12px;
    border-radius: 12px;
    font-weight: 600;
    letter-spacing: 0.5px;
    min-height: 16px;
    color: {LCARS_TEXT};
}}

QComboBox:hover {{
    background: rgba(255,159,28,0.15);  /* Légère transparence seulement au hover */
    border-color: {LCARS_ACCENT};
}}

QComboBox:focus {{
    background: {LCARS_BG};  /* Fond opaque même au focus */
    border-color: {LCARS_ACCENT};
    border-width: 3px;
}}

/* Flèche dropdown */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 2px solid {LCARS_ACCENT2};
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
    background: {LCARS_ACCENT};  /* Fond orange opaque */
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid black;
    margin: 2px;
}}

QComboBox::down-arrow:hover {{
    border-top-color: #333;
}}

/* Liste déroulante - fond opaque */
QComboBox QAbstractItemView {{
    background: {LCARS_BG};  /* Fond opaque */
    border: 2px solid {LCARS_ACCENT2};
    border-radius: 8px;
    selection-background-color: {LCARS_ACCENT};
    selection-color: black;
    font-weight: 600;
    padding: 4px;
    color: {LCARS_TEXT};
}}

QComboBox QAbstractItemView::item {{
    background: transparent;  /* Transparent pour les items individuels */
    padding: 8px 12px;
    border-radius: 6px;
    margin: 2px;
    color: {LCARS_TEXT};
}}

QComboBox QAbstractItemView::item:hover {{
    background: rgba(255,159,28,0.3);  /* Highlight orange au survol */
    color: black;
}}

QComboBox QAbstractItemView::item:selected {{
    background: {LCARS_ACCENT};
    color: black;
}}
"""

# Style pour l'en-tête principal
HEADER_STYLE = f"""
QFrame {{
    background: {LCARS_ACCENT};
    border-bottom-left-radius: 24px;
    border-bottom-right-radius: 24px;
}}

QLabel {{
    color: black;
    font-weight: 900;
    letter-spacing: 2px;
    font-size: 18px;
}}
"""