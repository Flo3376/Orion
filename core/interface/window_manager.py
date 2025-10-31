# /core/interface/window_manager.py
"""
Gestionnaire de position et état des fenêtres
"""

import json
from pathlib import Path
from PySide6 import QtCore, QtWidgets


class WindowManager:
    """Gestionnaire pour sauvegarder/restaurer la position des fenêtres"""
    
    def __init__(self, config_file="./core/config/window_state.json", config_manager=None):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # ✅ NOUVEAU: Intégration du gestionnaire de config
        self.config_manager = config_manager
    
    def _get_debug_setting(self) -> bool:
        """Récupère le paramètre debug_sw depuis la config principale"""
        if self.config_manager:
            try:
                return self.config_manager.get("debug_sw", False)
            except Exception:
                return False
        return False
    
    def save_window_state(self, window, window_name="main_window"):
        """Sauvegarde la position et taille de la fenêtre"""
        try:
            # Récupérer la géométrie actuelle
            geometry = window.geometry()
            is_maximized = window.isMaximized()
            
            # Charger le fichier existant ou créer un nouveau
            state_data = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
            
            # Mettre à jour les données pour cette fenêtre
            state_data[window_name] = {
                "x": geometry.x(),
                "y": geometry.y(),
                "width": geometry.width(),
                "height": geometry.height(),
                "maximized": is_maximized
            }
            
            # Sauvegarder
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2)
            
            # ✅ FIX: Utiliser debug_sw depuis la config
            if self._get_debug_setting():
                print(f"💾 Position fenêtre sauvée: {window_name} -> {geometry.x()}, {geometry.y()}")
            
        except Exception as e:
            print(f"❌ Erreur sauvegarde position: {e}")
    
    def restore_window_state(self, window, window_name="main_window"):
        """Restaure la position et taille de la fenêtre"""
        try:
            if not self.config_file.exists():
                if self._get_debug_setting():
                    print("📍 Aucune position sauvée, utilisation par défaut")
                return False
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            if window_name not in state_data:
                if self._get_debug_setting():
                    print(f"📍 Aucune position sauvée pour {window_name}")
                return False
            
            window_state = state_data[window_name]
            
            x = window_state.get("x", 100)
            y = window_state.get("y", 100)
            width = window_state.get("width", 1200)
            height = window_state.get("height", 800)
            maximized = window_state.get("maximized", False)
            
            # Vérifier que la position est valide pour les écrans actuels
            app = QtWidgets.QApplication.instance()
            screens = app.screens()
            position_valid = False
            
            for screen in screens:
                screen_geometry = screen.geometry()
                if (x >= screen_geometry.x() and 
                    y >= screen_geometry.y() and
                    x < screen_geometry.x() + screen_geometry.width() and
                    y < screen_geometry.y() + screen_geometry.height()):
                    position_valid = True
                    break
            
            if position_valid:
                # Restaurer la géométrie
                window.setGeometry(x, y, width, height)
                
                # Restaurer l'état maximisé si nécessaire
                if maximized:
                    window.showMaximized()
                
                # ✅ FIX: Utiliser debug_sw depuis la config
                if self._get_debug_setting():
                    print(f"🔄 Position fenêtre restaurée: {window_name} -> {x}, {y}")
                return True
            else:
                if self._get_debug_setting():
                    print(f"⚠️ Position invalide pour {window_name}, utilisation par défaut")
                return False
                
        except Exception as e:
            print(f"❌ Erreur restauration position: {e}")
            return False
    
    def get_screen_info(self):
        """Retourne des infos sur les écrans connectés"""
        app = QtWidgets.QApplication.instance()
        if not app:
            return []
            
        screens = app.screens()
        
        print(f"🖥️ {len(screens)} écran(s) détecté(s):")
        for i, screen in enumerate(screens):
            geometry = screen.geometry()
            # ✅ FIX: Utiliser debug_sw depuis la config
            if self._get_debug_setting():
                print(f"   Écran {i}: {geometry.width()}x{geometry.height()} à ({geometry.x()}, {geometry.y()})")
        
        return screens

    def set_config_manager(self, config_manager):
        """Définit le gestionnaire de configuration"""
        self.config_manager = config_manager
        if self._get_debug_setting():
            print("🔧 WindowManager: Configuration manager défini")