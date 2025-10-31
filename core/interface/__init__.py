# /core/interface/__init__.py
from .main_window import OrionMainWindow

def create_interface(event_bus, config_manager):
    """
    Crée et configure l'interface principale
    """
    
    # ✅ FIX: Passer les 2 paramètres requis
    main_window = OrionMainWindow(event_bus, config_manager)  # ← 2 paramètres !
    
    return main_window