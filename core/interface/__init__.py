# /core/interface/__init__.py
from .main_window import OrionMainWindow

def create_interface(event_bus):
    """Crée et retourne la fenêtre principale"""
    return OrionMainWindow(event_bus)