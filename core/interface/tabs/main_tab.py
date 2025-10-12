# /core/interface/tabs/main_tab.py
"""
Onglet principal - Tableau de bord et visualisation
"""

from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus


class MainTab(QtWidgets.QWidget):
    """Onglet principal avec tableau de bord et visualisation"""
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self._setup_ui()
        self._setup_event_handling()  # ← AJOUTER cette ligne
    
    def _setup_ui(self):
        """Configure l'interface de l'onglet"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(20)
        
        # Section tableau de bord
        dashboard_group = QtWidgets.QGroupBox("TABLEAU DE BORD")
        dashboard_layout = QtWidgets.QGridLayout(dashboard_group)
        
        # Ligne de voyants/boutons
        self._create_dashboard_buttons(dashboard_layout)
        
        layout.addWidget(dashboard_group)
        
        # Section visualisation son
        audio_group = QtWidgets.QGroupBox("VISUALISATION AUDIO")
        audio_layout = QtWidgets.QVBoxLayout(audio_group)
        
        # Placeholder pour la visualisation futuriste
        audio_placeholder = QtWidgets.QLabel("🎵 VISUALISATION AUDIO FUTURISTE 🎵")
        audio_placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        audio_placeholder.setStyleSheet("""
            QLabel {
                background: rgba(0, 209, 255, 0.1);
                border: 2px dashed #00d1ff;
                border-radius: 12px;
                padding: 40px;
                font-size: 18px;
                letter-spacing: 2px;
            }
        """)
        audio_layout.addWidget(audio_placeholder)
        
        layout.addWidget(audio_group)
        
        # Étirer pour occuper l'espace
        layout.addStretch()
    
    def _create_dashboard_buttons(self, layout: QtWidgets.QGridLayout):
        """Crée les boutons/voyants du tableau de bord"""
        
        # Row 0 - Status des modules
        layout.addWidget(QtWidgets.QLabel("MODULES:"), 0, 0)
        
        self.btn_listen = QtWidgets.QPushButton("LISTEN")
        self.btn_listen.setProperty("status", "error")
        layout.addWidget(self.btn_listen, 0, 1)
        
        self.btn_spotify = QtWidgets.QPushButton("SPOTIFY")
        self.btn_spotify.setProperty("status", "warning")
        layout.addWidget(self.btn_spotify, 0, 2)
        
        self.btn_config = QtWidgets.QPushButton("CONFIG")
        self.btn_config.setProperty("status", "success")
        layout.addWidget(self.btn_config, 0, 3)
        
        # Row 1 - Contrôles
        layout.addWidget(QtWidgets.QLabel("CONTRÔLES:"), 1, 0)
        
        self.btn_start_listen = QtWidgets.QPushButton("START LISTEN")
        layout.addWidget(self.btn_start_listen, 1, 1)
        
        self.btn_stop_listen = QtWidgets.QPushButton("STOP LISTEN")
        layout.addWidget(self.btn_stop_listen, 1, 2)
        
        self.btn_reload_config = QtWidgets.QPushButton("RELOAD CONFIG")
        layout.addWidget(self.btn_reload_config, 1, 3)
    
    def _setup_event_handling(self):  # ← AJOUTER cette méthode
        """Configure l'écoute des événements du bus"""
        # S'abonner aux événements du bus
        self.event_bus.subscribe(self._on_bus_event)

    def _on_bus_event(self, message):
        """Traite les événements reçus du bus"""
        name = message.get("name", "")
        state = message.get("state", "")
        payload = message.get("payload", {})

        # Événements du listen manager
        if name == "listen.main_listener":
            if state == "started":
                self._update_listen_status("success", "LISTEN")
                print("🟢 Interface: Listen démarré")
            elif state == "stopped":
                self._update_listen_status("error", "LISTEN")
                print("🔴 Interface: Listen arrêté")
            elif state == "error":
                self._update_listen_status("error", "LISTEN ERROR")
                print("❌ Interface: Listen erreur")
        
        # Tu peux ajouter d'autres modules ici
        elif name == "spotify":
            if state == "connected":
                self._update_spotify_status("success", "SPOTIFY")
            elif state == "disconnected":
                self._update_spotify_status("error", "SPOTIFY")
        
        elif name == "config":
            if state == "loaded":
                self._update_config_status("success", "CONFIG")
            elif state == "error":
                self._update_config_status("error", "CONFIG ERROR")
    
    def _update_listen_status(self, status: str, text: str):
        """Met à jour le statut du bouton Listen"""
        self.btn_listen.setProperty("status", status)
        self.btn_listen.setText(text)
        # Force la mise à jour du style
        self.btn_listen.style().polish(self.btn_listen)
    
    def _update_spotify_status(self, status: str, text: str):
        """Met à jour le statut du bouton Spotify"""
        self.btn_spotify.setProperty("status", status)
        self.btn_spotify.setText(text)
        self.btn_spotify.style().polish(self.btn_spotify)
    
    def _update_config_status(self, status: str, text: str):
        """Met à jour le statut du bouton Config"""
        self.btn_config.setProperty("status", status)
        self.btn_config.setText(text)
        self.btn_config.style().polish(self.btn_config)        