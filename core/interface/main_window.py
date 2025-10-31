# /core/interface/main_window.py
"""
Fenêtre principale de l'interface Orion avec onglets
"""

from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from typing import Optional
from core.bus import EventBus
from .lcars_style import MAIN_STYLE, HEADER_STYLE
from .tabs.main_tab import MainTab
from .tabs.logs_tab import LogsTab
from .tabs.micro_tab import MicroTab
from .tabs.web_tab import WebTab
from .tabs.config_tab import ConfigTab  # ← NOUVEAU: Importer l'onglet Config

class OrionMainWindow(QtWidgets.QMainWindow):
    """Fenêtre principale de l'interface Orion"""
    
    def __init__(self, event_bus: EventBus, config_manager):
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = config_manager  # ✅ Stocker config_manager
        
        self.setWindowTitle("ORION • INTERFACE • CONTROL")
        self.setFixedSize(1200, 800)  # Taille fixe pour commencer
        
        self._setup_ui()
        self._setup_style()
        self.center_on_screen()

    # Dans main_window.py, ajouter :
    def closeEvent(self, event):
        """✅ CORRECTION - Fermeture propre de l'application"""
        try:
            print("🔄 Fermeture de l'interface en cours...")
            
            # Arrêter le worker audio du micro
            if hasattr(self, 'micro_tab') and hasattr(self.micro_tab, 'worker'):
                self.micro_tab.worker.stop()
                print("🎤 Micro worker arrêté")
            
            # Publier événement de fermeture sur le bus (méthode corrigée)
            if self.event_bus:
                message = {
                    "name": "interface",
                    "state": "closing",
                    "payload": {}
                }
                self.event_bus.publish(message)
                print("📢 Événement de fermeture publié")
            
            print("✅ Fermeture propre terminée")
            
        except Exception as e:
            print(f"❌ Erreur lors de la fermeture: {e}")
        
        # Accepter la fermeture et quitter l'application
        event.accept()
        QtWidgets.QApplication.quit()
    
    def _setup_ui(self):
        """Configure l'interface utilisateur"""
        
        # Widget central avec scroll
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)
        
        # En-tête LCARS
        header = self._create_header()
        main_layout.addWidget(header)
        
        # Zone de contenu avec scroll
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Widget de contenu pour le scroll
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Onglets principaux
        self.tab_widget = QtWidgets.QTabWidget()
        self._create_tabs()
        content_layout.addWidget(self.tab_widget)
        
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def _create_header(self) -> QtWidgets.QFrame:
        """Crée l'en-tête LCARS"""
        header = QtWidgets.QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(HEADER_STYLE)
        
        title = QtWidgets.QLabel("ORION • INTERFACE • CONTROL")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        layout = QtWidgets.QHBoxLayout(header)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.addWidget(title)
        
        return header
    
    def _create_tabs(self):
        """Crée les onglets principaux"""
        
        # Onglet Main - Tableau de bord + visualisation son
        self.main_tab = MainTab(self.event_bus, self.config_manager)
        self.tab_widget.addTab(self.main_tab, "MAIN")
        
        # Onglet Logs - Affichage des logs avec filtres
        self.logs_tab = LogsTab(self.event_bus, self.config_manager)
        self.tab_widget.addTab(self.logs_tab, "LOGS")
        
        # Onglet Micro - VU-mètre et sélection micro
        self.micro_tab = MicroTab(self.event_bus, self.config_manager)
        self.tab_widget.addTab(self.micro_tab, "MICRO")
        
        # Onglet Web - Liens vers interfaces web
        self.web_tab = WebTab(self.event_bus, self.config_manager)
        self.tab_widget.addTab(self.web_tab, "WEB")

        # Onglet config - Liens vers interfaces web
        self.config_tab = ConfigTab(self.event_bus, self.config_manager)
        self.tab_widget.addTab(self.config_tab, "CONFIG")

         # ✅ NOUVEAU: Connecter les changements d'onglets
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        """Appelé quand on change d'onglet"""
        # Notifier tous les onglets qu'ils sont masqués
        self.main_tab.on_tab_hide() if hasattr(self.main_tab, 'on_tab_hide') else None
        self.logs_tab.on_tab_hide() if hasattr(self.logs_tab, 'on_tab_hide') else None
        self.micro_tab.on_tab_hide() if hasattr(self.micro_tab, 'on_tab_hide') else None
        self.web_tab.on_tab_hide() if hasattr(self.web_tab, 'on_tab_hide') else None
        
        # Notifier l'onglet actuel qu'il est visible
        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, 'on_tab_show'):
            current_widget.on_tab_show()
        print(f"Changement d'onglet détecté: {index}")
    
    def _setup_style(self):
        """Applique le style LCARS"""
        self.setStyleSheet(MAIN_STYLE)
    
    def center_on_screen(self):
        """Centre la fenêtre sur l'écran"""
        geo = self.frameGeometry()
        screen_center = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
        geo.moveCenter(screen_center)
        self.move(geo.topLeft())