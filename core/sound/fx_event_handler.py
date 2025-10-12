"""
🎛️ FX Event Handler - Gestionnaire d'événements pour génération d'effets
========================================================================

Écoute les événements fx.* sur le bus et déclenche la génération d'effets.
"""

from core.sound.fx_generator import fx_generator, Priority

class FXEventHandler:
    """Gestionnaire d'événements pour la génération d'effets"""
    
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self._register_handlers()
    
    def _register_handlers(self):
        """Enregistre les gestionnaires d'événements"""
        self.event_bus.subscribe("fx.generate_effect", self._handle_generate_effect)
        self.event_bus.subscribe("fx.generate_all_variants", self._handle_generate_all_variants)
        print("🎛️ FX Event Handler initialisé")
    
    def _handle_generate_effect(self, event):
        """Gère l'événement de génération d'effet unique"""
        payload = event.get("payload", {})
        
        source_path = payload.get("source_path")
        effect_type = payload.get("effect_type")
        priority_str = payload.get("priority", "normal")
        force_remake = payload.get("force_remake", False)
        requester = payload.get("requester", "unknown")
        
        # Convertir priorité string → enum
        priority_map = {
            "low": Priority.LOW,
            "normal": Priority.NORMAL, 
            "high": Priority.HIGH,
            "urgent": Priority.URGENT
        }
        priority = priority_map.get(priority_str, Priority.NORMAL)
        
        print(f"🎛️ Bus: Génération effet {effect_type} (priorité: {priority_str}, requester: {requester})")
        
        # Déclencher génération asynchrone
        success = fx_generator.create_async(source_path, effect_type, force_remake, priority)
        
        if success:
            print(f"✅ Effet {effect_type} programmé")
        else:
            print(f"❌ Erreur programmation effet {effect_type}")
    
    def _handle_generate_all_variants(self, event):
        """Gère l'événement de génération de toutes les variantes"""
        payload = event.get("payload", {})
        
        source_path = payload.get("source_path")
        effects = payload.get("effects", [])
        priority_str = payload.get("priority", "low")
        force_remake = payload.get("force_remake", False)
        requester = payload.get("requester", "unknown")
        
        # Convertir priorité
        priority_map = {
            "low": Priority.LOW,
            "normal": Priority.NORMAL,
            "high": Priority.HIGH, 
            "urgent": Priority.URGENT
        }
        priority = priority_map.get(priority_str, Priority.LOW)
        
        print(f"🎛️ Bus: Génération toutes variantes {effects} (priorité: {priority_str}, requester: {requester})")
        
        # Programmer chaque effet
        programmed = 0
        for effect in effects:
            if fx_generator.create_async(source_path, effect, force_remake, priority):
                programmed += 1
        
        print(f"✅ {programmed}/{len(effects)} variantes programmées")

# Instance globale
fx_event_handler = None

def init_fx_event_handler(event_bus):
    """Initialise le gestionnaire d'événements FX"""
    global fx_event_handler
    fx_event_handler = FXEventHandler(event_bus)
    return fx_event_handler