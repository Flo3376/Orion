# /core/interface/tabs/web_tab.py
"""
Onglet Web - Liens vers interfaces web
"""

from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus


class WebTab(QtWidgets.QWidget):
    """Onglet pour les liens web"""
    
    def __init__(self, event_bus: EventBus, config_manager=None):  # ✅ Ajouter config_manager
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = config_manager  # ✅ Stocker
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Placeholder
        placeholder = QtWidgets.QLabel("🌐 INTERFACES WEB")
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                background: rgba(255, 68, 68, 0.1);
                border: 2px dashed #ff4444;
                border-radius: 12px;
                padding: 60px;
                font-size: 18px;
                letter-spacing: 2px;
            }
        """)
        layout.addWidget(placeholder)