# /core/interface/tabs/config_tab.py
"""
Onglet Config - Configuration de l'application
"""

from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus
from pathlib import Path


class NoWheelSlider(QtWidgets.QSlider):
    """Slider qui ignore les événements de molette"""
    
    def __init__(self, min_val=0, max_val=100, step=1):
        super().__init__(QtCore.Qt.Horizontal)
        
        # ✅ Support décimales en multipliant par 10
        if isinstance(step, float) and step < 1:
            self.decimal_factor = int(1 / step)  # step=0.1 → factor=10
        else:
            self.decimal_factor = 1
            
        self.setMinimum(int(min_val * self.decimal_factor))
        self.setMaximum(int(max_val * self.decimal_factor))
    def wheelEvent(self, event):
        """Ignore les événements de molette pour éviter les conflits avec le scroll"""
        event.ignore()       
         
    def get_real_value(self):
        """Retourne la vraie valeur décimale"""
        return self.value() / self.decimal_factor
        
    def set_real_value(self, value):
        """Définit une valeur décimale"""
        self.setValue(int(value * self.decimal_factor))


class NoWheelComboBox(QtWidgets.QComboBox):
    """ComboBox qui ignore les événements de molette"""
    
    def wheelEvent(self, event):
        event.ignore()


class AutoSaveManager:
    """Gestionnaire de sauvegarde automatique avec délais"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.timers = {}  # Dict de timers par widget
        
    def schedule_save(self, config_key, value, delay_ms=500):
        """Programme une sauvegarde avec délai"""
        
        # Annuler le timer précédent s'il existe
        if config_key in self.timers:
            self.timers[config_key].stop()
            self.timers[config_key].deleteLater()
        
        # Créer un nouveau timer
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._do_save(config_key, value))
        self.timers[config_key] = timer
        
        print(f"⏳ Sauvegarde programmée dans {delay_ms/1000}s: {config_key} = {value}")
        timer.start(delay_ms)
    
    def save_immediate(self, config_key, value):
        """Sauvegarde immédiate (annule le timer)"""
        
        # Annuler le timer s'il existe
        if config_key in self.timers:
            self.timers[config_key].stop()
            self.timers[config_key].deleteLater()
            del self.timers[config_key]
            
        self._do_save(config_key, value)
    
    def _do_save(self, config_key, value):
        """Effectue la sauvegarde réelle"""
        try:
            print(f"💾 Sauvegarde: {config_key} = {value}")
            self.config_manager.set(config_key, value)
            
            # Nettoyer le timer
            if config_key in self.timers:
                del self.timers[config_key]
                
        except Exception as e:
            print(f"❌ Erreur sauvegarde {config_key}: {e}")


class ConfigTab(QtWidgets.QWidget):
    """Onglet pour la configuration de l'application"""

    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = None
        self._form_widgets = {}
        self.auto_saver = None  # ✅ AJOUTÉ

    def set_config_manager(self, config_manager):
        """Reçoit le gestionnaire de configuration et crée l'interface"""
        self.config_manager = config_manager
        self.auto_saver = AutoSaveManager(config_manager)  # ✅ AJOUTÉ
        self._setup_ui()

    def _setup_ui(self):
        if not self.config_manager:
            temp_label = QtWidgets.QLabel("En attente de la configuration...")
            layout = QtWidgets.QVBoxLayout(self)
            layout.addWidget(temp_label)
            return

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # En-tête
        header = QtWidgets.QLabel("CONFIGURATION • SYSTÈME • ORION")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
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
        """)
        layout.addWidget(header)

        # Zone scrollable
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 16, 0)
        content_layout.setSpacing(16)

        # === SECTIONS ===
        self._create_section(content_layout, "SECTION RECONNAISSANCE VOCALE", [
            ("Debug Audio", "checkbox", self.config_manager.get("listen.Debug", False), 
             "Active les logs détaillés pour diagnostiquer les problèmes audio"),
            
            ("Langue", "combo", ["fr-FR", "en-US", "es-ES"], 
             self._get_config_value("listen.Language", "fr-FR"),
             "Langue utilisée par le moteur de reconnaissance vocale"),
            
            ("Confiance minimale", "slider", 
             int(self._get_config_value("listen.Confidence", 0.75) * 100),
             "Seuil de confiance minimum (0-100%) pour accepter une commande vocale"),
            
            ("Mot-clé d'activation", "text", 
             self._get_config_value("listen.Hotword", "Swan"),
             "Mot déclencheur pour activer l'écoute"),
            
            ("Dossier grammaire", "folder", 
             self._get_config_value("listen.Grammar", "./core/grammar/"),
             "Répertoire contenant les fichiers SRGS de grammaire vocale"),
        ])

        self._create_section(content_layout, "SECTION TTS • SYNTHÈSE VOCALE", [

            ("Moteur Vocal", "combo", ["piper", "edgetts", "openAI"], 
             self._get_config_value("vocalisation.engine", "piper"),
             "Moteur TTS utilisé pour la synthèse vocale"),
            ("Effet", "combo", ["none", "ship", "city", "helmet"], 
             self._get_config_value("vocalisation.effect", "none"),
             "Effet appliqué à la voix lors de la synthèse vocale"),
            # ✅ Subsection ALTERNATIVE (bleue)
            ("__subsection_alt__", "Skin audio de l'assistant", None, "Stylisation audio de l'assistant"),

            ("Hauteur du skin", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.pitch", 0)),
                "min": -12,   # ← 1 octave vers le bas
                "max": 12,    # ← 1 octave vers le haut  
                "unit": "♪"   # ← Demi-tons, pas Hz !
            }, "Ajuste la tonalité de la voix (-12 à +12 demi-tons)"),

            ("Vitesse du skin", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.speed", 0)),
                "min": -50,   # ← 50% plus lent
                "max": 50,    # ← 50% plus rapide
                "unit": "%"   # ← Pourcentage, pas Hz !
            }, "Ajuste la vitesse de la voix (-50% à +50%)"),

            ("Filtre passe-haut", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.highpass", 0)),  # ← Nouvelle clé config
                "min": 0,
                "max": 100,
                "unit": "%"
            }, "Filtre passe-haut (0% = complet, 100% = coupe graves jusqu'à 2400Hz)"),

            ("Filtre passe-bas", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.lowpass", 0)),   # ← Nouvelle clé config
                "min": 0,
                "max": 100,
                "unit": "%"
            }, "Filtre passe-bas (0% = complet, 100% = coupe aigus jusqu'à 500Hz)"),

            ("metallic", "slider_custom", {
                "value": float(self._get_config_value("effects.skin.metallic", 0)),
                "min": 0.0,     # ← Pas métallique
                "max": 50.0,      # ← Réduit aussi
                "step": 0.5,
                "unit": "%"
            }, "Résonance métallique (0% = normal, 100% = très métallique)"),

            

            ("distortion", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.distortion", 0)),
                "min": 0,     # ← Pas de distortion
                "max": 80,    # ← Réduit de 100 à 80 (au-delà ça sature trop)
                "unit": "%"
            }, "Saturation douce (0% = propre, 80% = saturé)"),

            ("vocoder", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.vocoder", 0)),
                "min": 0,     # ← Pas de vocoder
                "max": 100,   # ← Vocoder max
                "unit": "%"
            }, "Effet vocoder (0% = normal, 100% = synthétiseur vocal)"),

            ("hash", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.hash", 0)),
                "min": 0,     # ← Pas de dégradation
                "max": 100,   # ← Dégradation max
                "unit": "%"
            }, "Dégradation digitale (0% = propre, 100% = très dégradé)"),

            # ✅ REVERB CORRIGÉ - Amplitude logique
            ("reverb", "slider_custom", {
                "value": float(self._get_config_value("effects.skin.reverb", 0)),  # ← float !
                "min": 0.0,       # ← Décimales !
                "max": 10.0,      # ← Plage réduite !
                "step": 0.1,      # ← Pas fin !
                "unit": "%"
            }, "Réverbération (0.0% = sec, 10.0% = cathédrale)"),

            # ✅ ECHO CORRIGÉ - Amplitude logique  
            ("echo", "slider_custom", {
                "value": float(self._get_config_value("effects.skin.echo", 0)),
                "min": 0.0,
                "max": 5.0,       # ← Encore plus réduit !
                "step": 0.1,
                "unit": "%"
            }, "Écho (0.0% = aucun, 5.0% = très prononcé)"),

            ("Mixage effect", "slider_custom", {
                "value": int(self._get_config_value("effects.skin.dry_wet", 50)),
                "min": 0,     # ← 100% effet (wet)
                "max": 100,   # ← 100% original (dry)
                "unit": "%"
            }, "Mixage de l'effet (0% = tout effet, 100% = tout original)"),
            
            ("Actions Skin Audio", "button_group", [
                {
                    "text": "🎤 Tester le Skin",
                    "onclick": "test_skin_audio",
                    "style": "secondary",
                    "tooltip": "Teste le skin audio avec les paramètres actuels"
                },
                {
                    "text": "🗑️ Purger Cache Skin",
                    "onclick": "purge_skin_cache",
                    "style": "danger",
                    "tooltip": "Supprime tous les fichiers skin et environment (ATTENTION: ils seront régénérés)"
                },
                {
                    "text": "🔄 Mettre à jour Skin",
                    "onclick": "update_skin_cache",
                    "style": "primary",
                    "tooltip": "Force la régénération du skin avec les nouveaux paramètres"
                }
            ], "Actions spécifiques Skin Audio"),
    
            

            # ✅ Test global juste après le sélecteur
            ("Test Global", "button_group", [
                {
                    "text": "🎤 Tester le Moteur Sélectionné",
                    "onclick": "test_selected_engine",
                    "style": "primary",
                    "tooltip": "Teste le moteur TTS actuellement sélectionné dans la liste"
                }
            ], "Test du moteur principal"),

            ("__subsection__", "Moteur Piper", None, "Configuration du moteur TTS gratuit Piper"),
            
            ("Voix Piper", "combo", {
                "🧔 Gilles (Homme, Rapide)": "gilles",
                "👩 Siwis (Femme, Qualité)": "siwis-medium", 
                "👨 UPMC (Homme, Qualité)": "upmc-medium",
                "🎭 MLS 1840 (Neutre)": "mls_1840-medium",
                "🎪 Tom (Homme, Expressif)": "tom-medium"
            }, self._get_config_value("piper.default_voice", "gilles"),
            "Voix Piper avec indication du type et qualité"),

            # ✅ Test spécifique Piper (indépendant du sélecteur)
            ("Actions Piper", "button_group", [
                {
                    "text": "🤖 Test Piper",
                    "onclick": "test_piper_specifically",
                    "style": "secondary",
                    "tooltip": "Teste spécifiquement Piper avec la voix sélectionnée (ignore le sélecteur de moteur)"
                }
            ], "Actions spécifiques Piper"),

            ("Modèle Piper", "folder", 
             self._get_config_value("piper.model_path", "./core/models_tts/piper/"),
             "Répertoire contenant les modèles Piper"),
            
            # Sous-section Edge TTS
            ("__subsection__", "Moteur Edge TTS", None, "Configuration du moteur TTS Edge"),

            ("Voix Edge", "combo", {
                # 🇫🇷 France
                "🇫🇷 Denise (Femme, France)": "fr-FR-DeniseNeural",
                "🇫🇷 Henri (Homme, France)": "fr-FR-HenriNeural", 
                "🇫🇷 Joséphine (Femme, France)": "fr-FR-JosephineNeural",
                "🇫🇷 Maurice (Homme, France)": "fr-FR-MauriceNeural",
                "🇫🇷 Yves (Homme, France)": "fr-FR-YvesNeural",
                "🇫🇷 Yvette (Femme, France)": "fr-FR-YvetteNeural",
                "🇫🇷 Alain (Homme, France)": "fr-FR-AlainNeural",
                "🇫🇷 Brigitte (Femme, France)": "fr-FR-BrigitteNeural",
                "🇫🇷 Céleste (Femme, France)": "fr-FR-CelesteNeural",
                "🇫🇷 Claude (Homme, France)": "fr-FR-ClaudeNeural",
                "🇫🇷 Coralie (Femme, France)": "fr-FR-CoralieNeural",
                "🇫🇷 Jacqueline (Femme, France)": "fr-FR-JacquelineNeural",
                "🇫🇷 Jérôme (Homme, France)": "fr-FR-JeromeNeural",
                "🇫🇷 Lucien (Homme, France)": "fr-FR-LucienNeural",
                "🇫🇷 Vivienne (Femme, France)": "fr-FR-VivienneNeural",
                
                # 🇨🇦 Canada  
                "🇨🇦 Antoine (Homme, Canada)": "fr-CA-AntoineNeural",
                "🇨🇦 Jean (Homme, Canada)": "fr-CA-JeanNeural",
                "🇨🇦 Sylvie (Femme, Canada)": "fr-CA-SylvieNeural",
                "🇨🇦 Caroline (Femme, Canada)": "fr-CA-CarolineNeural",
                "🇨🇦 Harmonie (Femme, Canada)": "fr-CA-HarmonieNeural",
                
                # 🇧🇪 Belgique
                "🇧🇪 Charline (Femme, Belgique)": "fr-BE-CharlineNeural",
                "🇧🇪 Gérard (Homme, Belgique)": "fr-BE-GerardNeural",
                
                # 🇨🇭 Suisse
                "🇨🇭 Ariane (Femme, Suisse)": "fr-CH-ArianeNeural",
                "🇨🇭 Fabrice (Homme, Suisse)": "fr-CH-FabriceNeural",
            }, self._get_config_value("edgetts.default_voice", "fr-FR-DeniseNeural"),
            "Voix française par pays - France, Canada, Belgique, Suisse"),
             
            ("Tonalité", "slider_custom", {
                "value": int(self._get_config_value("edgetts.pitch", -20)),
                "min": -50, 
                "max": 50,
                "unit": "Hz"
            }, "Ajuste la tonalité de la voix (-50Hz à +50Hz)"),
             
            ("Vitesse", "slider_custom", {
                "value": int(self._get_config_value("edgetts.rate", 0)),
                "min": -100, 
                "max": 100,
                "unit": "%"
            }, "Ajuste la vitesse de la voix (-100% à +100%)"),

            # ✅ Test spécifique Edge TTS
            ("Actions Edge TTS", "button_group", [
                {
                    "text": "🎭 Test Edge TTS",
                    "onclick": "test_edgetts_specifically",
                    "style": "secondary",
                    "tooltip": "Teste spécifiquement Edge TTS avec les paramètres configurés"
                }
            ], "Actions spécifiques Edge TTS"),

            
            # ✅ Sous-section OpenAI
            ("__subsection__", "Moteur OpenAI TTS", None, "Configuration du moteur TTS OpenAI"),
            
            ("Voix OpenAI", "combo", [
                "alloy", "echo", "fable", "onyx", "nova", "shimmer"
            ], self._get_config_value("openAI.assistant_voice", "nova"),
            "Voix OpenAI sélectionnée"),
            ("Modèle TTS", "combo", {
                    "🚀 TTS-1 (Rapide, Standard)": "tts-1",
                    "💎 TTS-1-HD (Lent, Haute Qualité)": "tts-1-hd"
                }, self._get_config_value("openAI.tts_model", "tts-1"),
                "Modèle OpenAI TTS - HD = meilleure qualité mais plus lent"),

             ("Clé API OpenAI", "password", 
             self._get_config_value("openAI.apiKey", "xxxx-xxxx-xxxx"),
             "Clé d'API OpenAI"),


            # ✅ Test spécifique OpenAI
            ("Actions OpenAI", "button_group", [
                {
                    "text": "🤖 Test OpenAI",
                    "onclick": "test_openai_specifically",
                    "style": "secondary",
                    "tooltip": "Teste spécifiquement OpenAI avec les paramètres configurés"
                }
            ], "Actions spécifiques OpenAI"),
        ])

        self._create_section(content_layout, "SECTION INTERFACE", [
            ("Thème sombre", "checkbox", True,
             "Active le mode sombre de l'interface"),
            
            ("Transparence", "slider", 90,
             "Niveau de transparence de l'interface (0% = opaque, 100% = transparent)"),
            
            ("Langue interface", "combo", ["Français", "English"], "Français",
             "Langue d'affichage de l'interface utilisateur"),
            
            ("Notifications", "checkbox", True,
             "Affiche les notifications système lors d'événements importants"),
        ])

        self._create_section(content_layout, "SECTION MUSIQUE", [
            ("Lecteur media", "combo", ["Spotify", "YouTube", "Local"], "Spotify",
             self._get_config_value("default_mm_player", "Spotify"),
             "Lecteur multimédia par défaut"),

            ("__subsection__", "SPOTIFY", None, "Configuration Spotify"),
            ("client_id_spotify", "text", 
             self._get_config_value("spotify.clientId", "none"),
             "Client ID Spotify"),
            ("client_secret_spotify", "password", 
             self._get_config_value("spotify.clientSecret", "none"),
             "Client Secret Spotify"),
            ("client_access_token_spotify", "password", 
             self._get_config_value("spotify.client_acces_token", ""),
             "Client Access Token Spotify"),
            ("client_refresh_token_spotify", "password", 
             self._get_config_value("spotify.client_refresh_token", ""),
             "Client Refresh Token Spotify"),
            ("redirectUri_spotify", "text", 
             self._get_config_value("spotify.redirectUri", "http://localhost:8888/callback"),
             "Redirect URI Spotify (doit correspondre à l'application Spotify)"),
            ("client_pref_device_name", "text",
             self._get_config_value("spotify.client_pref_device_name", "unknown"),
             "Nom du périphérique préféré pour la lecture Spotify"),
            ("Spotify Volume", "slider_custom", {
                "value": int(self._get_config_value("spotify.defaultvolume", 50)),
                "min": 0,
                "max": 100,
                "unit": "%"
            }, "Ajuste le volume de Spotify (0% à 100%)"),

            ])

        self._create_section(content_layout, "SECTION SÉCURITÉ", [
            ("Chiffrement actif", "checkbox", True,
             "Chiffre les communications et données sensibles"),
            
            ("Logs détaillés", "checkbox", False,
             "Enregistre des logs détaillés pour le débogage"),
            
            ("Clé API OpenAI", "password", 
             self._get_config_value("openAI.api_key", "sk-xxxxxxxxxxxxxxxx"),
             "Clé d'API OpenAI pour les fonctionnalités d'intelligence artificielle"),
            
            ("Timeout réseau", "number", 5000,
             "Délai d'attente pour les connexions réseau en millisecondes"),

            # Actions système
            ("Actions Système", "button_group", [
                {
                    "text": "🔄 Reset Config",
                    "onclick": "reset_config",
                    "style": "danger",
                    "tooltip": "Remet la configuration aux valeurs par défaut (ATTENTION: irréversible)"
                }
            ], "Actions système dangereuses"),
        ])

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

    def _create_section(self, parent_layout, title, fields):
        """Crée une section avec titre et champs"""
        
        # Titre de section
        section_header = QtWidgets.QLabel(title)
        section_header.setStyleSheet("""
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
        """)
        parent_layout.addWidget(section_header)

        # Container pour les champs
        fields_container = QtWidgets.QWidget()
        fields_container.setStyleSheet("""
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
        """)

        main_layout = QtWidgets.QVBoxLayout(fields_container)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        current_subsection_layout = None
        
        for field_data in fields:
            # Sous-section
            if len(field_data) >= 2 and field_data[0] == "__subsection__":
                subsection_title = field_data[1]
                subsection_description = field_data[3] if len(field_data) > 3 else None
                
                subsection_header = QtWidgets.QLabel(f"🔸 {subsection_title}")
                subsection_header.setStyleSheet("""
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
                """)
                if subsection_description:
                    subsection_header.setToolTip(subsection_description)
                
                main_layout.addWidget(subsection_header)
                
                subsection_container = QtWidgets.QWidget()
                subsection_container.setStyleSheet("""
                    QWidget {
                        background: rgba(255, 159, 28, 0.05);
                        border: 1px solid rgba(255, 159, 28, 0.2);
                        border-radius: 6px;
                        padding: 8px;
                        margin-left: 12px;
                    }
                """)
                
                current_subsection_layout = QtWidgets.QGridLayout(subsection_container)
                current_subsection_layout.setContentsMargins(8, 8, 8, 8)
                current_subsection_layout.setSpacing(6)
                
                main_layout.addWidget(subsection_container)
                continue
            # ✅ NOUVEAU : Sous-section ALTERNATIVE (même style, couleur différente)
            elif len(field_data) >= 2 and field_data[0] == "__subsection_alt__":
                subsection_title = field_data[1]
                subsection_description = field_data[3] if len(field_data) > 3 else None
                
                subsection_header = QtWidgets.QLabel(f"🔹 {subsection_title}")  # ← Icône différente
                subsection_header.setStyleSheet("""
                    QLabel {
                        background: rgba(76, 175, 80, 0.15);         /* ← Vert au lieu de violet */
                        border-left: 3px solid #4caf50;             /* ← Bordure verte */
                        color: #4caf50;                             /* ← Texte vert */
                        font-weight: 600;                           /* ← MÊME alignement */
                        font-size: 11px;                            /* ← MÊME alignement */
                        letter-spacing: 0.5px;                      /* ← MÊME alignement */
                        padding: 4px 8px;                           /* ← MÊME alignement */
                        margin: 8px 0px 4px 0px;                    /* ← MÊME alignement */
                        border-radius: 4px;                         /* ← MÊME alignement */
                    }
                """)
                if subsection_description:
                    subsection_header.setToolTip(subsection_description)
                
                main_layout.addWidget(subsection_header)
                
                # ✅ MÊME conteneur que subsection normale
                subsection_container = QtWidgets.QWidget()
                subsection_container.setStyleSheet("""
                    QWidget {
                        background: rgba(76, 175, 80, 0.05);         /* ← Fond vert léger */
                        border: 1px solid rgba(76, 175, 80, 0.2);    /* ← Bordure verte */
                        border-radius: 6px;                         /* ← MÊME alignement */
                        padding: 8px;                               /* ← MÊME alignement */
                        margin-left: 12px;                          /* ← MÊME alignement */
                    }
                """)
                
                current_subsection_layout = QtWidgets.QGridLayout(subsection_container)
                current_subsection_layout.setContentsMargins(8, 8, 8, 8)  # ← MÊME alignement
                current_subsection_layout.setSpacing(6)                   # ← MÊME alignement
                
                main_layout.addWidget(subsection_container)
                continue
            
            # Traitement des champs normaux
            if len(field_data) >= 4:
                label_text, field_type, *args, description = field_data
                if field_type == "combo":
                    value = args[1] if len(args) > 1 else args[0][0] if isinstance(args[0], list) else list(args[0].values())[0]
                    options = args[0]
                elif field_type == "button_group":
                    value = args[0]  # Liste des boutons
                else:
                    value = args[0] if args else None
            else:
                label_text, field_type, *args = field_data
                value = args[0] if args else None
                description = None

            # Créer le widget
            widget = None
            label = None
            
            if field_type == "checkbox":
                widget = self._create_checkbox(value)
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "combo":
                widget = self._create_combo(options, value)
                config_key = self._infer_config_key(label_text)
                widget._config_key = config_key
                print(f"🔗 ComboBox '{label_text}' lié à la config '{config_key}'")
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "button_group":
                widget = self._create_button_group(value)
                label = None  # Pas de label pour un groupe
            elif field_type == "slider":
                widget = self._create_slider(value)
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "slider_custom":  # ✅ NOUVEAU
                widget = self._create_slider_custom(value)  # value contient le dict config
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "text":
                widget = self._create_text_input(value)
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "password":
                widget = self._create_password_input(value)
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "number":
                widget = self._create_number_input(value)
                label = QtWidgets.QLabel(f"{label_text}:")
            elif field_type == "folder":
                widget = self._create_folder_input(value)
                label = QtWidgets.QLabel(f"{label_text}:")

            # Style des labels
            if label and description:
                label.setStyleSheet("""
                    QLabel {
                        color: #e6e6e6;
                        font-weight: 600;
                        font-size: 13px;
                    }
                    QLabel:hover {
                        color: #ff9f1c;
                    }
                """)
                label.setToolTip(description)

            # Ajouter au layout
            if widget:
                self._form_widgets[label_text] = widget
                
                # ✅ NOUVEAU: Configurer l'auto-save avec la clé appropriée
                config_key = self._infer_config_key(label_text)
                if hasattr(widget, '_setup_auto_save') and self.auto_saver:
                    print(f"🔗 Auto-save configuré pour: {label_text} -> {config_key}")
                    widget._setup_auto_save(widget, config_key)
                
                if current_subsection_layout:
                    row = current_subsection_layout.rowCount()
                    if label:
                        current_subsection_layout.addWidget(label, row, 0)
                        current_subsection_layout.addWidget(widget, row, 1)
                    else:
                        current_subsection_layout.addWidget(widget, row, 0, 1, 2)
                else:
                    if label:
                        field_layout = QtWidgets.QGridLayout()
                        field_layout.addWidget(label, 0, 0)
                        field_layout.addWidget(widget, 0, 1)
                        main_layout.addLayout(field_layout)
                    else:
                        main_layout.addWidget(widget)

        parent_layout.addWidget(fields_container)

    def _create_button_group(self, buttons_config):
        """Crée un groupe de boutons horizontaux compacts"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        for button_config in buttons_config:
            button = self._create_compact_button(button_config)
            layout.addWidget(button)
        
        # Spacer pour aligner à gauche
        layout.addStretch()
        
        return container

    def _create_compact_button(self, button_config):
        """Crée un bouton compact"""
        text = button_config.get("text", "Action")
        onclick = button_config.get("onclick", None)
        params = button_config.get("params", {})
        style = button_config.get("style", "primary")
        tooltip = button_config.get("tooltip", "")
        
        button = QtWidgets.QPushButton(text)
        
        # Styles compacts
        button_styles = {
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
            "success": """
                QPushButton {
                    background: #00cc00;
                    border: 2px solid #00cc00;
                    border-radius: 4px;
                    color: black;
                    font-weight: 700;
                    font-size: 11px;
                    padding: 4px 8px;
                    min-width: 60px;
                    max-height: 28px;
                }
                QPushButton:hover {
                    background: #33dd33;
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
        
        button.setStyleSheet(button_styles.get(style, button_styles["primary"]))
        
        if tooltip:
            button.setToolTip(tooltip)
        
        # Connexion simple sans gestion d'état
        if onclick:
            def handle_click():
                if hasattr(self, onclick):
                    method = getattr(self, onclick)
                    if params:
                        method(params)
                    else:
                        method()
            
            button.clicked.connect(handle_click)
        
        return button

    def _create_checkbox(self, checked=False):
        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(checked)
        
        # ✅ NOUVEAU: Auto-save immédiat pour checkbox
        def setup_auto_save(widget, config_key):
            def on_state_changed(state):
                is_checked = state == QtCore.Qt.CheckState.Checked
                print(f"🔲 Checkbox {config_key}: {is_checked}")
                self.auto_saver.save_immediate(config_key, is_checked)
            
            widget.stateChanged.connect(on_state_changed)
        
        checkbox._setup_auto_save = setup_auto_save
        return checkbox

    def _create_combo(self, options, selected=None):
        """Crée un ComboBox avec support nom/valeur"""
        combo = NoWheelComboBox()
        
        if isinstance(options, dict):
            for display_name, value in options.items():
                combo.addItem(display_name, userData=value)
            if selected:
                index = combo.findData(selected)
                if index >= 0:
                    combo.setCurrentIndex(index)
        
        elif isinstance(options, list) and options and isinstance(options[0], tuple):
            for display_name, value in options:
                combo.addItem(display_name, userData=value)
            if selected:
                index = combo.findData(selected)
                if index >= 0:
                    combo.setCurrentIndex(index)
        
        else:
            combo.addItems(options)
            if selected and selected in options:
                combo.setCurrentText(selected)
        
        # Connexion pour mise à jour config
        def on_combo_changed():
            if hasattr(combo, '_config_key') and self.config_manager:
                selected_value = self._get_combo_value(combo)
                config_key = combo._config_key
                print(f"🔄 Mise à jour config: {config_key} = {selected_value}")
                self.config_manager.set(config_key, selected_value)
        
        combo.currentTextChanged.connect(on_combo_changed)
        
        combo.setStyleSheet("""
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
        """)
        return combo

    def _get_combo_value(self, combo_widget):
        """Récupère la valeur technique d'un ComboBox"""
        current_data = combo_widget.currentData()
        if current_data is not None:
            return current_data
        else:
            return combo_widget.currentText()

    def _create_slider(self, value=50, min_val=0, max_val=100):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        # ✅ FIX: Utiliser le bon constructeur
        slider = NoWheelSlider(min_val, max_val, 1)  # ← CORRECT : passer min, max, step
        slider.setOrientation(QtCore.Qt.Orientation.Horizontal)  # ← AJOUTER : définir l'orientation
        
        # Conversion sécurisée
        try:
            slider_value = int(value) if isinstance(value, (str, float)) else value
        except (ValueError, TypeError):
            slider_value = 0
            
        slider.setValue(slider_value)

        # Affichage avec unité
        value_label = QtWidgets.QLabel(f"{slider_value}%")
        value_label.setMinimumWidth(50)
        
        def update_label(v):
            value_label.setText(f"{v}%")
                
        slider.valueChanged.connect(update_label)

        # ✅ CORRIGER L'INDENTATION ICI :
        def setup_auto_save(widget_container, config_key):
            slider_widget = widget_container.findChild(NoWheelSlider)  # ← BIEN INDENTÉ
            if not slider_widget:
                return
                
            slider_timer = None
            
            def on_slider_moved(value):
                nonlocal slider_timer
                if slider_timer:
                    slider_timer.stop()
                    slider_timer.deleteLater()
                
                slider_timer = QtCore.QTimer()
                slider_timer.setSingleShot(True)
                slider_timer.timeout.connect(lambda: self.auto_saver.schedule_save(config_key, value, 0))
                slider_timer.start(3000)  # 3s après relâchement
            
            def on_slider_released():
                current_value = slider_widget.value()
                self.auto_saver.schedule_save(config_key, current_value, 500)  # 500ms
            
            slider_widget.valueChanged.connect(on_slider_moved)
            slider_widget.sliderReleased.connect(on_slider_released)
        
        container._setup_auto_save = setup_auto_save  # ← BIEN INDENTÉ

        layout.addWidget(slider)
        layout.addWidget(value_label)
        return container

    def _create_slider_custom(self, config):
        """
        Crée un slider avec paramètres personnalisés
        
        Args:
            config: Dict avec value, min, max, unit, step
        """
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ✅ FIX: Utiliser le bon constructeur avec support décimales
        min_val = config.get("min", 0)
        max_val = config.get("max", 100) 
        step = config.get("step", 1)
        
        slider = NoWheelSlider(min_val, max_val, step)  # ← CORRECT
        slider.setOrientation(QtCore.Qt.Orientation.Horizontal)  # ← AJOUTER

        # ✅ Style du slider (reste inchangé)
        slider.setStyleSheet("""
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
        """)
        
        # Conversion sécurisée de la valeur
        try:
            slider_value = float(config["value"]) if isinstance(config["value"], (str, int)) else config["value"]
        except (ValueError, TypeError):
            slider_value = 0
            
        # ✅ FIX: Utiliser la méthode set_real_value pour les décimales
        slider.set_real_value(slider_value)

        # Label avec unité et style selon valeur
        unit = config.get("unit", "")
        value_label = QtWidgets.QLabel()
        value_label.setMinimumWidth(70)
        value_label.setMaximumWidth(70)
        value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        value_label.setStyleSheet("""
            QLabel {
                background: rgba(255,255,255,0.1);
                border: 1px solid rgba(0,209,255,0.3);
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        
        def update_label_with_style(internal_value):
            # ✅ FIX: Utiliser get_real_value pour les décimales
            real_value = slider.get_real_value()
            
            if real_value >= 0 and unit:
                value_label.setText(f"+{real_value:.1f}{unit}")
                value_label.setStyleSheet(value_label.styleSheet() + "QLabel { color: #4CAF50; }")
            elif real_value < 0:
                value_label.setText(f"{real_value:.1f}{unit}")
                value_label.setStyleSheet(value_label.styleSheet() + "QLabel { color: #FF9800; }")
            else:
                value_label.setText(f"{real_value:.1f}{unit}")
                value_label.setStyleSheet(value_label.styleSheet() + "QLabel { color: #9E9E9E; }")
            
        update_label_with_style(slider.value())  # Style initial
        
        # Auto-save pour sliders personnalisés (reste inchangé)
        def setup_auto_save(widget_container, config_key):
            slider_widget = widget_container.findChild(NoWheelSlider)
            if not slider_widget:
                return
                
            slider_timer = None
            
            def on_slider_moved(internal_value):
                # Mise à jour visuelle immédiate
                update_label_with_style(internal_value)
                
                # Programmer sauvegarde avec délai
                nonlocal slider_timer
                if slider_timer:
                    slider_timer.stop()
                    slider_timer.deleteLater()
                
                # ✅ FIX: Sauvegarder la vraie valeur décimale
                real_value = slider_widget.get_real_value()
                slider_timer = QtCore.QTimer()
                slider_timer.setSingleShot(True)
                slider_timer.timeout.connect(lambda: self.auto_saver.schedule_save(config_key, real_value, 0))
                slider_timer.start(3000)  # 3s après relâchement
            
            def on_slider_released():
                real_value = slider_widget.get_real_value()
                self.auto_saver.schedule_save(config_key, real_value, 500)  # 500ms
            
            slider_widget.valueChanged.connect(on_slider_moved)
            slider_widget.sliderReleased.connect(on_slider_released)
        
        container._setup_auto_save = setup_auto_save
        slider.valueChanged.connect(update_label_with_style)
        layout.addWidget(slider, 3)  # ← MANQUAIT !
        layout.addWidget(value_label, 1)  # ← MANQUAIT !
        
        return container  # ← MANQUAIT !

    def _create_text_input(self, placeholder=""):
        input_field = QtWidgets.QLineEdit()
        input_field.setText(placeholder)
        
        # ✅ NOUVEAU: Auto-save pour text
        def setup_auto_save(widget, config_key):
            typing_timer = None
            
            def on_text_changed():
                nonlocal typing_timer
                # Annuler le timer précédent
                if typing_timer:
                    typing_timer.stop()
                    typing_timer.deleteLater()
                
                # Nouveau timer 3s
                typing_timer = QtCore.QTimer()
                typing_timer.setSingleShot(True)
                typing_timer.timeout.connect(lambda: self.auto_saver.schedule_save(config_key, widget.text(), 0))  # 0 = immédiat
                typing_timer.start(3000)  # 3 secondes
            
            def on_focus_lost():
                # Sauvegarde immédiate à la perte de focus
                self.auto_saver.save_immediate(config_key, widget.text())
            
            def on_return_pressed():
                # Sauvegarde immédiate sur Entrée
                self.auto_saver.save_immediate(config_key, widget.text())
            
            widget.textChanged.connect(on_text_changed)
            widget.editingFinished.connect(on_focus_lost)  # Perte de focus ou Entrée
            widget.returnPressed.connect(on_return_pressed)
        
        # Stocker la fonction pour l'utiliser plus tard
        input_field._setup_auto_save = setup_auto_save
        return input_field

    def _create_password_input(self, placeholder=""):
        input_field = QtWidgets.QLineEdit()
        input_field.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        input_field.setText(placeholder)
        
        # ✅ MÊME LOGIQUE que text_input
        def setup_auto_save(widget, config_key):
            typing_timer = None
            
            def on_text_changed():
                nonlocal typing_timer
                if typing_timer:
                    typing_timer.stop()
                    typing_timer.deleteLater()
                
                typing_timer = QtCore.QTimer()
                typing_timer.setSingleShot(True)
                typing_timer.timeout.connect(lambda: self.auto_saver.schedule_save(config_key, widget.text(), 0))
                typing_timer.start(3000)
            
            def on_focus_lost():
                self.auto_saver.save_immediate(config_key, widget.text())
            
            def on_return_pressed():
                self.auto_saver.save_immediate(config_key, widget.text())
            
            widget.textChanged.connect(on_text_changed)
            widget.editingFinished.connect(on_focus_lost)
            widget.returnPressed.connect(on_return_pressed)
        
        input_field._setup_auto_save = setup_auto_save
        return input_field

    def _create_number_input(self, value=0):
        input_field = QtWidgets.QSpinBox()
        input_field.setRange(0, 999999)
        input_field.setValue(value)
        
        # ✅ NOUVEAU: Auto-save pour number
        def setup_auto_save(widget, config_key):
            def on_value_changed(value):
                print(f"🔢 Number {config_key}: {value}")
                self.auto_saver.save_immediate(config_key, value)
            
            widget.valueChanged.connect(on_value_changed)
        
        input_field._setup_auto_save = setup_auto_save
        return input_field

    def _create_folder_input(self, default_path=""):
        """Crée un sélecteur de dossier"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        path_field = QtWidgets.QLineEdit()
        path_field.setText(default_path)
        path_field.setPlaceholderText("Sélectionnez un dossier...")
        
        browse_btn = QtWidgets.QPushButton("📁")
        browse_btn.setMaximumWidth(40)
        browse_btn.setToolTip("Parcourir les dossiers")
        browse_btn.setStyleSheet("""
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
        """)
        
        def open_folder_dialog():
            dialog = QtWidgets.QFileDialog()
            dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
            dialog.setOption(QtWidgets.QFileDialog.Option.ShowDirsOnly, True)
            
            if dialog.exec():
                selected_folder = dialog.selectedFiles()[0]
                import os
                try:
                    cwd = os.getcwd()
                    if selected_folder.startswith(cwd):
                        relative_path = os.path.relpath(selected_folder, cwd)
                        path_field.setText(f"./{relative_path.replace(os.sep, '/')}")
                    else:
                        path_field.setText(selected_folder)
                except:
                    path_field.setText(selected_folder)
        
        browse_btn.clicked.connect(open_folder_dialog)
        
    # ✅ NOUVEAU: Auto-save pour folder
    def setup_auto_save(widget_container, config_key):
        path_widget = widget_container._path_field
            
    def on_path_changed():
        path_value = path_widget.text()
        self.auto_saver.save_immediate(config_key, path_value)
            
        path_widget.editingFinished.connect(on_path_changed)
        
        container._setup_auto_save = setup_auto_save
        
        layout.addWidget(path_field, 1)
        layout.addWidget(browse_btn)
        
        container._path_field = path_field
        return container

    def _get_config_value(self, key, default_value):
        """Récupère une valeur de config"""
        if self.config_manager is not None:
            return self.config_manager.get(key, default_value)
        return default_value

    def _get_widget_value(self, config_key):
        """
        Récupère la valeur actuelle d'un widget de l'interface
        
        Args:
            config_key: Clé de configuration (ex: "edgetts.rate")
            
        Returns:
            Valeur actuelle du widget ou valeur par défaut
        """
        if config_key in self._form_widgets:
            widget = self._form_widgets[config_key]
            
            # Slider standard
            if hasattr(widget, 'findChild') and widget.findChild(NoWheelSlider):
                slider = widget.findChild(NoWheelSlider)
                return slider.value() if slider else 0
            
            # ComboBox
            elif hasattr(widget, 'currentText'):
                return widget.currentText()
                
            # Autres types de widgets
            elif hasattr(widget, 'value'):
                return widget.value()
                
        # Fallback vers la config
        return self.config_manager.get(config_key, 0)

    def _infer_config_key(self, label_text):
        """Infère la clé de configuration depuis le label"""
        mapping = {
            # === RECONNAISSANCE VOCALE ===
            "Debug Audio": "listen.Debug",
            "Langue": "listen.Language",
            "Confiance minimale": "listen.Confidence",
            "Mot-clé d'activation": "listen.Hotword",
            "Dossier grammaire": "listen.Grammar",
            
            # === TTS GÉNÉRAL ===
            "Moteur Vocal": "vocalisation.engine",
            "Effet": "vocalisation.effect",
            
            # === 🌿 SKIN AUDIO (SUBSECTION ALTERNATIVE VERTE) ===
            "Hauteur du skin": "effects.skin.pitch",           # Skin Audio (priorité sur Edge)
            "Vitesse du skin": "effects.skin.speed",
            "Filtre passe-haut": "effects.skin.highpass",
            "Filtre passe-bas": "effects.skin.lowpass",
            "metallic": "effects.skin.metallic",        # ← Corrigé sans espace
            "distortion": "effects.skin.distortion",
            "vocoder": "effects.skin.vocoder",
            "hash": "effects.skin.hash",
            "reverb": "effects.skin.reverb",
            "echo": "effects.skin.echo",
            "Mixage effect": "effects.skin.dry_wet",
            "Qualité": "piper.quality",
            "Cache modèles": "piper.cache_models",
            
            # === PIPER ===
            "Voix Piper": "piper.default_voice",
            "Modèle Piper": "piper.model_path",
            
            # === EDGE TTS ===
            "Voix Edge": "edgetts.default_voice",
            "Vitesse": "edgetts.rate",                  # Edge TTS vitesse
            # Note: "Tonalité" est mappé vers Skin Audio, pas Edge TTS
            # Si besoin d'un champ séparé pour Edge, renommer en "Tonalité Edge"
            
            # === OPENAI ===
            "Voix OpenAI": "openAI.assistant_voice",
            "Modèle TTS": "openAI.tts_model",
            "Clé API OpenAI": "openAI.apiKey",
            
            # === INTERFACE ===
            "Thème sombre": "interface.dark_theme",
            "Transparence": "interface.transparency",
            "Langue interface": "interface.language",
            "Notifications": "interface.notifications",
            
            # === MUSIQUE ===
            "Lecteur media": "default_mm_player",
            "client_id_spotify": "spotify.clientId",
            "client_secret_spotify": "spotify.clientSecret",
            "client_access_token_spotify": "spotify.client_access_token",
            "client_refresh_token_spotify": "spotify.client_refresh_token",
            "redirectUri_spotify": "spotify.redirectUri",
            "client_pref_device_name": "spotify.client_pref_device_name",
            "Spotify Volume": "spotify.defaultvolume",
            
            # === SÉCURITÉ ===
            "Chiffrement actif": "security.encryption",
            "Logs détaillés": "security.detailed_logs",
            "Timeout réseau": "security.network_timeout",
        }
        
        return mapping.get(label_text, f"unknown.{label_text.lower().replace(' ', '_')}")

    # ===== MÉTHODES DE TEST TTS VIA BUS D'ÉVÉNEMENTS =====

    def test_selected_engine(self, params=None):
        """Teste le moteur actuellement sélectionné dans le ComboBox"""
        try:
            # Récupérer le moteur sélectionné
            current_engine = self.config_manager.get("vocalisation.engine", "piper")
            
            # Créer l'événement TTS global
            test_event = {
                "name": "tts.speak",
                "state": "request", 
                "payload": {
                    "engine": current_engine,
                    "action": "config_test_global",
                    "text": f"Test du moteur principal {current_engine}. Ceci est le test global depuis la configuration.",
                    "effect": "none",
                    "play_now": True
                }
            }
            
            print(f"🎤 Test GLOBAL via bus: moteur {current_engine}")
            self.event_bus.publish(test_event)
            
        except Exception as e:
            print(f"❌ Erreur test global: {e}")

    def test_piper_specifically(self, params=None):
        """Teste spécifiquement Piper (ignore le sélecteur de moteur)"""
        try:
            # Récupérer la voix Piper configurée
            piper_voice = self.config_manager.get("piper.default_voice", "gilles")
            
            # ✅ FORCER Piper indépendamment du sélecteur
            test_event = {
                "name": "tts.speak",
                "state": "request", 
                "payload": {
                    "engine": "piper",  # ✅ Forcé à Piper
                    "action": "config_test_piper",
                    "text": f"Test spécifique de Piper avec la voix {piper_voice}. Configuration Piper fonctionnelle.",
                    "effect": "none",
                    "play_now": True
                }
            }
            
            print(f"🤖 Test PIPER spécifique via bus: voix {piper_voice}")
            self.event_bus.publish(test_event)
            
        except Exception as e:
            print(f"❌ Erreur test Piper spécifique: {e}")

    def test_edgetts_specifically(self, params=None):
        """Test spécifique du moteur EdgeTTS"""
        try:
            print("🧪 Test EdgeTTS demandé via interface")
            
            # Récupérer les paramètres actuels de l'interface
            current_voice = self._get_widget_value("edgetts.default_voice")
            current_rate = self._get_widget_value("edgetts.rate") 
            current_pitch = self._get_widget_value("edgetts.pitch")
            
            # Texte de test avec info sur les paramètres
            test_text = f"Test EdgeTTS avec la voix {current_voice}, vitesse {current_rate}%, tonalité {current_pitch}Hz."
            
            # Publier l'événement de test via le bus
            test_event = {
                "name": "tts.speak",
                "state": "request", 
                "payload": {
                    "engine": "edgetts",
                    "text": test_text,
                    "action": "config_test_edgetts",
                    "effect": "none",
                    "play_now": True
                }
            }
            
            print(f"🎵 Test EdgeTTS: '{test_text}'")
            self.event_bus.publish(test_event)
            
        except Exception as e:
            print(f"❌ Erreur test EdgeTTS: {e}")

    def test_openai_specifically(self, params=None):
        """Teste spécifiquement OpenAI (ignore le sélecteur de moteur)"""
        try:
            # Récupérer la voix OpenAI configurée
            openai_voice = self.config_manager.get("openAI.assistant_voice", "nova")
            
            # ✅ FORCER OpenAI indépendamment du sélecteur
            test_event = {
                "name": "tts.speak",
                "state": "request", 
                "payload": {
                    "engine": "openai",  # ✅ Forcé à OpenAI
                    "action": "config_test_openai",
                    "text": f"Test spécifique d'OpenAI avec la voix {openai_voice}. Configuration OpenAI fonctionnelle.",
                    "effect": "none",
                    "play_now": True
                }
            }
            
            print(f"🤖 Test OPENAI spécifique via bus: voix {openai_voice}")
            self.event_bus.publish(test_event)
            
        except Exception as e:
            print(f"❌ Erreur test OpenAI spécifique: {e}")

    def test_skin_audio(self, params=None):
        """Teste le skin audio avec les paramètres actuels"""
        try:
            print("🎨 Test Skin Audio demandé via interface")
            
            # Récupérer TOUS les paramètres skin actuels
            skin_params = {
                "pitch": self._get_widget_value("effects.skin.pitch"),
                "speed": self._get_widget_value("effects.skin.speed"), 
                "helium": self._get_widget_value("effects.skin.helium"),
                "metallic": self._get_widget_value("effects.skin.metallic"),
                "robotic": self._get_widget_value("effects.skin.robotic"),
                "distortion": self._get_widget_value("effects.skin.distortion"),
                "vocoder": self._get_widget_value("effects.skin.vocoder"),
                "hash": self._get_widget_value("effects.skin.hash"),
                "reverb": self._get_widget_value("effects.skin.reverb"),
                "echo": self._get_widget_value("effects.skin.echo"),
                "dry_wet": self._get_widget_value("effects.skin.dry_wet")
            }
            
            # Créer un résumé des paramètres non-nuls
            active_params = [f"{k}:{v}" for k, v in skin_params.items() if v != 0]
            params_text = f" avec {', '.join(active_params[:3])}" if active_params else " neutre"
            
            # ✅ CORRECTION: Demander génération SANS effet d'abord (pour le brut)
            test_event = {
                "name": "tts.speak",
                "state": "request", 
                "payload": {
                    "engine": self.config_manager.get("vocalisation.engine", "edgetts"),
                    "action": "config_test_skin",
                    "text": f"Test du skin audio{params_text}. Paramètres appliqués avec succès.",
                    "effect": "none",      # ← CORRECTION: Pas d'effet environment
                    "skin_test": True,     # ← NOUVEAU: Flag pour indiquer qu'on veut tester le skin
                    "play_now": True
                }
            }
            
            print(f"🎨 Test Skin: paramètres actifs = {active_params}")
            self.event_bus.publish(test_event)
            
        except Exception as e:
            print(f"❌ Erreur test skin: {e}")

    def purge_skin_cache(self, params=None):
        """Purge complètement le cache skin et environments"""
        try:
            reply = QtWidgets.QMessageBox.question(
                self, 
                "Purger Cache Skin", 
                "Supprimer TOUS les fichiers skin et environments ?\n\n• Fichiers SKIN.wav supprimés\n• Fichiers SHIP/CITY/HELMET.wav supprimés\n• Fichiers BRUT.wav conservés\n\nIls seront régénérés au prochain usage.",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Publier événement de purge sur le bus
                purge_event = {
                    "name": "cache.purge_skin",
                    "state": "request",
                    "payload": {
                        "include_environments": True,  # Purger aussi ship/city/helmet
                        "keep_brut": True,             # Garder les fichiers brut
                        "requester": "config_interface"
                    }
                }
                
                print("🗑️ Purge cache skin + environments demandée")
                self.event_bus.publish(purge_event)
                
        except Exception as e:
            print(f"❌ Erreur purge cache: {e}")

    def update_skin_cache(self, params=None):
        """Met à jour le cache skin avec les nouveaux paramètres"""
        try:
            reply = QtWidgets.QMessageBox.question(
                self, 
                "Mettre à jour Skin", 
                "Régénérer les fichiers skin avec les nouveaux paramètres ?\n\n• Fichiers SKIN.wav régénérés\n• Fichiers SHIP/CITY/HELMET.wav supprimés\n• Fichiers BRUT.wav conservés",
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes  # Oui par défaut
            )
            
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                # Publier événement de mise à jour
                update_event = {
                    "name": "cache.update_skin",
                    "state": "request",
                    "payload": {
                        "force_regenerate": True,
                        "clear_environments": True,  # Supprimer les environments pour forcer régénération
                        "requester": "config_interface"
                    }
                }
                
                print("🔄 Mise à jour cache skin demandée")
                self.event_bus.publish(update_event)
                
        except Exception as e:
            print(f"❌ Erreur mise à jour cache: {e}")

    def reset_config(self):
        """Remet la configuration aux valeurs par défaut"""
        reply = QtWidgets.QMessageBox.question(
            self, 
            "Confirmation", 
            "Êtes-vous sûr de vouloir remettre la configuration aux valeurs par défaut ?\n\nCette action est irréversible !",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            try:
                print("🔄 Réinitialisation de la configuration...")
                # TODO: Implémenter la réinitialisation réelle
                # self.config_manager.reset_to_defaults()
                print("✅ Configuration réinitialisée (simulation)")
                
            except Exception as e:
                print(f"❌ Erreur réinitialisation: {e}")
        else:
            print("❌ Réinitialisation annulée")