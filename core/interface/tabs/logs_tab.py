# /core/interface/tabs/logs_tab.py
"""
Onglet Logs - Affichage des logs avec filtres
"""

from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus


class LogsTab(QtWidgets.QWidget):
    """Onglet pour l'affichage des logs"""
    
    def __init__(self, event_bus: EventBus, config_manager=None):  # ✅ Ajouter config_manager
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = config_manager  # ✅ Stocker
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Placeholder
        placeholder = QtWidgets.QLabel("📋 LOGS & FILTRES")
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("""
            QLabel {
                background: rgba(255, 159, 28, 0.1);
                border: 2px dashed #ff9f1c;
                border-radius: 12px;
                padding: 60px;
                font-size: 18px;
                letter-spacing: 2px;
            }
        """)
        layout.addWidget(placeholder)