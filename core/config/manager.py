"""
Module de gestion de configuration avec validation par empreinte
/core/config/manager.py
"""

from ruamel.yaml import YAML
from pathlib import Path
from typing import Dict, Any, Optional, Union
from core.bus import EventBus


class ConfigSection:
    """Classe pour accéder aux sections de config avec notation pointée"""
    
    def __init__(self, config_manager, section_name):
        self._config_manager = config_manager
        self._section_name = section_name
        
    
    def __getattr__(self, name):
        """Permet d'accéder aux valeurs avec config.listen.confidence"""
        return self._config_manager.get(f"{self._section_name}.{name}")
    
    def __setattr__(self, name, value):
        """Permet de modifier avec config.listen.confidence = 0.9"""
        if name.startswith('_'):
            # Attributs internes de la classe
            super().__setattr__(name, value)
        else:
            self._config_manager.set(f"{self._section_name}.{name}", value)


class ConfigManager:
    """Gestionnaire de configuration YAML avec validation par empreinte"""
    
    def __init__(self, event_bus: EventBus, config_path: str = None):
        self.event_bus = event_bus
        self.config_path = Path(config_path or "./core/config/config.yaml")
        self._data: Dict[str, Any] = {}
        self._fingerprint: Optional[str] = None
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.default_flow_style = False

        # Empreinte de validation (structure attendue avec types et défauts)
        self.config_template = {
            "version": {
                "ver": {
                    "type": str,
                    "default": "1.2.1",
                    "emptyable": False
                }
            },
            "listen": {
                "grammar": {
                    "type": str,
                    "default": "./core/grammar/",
                    "emptyable": False
                },
                "confidence": {
                    "type": (float, int, str),
                    "default": 0.75,
                    "emptyable": False
                },
                "language": {
                    "type": str,
                    "default": "fr-FR",
                    "emptyable": False
                },
                "Microphone": {
                    "type": int,
                    "default": 1,
                    "emptyable": False
                },
                "hotword": {
                    "type": str,
                    "default": "Swan",
                    "emptyable": False
                },
                "debug": {
                    "type": bool,
                    "default": True,
                    "emptyable": False
                }
            },
            "mic": {
                "path_input": {"type": str, "default": "/sound/input_mic_sound/", "emptyable": False},
                "debug_mic": {"type": bool, "default": False, "emptyable": False}
            },
            "openAI": {
                "apiKey": {"type": str, "default": "", "emptyable": True},
                "assistant_id": {"type": str, "default": "", "emptyable": True},
                "thread_id": {"type": str, "default": "", "emptyable": True},
                "assistant_name": {"type": str, "default": "Swan_sc_0.6_b", "emptyable": False},
                "model_assistant": {"type": str, "default": "gpt-4-turbo", "emptyable": False},
                "assistant_voice": {"type": str, "default": "nova", "emptyable": False},
                "path_output": {"type": str, "default": "/sound/output_sound/openAI/", "emptyable": False}
            },
            "push_to_talk": {
                "keyboard": {
                    "keyboard_key": {"type": str, "default": "SCROLL LOCK", "emptyable": False}
                },
                "joystick": {
                    "vendorId": {"type": int, "default": 13124, "emptyable": False},
                    "productId": {"type": int, "default": 32971, "emptyable": False},
                    "tramId": {"type": int, "default": 21, "emptyable": False},
                    "bp_Id": {"type": int, "default": 64, "emptyable": False}
                }
            },
            "revoicer": {
                "email": {"type": str, "default": "", "emptyable": True},
                "password": {"type": str, "default": "", "emptyable": True},
                "campaignId": {"type": str, "default": "55351", "emptyable": False},
                "default_tone": {"type": str, "default": "normal", "emptyable": False},
                "default_langage": {"type": str, "default": "fr", "emptyable": False},
                "default_voice": {"type": str, "default": "fr-FR-DeniseNeural", "emptyable": False},
                "path_output": {"type": str, "default": "/sound/output_sound/revoicer/", "emptyable": False}
            },
            "google": {
                "apiKey": {"type": (str, type(None)), "default": None, "emptyable": True}
            },
            "spotify": {
                "client_id": {"type": str, "default": "02a722539e174c4ca2b7becf21c0222d", "emptyable": False},
                "client_secret": {"type": str, "default": "87a6f4b2cb964a3cb6ab3f36fbeb8df3", "emptyable": False},
                "redirect_uri": {"type": str, "default": "http://localhost:8888/callback", "emptyable": False},
                "device_name_preference": {"type": str, "default": "DESKTOP-PA27E11", "emptyable": True},
                "default_volume": {"type": (int, float), "default": 50, "emptyable": False}
            },
            "default_mm_player": {
                "type": str,
                "default": "spotify",
                "emptyable": False
            },
            "sound_bank": {
                "path_output": {"type": str, "default": "/sound/output_sound/sound_bank/", "emptyable": False}
            },
            "vocalisation": {
                "engine": {"type": str, "default": "openAI", "emptyable": False},
                "volume": {"type": (int, str), "default": "100", "emptyable": False},
                "effect": {"type": str, "default": "none", "emptyable": False}
            },
            "tokenizer": {
                "type": str,
                "default": "local",
                "emptyable": False
            },
            "debug_sw": {
                "type": bool,
                "default": False,
                "emptyable": False
            }
        }

        # Créer le répertoire config s'il n'existe pas
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialiser ruamel.yaml pour préserver les commentaires
        self.load()
        
    
    def __getattr__(self, name):
        """Permet d'accéder aux sections avec config.listen, config.spotify"""
        if name in self._data:
            return ConfigSection(self, name)
        raise AttributeError(f"Section '{name}' not found in configuration")
    
    def _validate_and_complete_config(self) -> bool:
        """Valide la config actuelle contre l'empreinte et complète si nécessaire"""
        config_modified = False
        
        def process_section(config_section, template_section, section_path=""):
            nonlocal config_modified
            
            # Si la section n'existe pas, la créer
            if not isinstance(config_section, dict):
                print(f"⚠️ Section {section_path} manquante ou invalide, création...")
                config_section = {}
                config_modified = True
            
            for key, template_def in template_section.items():
                current_path = f"{section_path}.{key}" if section_path else key
                
                if isinstance(template_def, dict) and "type" in template_def:
                    # C'est une définition de champ
                    expected_type = template_def["type"]
                    default_value = template_def["default"]
                    emptyable = template_def.get("emptyable", False)
                    
                    if key not in config_section:
                        print(f"➕ Ajout de {current_path} = {default_value}")
                        config_section[key] = default_value
                        config_modified = True
                    else:
                        value = config_section[key]
                        
                        # Vérifier si la valeur est vide et si c'est autorisé
                        if not emptyable and (value is None or value == "" or (isinstance(value, (list, dict)) and len(value) == 0)):
                            print(f"🔧 {current_path} est vide mais ne peut pas l'être, utilisation de la valeur par défaut: {default_value}")
                            config_section[key] = default_value
                            config_modified = True
                        
                        # Vérifier le type si la valeur n'est pas vide
                        elif value is not None and value != "":
                            if isinstance(expected_type, tuple):
                                # Plusieurs types acceptés
                                if not isinstance(value, expected_type):
                                    print(f"🔧 {current_path} type incorrect ({type(value).__name__}), correction avec: {default_value}")
                                    config_section[key] = default_value
                                    config_modified = True
                            else:
                                # Un seul type attendu
                                if not isinstance(value, expected_type):
                                    print(f"🔧 {current_path} type incorrect ({type(value).__name__}), correction avec: {default_value}")
                                    config_section[key] = default_value
                                    config_modified = True
                
                else:
                    # C'est une sous-section
                    if key not in config_section:
                        config_section[key] = {}
                        config_modified = True
                    
                    config_section[key] = process_section(
                        config_section[key], 
                        template_def, 
                        current_path
                    )
            
            return config_section
        
        # Traiter toutes les sections
        self._data = process_section(self._data, self.config_template)
        
        if config_modified:
            print("📝 Configuration complétée/corrigée, sauvegarde...")
            self.save()
        else:
            print("✅ Configuration conforme à l'empreinte")
        
        return True
    
    def load(self) -> bool:
        """Charge la configuration depuis le fichier YAML"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._data = self.yaml.load(f) or {}  # ← Utiliser _yaml_parser
                print(f"Configuration chargée depuis {self.config_path}")
            else:
                print(f"Fichier de configuration absent...")
                self._data = {}
            
            return True
            
        except Exception as e:
            print(f"Erreur lors du chargement de la configuration: {e}")
            self._data = {}
            return False
    
    def set(self, key: str, value: Any) -> bool:
        """
        Définit une valeur dans la configuration et sauvegarde
        
        Args:
            key: Clé en notation pointée (ex: "listen.Microphone")
            value: Valeur à définir
            
        Returns:
            bool: True si sauvegarde réussie
        """
        try:
            # Naviguer dans la structure et définir la valeur
            keys = key.split('.')
            current = self._data
            
            # Créer la structure si nécessaire
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            
            # Définir la valeur finale
            current[keys[-1]] = value
            
            # Sauvegarder immédiatement
            return self.save()
            
        except Exception as e:
            print(f"❌ Erreur lors de la définition de {key}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Sauvegarde la configuration dans le fichier
        
        Returns:
            bool: True si sauvegarde réussie
        """
        try:
            # Créer le répertoire parent si nécessaire
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Sauvegarder avec ruamel.yaml pour préserver le formatage
            with open(self.config_path, 'w', encoding='utf-8') as file:
                self.yaml.dump(self._data, file)
            
            # Publier un événement de sauvegarde
            self.event_bus.publish({
                "name": "config",
                "state": "saved",
                "payload": {"path": str(self.config_path)}
            })
            
            print(f"✅ Configuration sauvegardée: {self.config_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde: {e}")
            self.event_bus.publish({
                "name": "config",
                "state": "error",
                "payload": {"error": str(e)}
            })
            return False
    
    def get(self, path: str, default=None) -> Any:
        """Récupère une valeur de configuration avec notation pointée"""
        keys = path.split('.')
        value = self._data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Récupère une section complète de la configuration"""
        return self._data.get(section, {})
    
    def reload(self) -> bool:
        """Recharge la configuration depuis le fichier"""
        old_config = self._data.copy()
        
        if self.load():
            # Publier l'événement de rechargement sur le bus
            self._publish_event("reloaded", {
                "old_config": old_config,
                "new_config": self._data
            })
            return True
        
        return False
    
    def _publish_event(self, state: str, payload: Dict[str, Any] = None):
        """Publie un événement sur le bus"""
        if payload is None:
            payload = {}
        
        message = {
            "name": "config",
            "state": state,
            "payload": payload
        }
        self.event_bus.publish(message)


# Instance globale
_config_manager: Optional[ConfigManager] = None

def get_config_manager(event_bus: EventBus, config_path: str = None) -> ConfigManager:
    """Retourne l'instance du gestionnaire de configuration"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(event_bus, config_path)
    return _config_manager