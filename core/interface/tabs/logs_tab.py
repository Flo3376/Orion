# /core/interface/tabs/logs_tab.py
"""
Onglet Logs - Affichage des logs avec lecture de fichier
"""

from __future__ import annotations
import os
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus


class LogsTab(QtWidgets.QWidget):
    """Onglet pour l'affichage des logs"""
    
    def __init__(self, event_bus: EventBus, config_manager=None):
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # ✅ Chemin simple : logs.txt à la racine du projet
        # Si on lance depuis la racine du projet, logs.txt sera trouvé
        self.logs_file_path = "./logs/orion.log"
        
        self._setup_ui()
        self._setup_timer()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header avec info
        header = QtWidgets.QLabel("📋 LOGS SYSTÈME (500 dernières lignes)")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                background: rgba(255, 159, 28, 0.1);
                border: 1px solid #ff9f1c;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)
        
        # Zone de texte scrollable pour les logs
        self.logs_display = QtWidgets.QTextEdit()
        self.logs_display.setReadOnly(True)
        self.logs_display.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.logs_display)
        
        # Bouton de rechargement manuel
        refresh_btn = QtWidgets.QPushButton("🔄 Recharger")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #ff9f1c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e8890f;
            }
        """)
        refresh_btn.clicked.connect(self._load_logs)
        layout.addWidget(refresh_btn)
    
    def _setup_timer(self):
        """Configure le timer pour recharger les logs toutes les 500ms"""
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._load_logs)
        self.timer.start(500)  # 500ms
        
        # Charger une première fois
        self._load_logs()
    
    def _load_logs(self):
        """Charge les 500 dernières lignes du fichier de logs"""
        try:
            if not os.path.exists(self.logs_file_path):
                self.logs_display.setText("📄 Fichier logs.txt introuvable...")
                return
            
            with open(self.logs_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Prendre les 500 dernières lignes maximum
            if len(lines) > 500:
                lines = lines[-500:]
            
            # Formatter et afficher
            content = ""
            for line in lines:
                line = line.strip()
                if line:
                    # Coloration simple selon le type de log
                    if "[ERROR]" in line or "❌" in line:
                        content += f'<span style="color: #ff6b6b;">{line}</span><br>'
                    elif "[WARNING]" in line or "⚠️" in line:
                        content += f'<span style="color: #ffa726;">{line}</span><br>'
                    elif "[SUCCESS]" in line or "✅" in line:
                        content += f'<span style="color: #66bb6a;">{line}</span><br>'
                    elif "[DEBUG]" in line or "🔍" in line:
                        content += f'<span style="color: #90a4ae;">{line}</span><br>'
                    else:
                        content += f'<span style="color: #ffffff;">{line}</span><br>'
            
            self.logs_display.setHtml(content)
            
            # Scroll automatique vers le bas
            scrollbar = self.logs_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
        except Exception as e:
            self.logs_display.setText(f"❌ Erreur lecture logs: {e}")