"""
🎛️ FX Manager - Interface unifiée pour tous les effets audio
============================================================

Gestionnaire principal pour :
- Effets skin (pitch, speed, helium, metallic, etc.)
- Effets environment (ship, city, helmet)

Interface simple :
- fx.create_skin_for(path) → Crée skin.wav depuis brut.wav
- fx.create_for(path, effects=["ship"]) → Crée skin + effets demandés
"""

from __future__ import annotations
from pathlib import Path
from typing import Union, List, Dict, Any
import threading
import time

# Instance globale
_fx_manager_instance = None
_fx_manager_lock = threading.Lock()

class FXManager:
    """Gestionnaire unifié pour tous les effets audio"""
    
    def __init__(self, config_manager, event_bus):
        """
        Initialise le FX Manager
        
        Args:
            config_manager: Gestionnaire de configuration
            event_bus: Bus d'événements pour monitoring
        """
        self.config_manager = config_manager
        self.event_bus = event_bus
        self.processor = None  # Sera initialisé lors de la première utilisation
        
        print("🎛️ FX Manager initialisé")
    
    def _get_processor(self):
        """Lazy loading du processor pour éviter les imports circulaires"""
        if self.processor is None:
            from core.sound.fx_processor import FXProcessor
            self.processor = FXProcessor(self.config_manager, self.event_bus)
        return self.processor
    
    def create_skin_for(self, source_path: str) -> bool:
        """
        Crée uniquement le skin.wav depuis brut.wav
        
        Args:
            source_path: Chemin vers le fichier brut.wav
            
        Returns:
            bool: True si succès
        """
        try:
            source = Path(source_path)
            
            if not source.exists():
                print(f"❌ Fichier source introuvable: {source}")
                return False
            
            # Calculer le chemin skin
            skin_path = source.parent / "skin.wav"
            
            print(f"🎨 Création skin: {source.name} → {skin_path.name}")
            
            # Publier événement de monitoring (bus fragile, on protège)
            try:
                self.event_bus.publish({
                    "name": "skin.create",
                    "state": "request",
                    "payload": {
                        "source_path": str(source),
                        "target_path": str(skin_path),
                        "requester": "fx_manager"
                    }
                })
            except:
                pass  # Ignore les erreurs de bus pour ne pas casser le workflow
            
            # Récupérer les paramètres skin depuis la config
            skin_params = self._get_skin_params_from_config()
            
            # Déléguer au processor
            processor = self._get_processor()
            success = processor.apply_skin_effects(str(source), str(skin_path), skin_params)
            
            if success:
                print(f"✅ Skin créé: {skin_path.name}")
            else:
                print(f"❌ Échec création skin: {skin_path.name}")
            
            return success
            
        except Exception as e:
            print(f"❌ Erreur create_skin_for: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_for(self, source_path: str, effects: Union[str, List[str]] = "all") -> bool:
        """
        Crée skin + effets selon la demande
        
        Args:
            source_path: Chemin vers le fichier brut.wav
            effects: "all", "none", ["ship", "city"], etc.
            
        Returns:
            bool: True si succès global
        """
        try:
            source = Path(source_path)
            
            if not source.exists():
                print(f"❌ Fichier source introuvable: {source}")
                return False
            
            # Publier événement de monitoring (bus fragile, on protège)
            try:
                self.event_bus.publish({
                    "name": "fx.create_for",
                    "state": "request",
                    "payload": {
                        "source_path": str(source),
                        "effects": effects,
                        "requester": "fx_manager"
                    }
                })
            except:
                pass  # Ignore les erreurs de bus
            
            # Résoudre la liste d'effets
            effects_list = self._resolve_effects_list(effects)
            
            print(f"🎛️ Création effets pour {source.name}: {effects_list}")
            
            # === ÉTAPE 1 : S'assurer que skin.wav existe ===
            skin_path = source.parent / "skin.wav"
            
            if not skin_path.exists() or self._skin_needs_regeneration(skin_path):
                print("🎨 Génération skin nécessaire...")
                skin_success = self.create_skin_for(str(source))
                if not skin_success:
                    print("❌ Impossible de créer le skin, abandon")
                    return False
            else:
                print("⚡ Skin existant utilisé")
            
            # === ÉTAPE 2 : Générer les effets environment depuis skin ===
            if effects == "none":
                print("ℹ️ Mode 'none' → skin seulement")
                return True
            
            processor = self._get_processor()
            success_count = 0
            total_effects = len(effects_list)
            
            for effect in effects_list:
                target_path = source.parent / f"{effect}.wav"
                
                print(f"🌍 Génération {effect}: {skin_path.name} → {target_path.name}")
                
                success = processor.apply_environment_effect(str(skin_path), str(target_path), effect)
                
                if success:
                    success_count += 1
                    print(f"✅ Effet {effect} créé")
                else:
                    print(f"❌ Échec effet {effect}")
            
            # Résultat global
            if success_count == total_effects:
                print(f"✅ Tous les effets créés ({success_count}/{total_effects})")
                return True
            elif success_count > 0:
                print(f"⚠️ Succès partiel ({success_count}/{total_effects})")
                return True
            else:
                print(f"❌ Aucun effet créé (0/{total_effects})")
                return False
                
        except Exception as e:
            print(f"❌ Erreur create_for: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _resolve_effects_list(self, effects: Union[str, List[str]]) -> List[str]:
        """Résout la liste d'effets selon la demande"""
        
        available_effects = ["ship", "city", "helmet"]
        
        if effects == "all":
            return available_effects
        elif effects == "none":
            return []
        elif isinstance(effects, list):
            # Filtrer les effets valides
            return [e for e in effects if e in available_effects]
        elif isinstance(effects, str) and effects in available_effects:
            return [effects]
        else:
            print(f"⚠️ Effets non reconnus: {effects}, utilisation par défaut")
            return available_effects
    
    def _get_skin_params_from_config(self) -> Dict[str, Any]:
        """Récupère les paramètres skin depuis la configuration"""
        params = {
            "pitch": self.config_manager.get("effects.skin.pitch", 0),
            "speed": self.config_manager.get("effects.skin.speed", 0),
            "highpass": self.config_manager.get("effects.skin.highpass", 0),
            "lowpass": self.config_manager.get("effects.skin.lowpass", 0),
            "metallic": self.config_manager.get("effects.skin.metallic", 0),
            "distortion": self.config_manager.get("effects.skin.distortion", 0),
            "vocoder": self.config_manager.get("effects.skin.vocoder", 0),
            "hash": self.config_manager.get("effects.skin.hash", 0),
            "reverb": self.config_manager.get("effects.skin.reverb", 0),
            "echo": self.config_manager.get("effects.skin.echo", 0),
            "dry_wet": self.config_manager.get("effects.skin.dry_wet", 100)
        }
        
        # ✅ DEBUG : Voir EXACTEMENT ce qui est lu
        print(f"🔍 DEBUG config lue: {params}")
        return params
    
    def _skin_needs_regeneration(self, skin_path: Path) -> bool:
        """
        Vérifie si le skin doit être régénéré
        
        Pour l'instant, toujours False (on fait confiance au cache)
        TODO: Comparer timestamp config vs fichier
        """
        return False


def get_fx_manager(config_manager, event_bus) -> FXManager:
    """
    Retourne l'instance singleton du FX Manager
    
    Args:
        config_manager: Gestionnaire de configuration
        event_bus: Bus d'événements
        
    Returns:
        FXManager: Instance singleton
    """
    global _fx_manager_instance
    
    with _fx_manager_lock:
        if _fx_manager_instance is None:
            _fx_manager_instance = FXManager(config_manager, event_bus)
        
        return _fx_manager_instance