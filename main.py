from __future__ import annotations
from core.sound.player import SoundManager
from core.sound.spotify import SpotifyController
from core.listen.listen import get_listen_manager
from core.config.manager import get_config_manager
from core.log_manager import init_new_session
import time
import threading
from core.interface import create_interface
from core.interface.window_manager import WindowManager
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict
import yaml
from PySide6 import QtCore, QtGui, QtWidgets
from pprint import pprint
from core.bus import EventBus
from core.vocalizer import Vocalizer
from core.sound.fx_event_handler import init_fx_event_handler
from core.lexique.manager import get_lexique_manager
import queue  # Pour les exceptions queue.Empty
import signal
import sys
from core.pol import create_pol
pol = create_pol(source_id=1)

# ✅ Variables globales
bus = EventBus()
listen_started = False
config = None  # ← Déclarer config globalement
sm = None      # ← Déclarer sm globalement
#fx_handler = init_fx_event_handler(bus)
lexique = get_lexique_manager()
# --- callback événements ---
def on_bus_message(msg):
    global sm  # ✅ Utiliser l'instance globale sm (pas sound_manager)
    
    name = msg["name"]
    state = msg["state"]
    payload = msg.get("payload", {})

    # ========== FILTRAGE DES MESSAGES VERBEUX ==========
    # Masquer les messages Spotify trop fréquents pour éviter le spam
    if name == "spotify" and state in ["playback", "playing","app_check", "paused","polling","volume_command","device_scan","command_success"]:
        return  # On ignore ces messages, pas d'affichage
    
    # Masquer les messages debug de listen (trop verbeux)
    if name == "listen.main_listener" and state == "debug":
        return  # On ignore ces messages debug
    
    # ✅ NOUVEAU : Filtrer les événements de volume qui spamment
    if name == "volume" and state in ["music_changed", "journal_changed", "info_changed", "master_changed"]:
        return
    
    # ✅ NOUVEAU : Filtrer les événements duck trop fréquents
    if name == "duck" and state in ["on", "off"]:
        return
    
    # ✅ NOUVEAU : Filtrer les événements audio de routine
    if name in ["info", "music", "journal"] and state in ["low_enqueued", "low_started", "low_finished"]:
        return
    
    if name == "listen.main_listener" and state == "started":
        listen_started = True

    #pour les test audio de la config
    if name == "audio.play_file" and state == "request":
        pol.write(1, "🔊 Test audio en cours...", "log")
        if sm:  # ✅ Utiliser sm au lieu de SoundManager
            # Utiliser la priorité info (basse) comme dans la doc
            sm.info.play(payload.get("file", ""), priority="low")
        else:
            pol.write(3, "❌ SoundManager non initialisé", "log+print")
    elif name == "audio.play_file" and state == "success":
        pol.write(1, "✅ Test audio réussi", "log")
    elif name == "audio.play_file" and state == "error":
        pol.write(3, "❌ Erreur lors du test audio", "log+print")

    # Traitement spécial pour les reconnaissances vocales
    if name == "listen.main_listener" and state == "recognition":
        
        data = payload.get("data", {})
        
        # ✅ CORRECTION ÉCHELLE : Listen renvoie 0-1, config stocke 0-100
        confidence_received = data.get("confidence", 0)  # 0-1 (ex: 0.85)
        confidence_threshold_config = config.get("listen.Confidence", 50)  # 0-100 (ex: 50)
        
        # Convertir le seuil de config (0-100) vers l'échelle listen (0-1)
        confidence_threshold = confidence_threshold_config / 100.0  # ex: 50 -> 0.5
        
        if confidence_received < confidence_threshold:
            # ✅ PROTECTION : Vérifier que data et options existent
            options = data.get("options")
            if options is None:
                action_detected = "données_manquantes"
            else:
                action_detected = options.get("action", "commande_inconnue")
            pol.write(2, f"🎤 Commande rejetée '{action_detected}' (confiance trop basse: {confidence_received:.2f} < {confidence_threshold:.2f})", "log")
            pol.write(2, f"🎤 COMMANDE REJETÉE '{action_detected}' (confiance trop basse)", "log")
            pol.write(2, f"💡 Confiance reçue: {confidence_received:.2f} ({confidence_received*100:.0f}%)", "log")
            pol.write(2, f"💡 Seuil requis: {confidence_threshold:.2f} ({confidence_threshold_config}%)", "log")
            return
        pol.write(2, f"🎤 Commande acceptée (confiance suffisante: {confidence_received:.2f} >= {confidence_threshold:.2f})", "log")
        pol.write(1, f"✅ Confiance OK: {confidence_received:.2f} ({confidence_received*100:.0f}%) >= {confidence_threshold:.2f} ({confidence_threshold_config}%)", "log")
        pol.write(1, f"🎤 COMMANDE RECONNUE (COMPLET):", "log")

        # ✅ PROTECTION : Vérifier que options existe avant de l'utiliser
        options = data.get("options")
        if options is None:
            pol.write(3, "⚠️ Aucune option trouvée dans les données de reconnaissance", "log+print")
            action_detected = "options_manquantes"
        else:
            action_detected = options.get("action", "action_manquante")
        # Récupérer l'action dans le lexique
        action = lexique.get_action(action_detected)
        random_response = lexique.get_random_response(action_detected)
        
        pol.write(1, f"🎤 COMMANDE RECONNUE: {action_detected}", "log")
        pol.write(1, f"💬 Réponse aléatoire: {random_response}", "log")
        pol.write(1, f"🗂️ effect: {config.get('vocalisation.effect', 'none')}", "log")
        action_event = {
            "name": "tts.speak",
            "state": "request",
            "payload": {
                "engine": config.get("vocalisation.engine", "edgetts"),
                "action": action_detected, 
                "text": random_response,
                #"effect": action.effect if action else config.get("vocalisation.default_effect", "none"),
                "effect": config.get("vocalisation.effect", "none"),
                "play_now": True
            }
        }
        bus.publish(action_event)
        return

    # Afficher tous les autres messages normalement
    print("[MAIN] Event:", name, state, payload)

    if name == "tts.speak" and state == "request":
        pol.write(1, "🎵 Demande TTS via bus...", "log")
        
        # Créer une instance VCZ
        from core.vocalizer import Vocalizer
        vcz = Vocalizer(config, bus)
           
        # Extraire les paramètres
        engine = payload.get("engine", "piper")
        action = payload.get("action", "default")
        text = payload.get("text", "Test")
        effect = payload.get("effect", "none")
        play_now = payload.get("play_now", True)

        pol.write(1, f"🎤 TTS: {engine}/{action} - '{text[:30]}...'", "log")

        # ✅ Déléguer au VCZ (qui publiera audio.play_file si succès)
        result = vcz.create(engine, action, text, effect, play_now)
    
    if name == "info.high.started":
        pol.write(1, "Info HIGH démarrée, musique et journal stoppés.", "log")
        # ex : LED bureau rouge + baisse Spotify
        # hue.set_color("red")
        # spotify.lower_volume()
        pass
    elif name == "duck.on":
        # si un autre lecteur est actif, baisse-le aussi
        pass
    elif name == "duck.off":
        # remonte le volume externe
        pass

    # ✅ NOUVEAU : Gestion des événements FX Generator
    if name == "fx.generate_effect" and state == "request":
        pol.write(1, "🎛️ Demande génération effet via bus...", "log")
        
        # Lazy import pour éviter les dépendances circulaires
        from core.sound.fx_generator import fx_generator
        
        # Extraire les paramètres
        source_path = payload.get("source_path", "")
        effect_type = payload.get("effect_type", "")
        priority_str = payload.get("priority", "normal")
        force_remake = payload.get("force_remake", False)
        requester = payload.get("requester", "unknown")
        
        # Convertir priorité string → enum
        from core.sound.fx_generator import Priority
        priority_map = {
            "low": Priority.LOW,
            "normal": Priority.NORMAL, 
            "high": Priority.HIGH,
            "urgent": Priority.URGENT
        }
        priority = priority_map.get(priority_str, Priority.NORMAL)
        
        pol.write(1, f"🎛️ Génération effet {effect_type} (priorité: {priority_str}, source: {requester})", "log")

        # Déclencher génération asynchrone
        success = fx_generator.create_async(source_path, effect_type, force_remake, priority)
        
        if success:
            pol.write(1, f"✅ Effet {effect_type} programmé", "log")
        else:
            pol.write(3, f"❌ Erreur programmation effet {effect_type}", "log+print")

    elif name == "fx.generate_all_variants" and state == "request":
        pol.write(1, "🎛️ Demande génération toutes variantes via bus...", "log")
        
        # Lazy import pour éviter les dépendances circulaires
        from core.sound.fx_generator import fx_generator, Priority
        
        # Extraire les paramètres
        source_path = payload.get("source_path", "")
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
        
        pol.write(1, f"🎛️ Génération toutes variantes {effects} (priorité: {priority_str}, source: {requester})", "log")

        # Programmer chaque effet
        programmed = 0
        for effect in effects:
            if fx_generator.create_async(source_path, effect, force_remake, priority):
                programmed += 1

        pol.write(1, f"✅ {programmed}/{len(effects)} variantes programmées", "log")

# ✅ Corriger la fonction async
def start_listen_manager_async():
    """Démarre le listen manager de façon asynchrone"""
    global config  # ✅ Utiliser la variable globale
    try:
        print("🎤 Démarrage du listen manager...")
        listen_mgr = get_listen_manager(bus, config.get_section("listen").get("debug", False))
        options = config.get_section("listen")
        listen_mgr.start("main_listener", options)
        print("✅ Listen manager démarré avec succès")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage du listen manager: {e}")
        import traceback
        traceback.print_exc()

def main():
    global config, sm, lexique, window_manager  # ✅ Ajouter window_manager
    
    # ✅ PREMIÈRE CHOSE : Rotation des logs (avant tout autre traitement)
    init_new_session()
    #pol = create_pol(source_id=1)
    pol.write(1, "🚀 Démarrage d'Orion...", "log+print")  # LEGER + console
    
    sm = SoundManager(event_bus=bus)
    
    # Créer l'application Qt
    app = QtWidgets.QApplication([])
    
    # ✅ NOUVEAU : Gestionnaire de signal pour Ctrl+C
    def signal_handler(sig, frame):
        pol.write(1, "🛑 Interruption détectée (Ctrl+C)", "log")
        #print("\n🛑 Interruption détectée (Ctrl+C)")
        pol.write(1, "🔄 Arrêt en cours...", "log")
        #print("🔄 Arrêt en cours...")
        
        # Arrêter proprement les composants
        try:
            if sm:
                pol.write(1, "🔊 Arrêt SoundManager...", "log")
                #print("🔊 Arrêt SoundManager...")
                sm.stop_all()

            pol.write(1, "🚪 Fermeture application...", "log")
            #print("🚪 Fermeture application...")
            app.quit()  # Fermer l'application Qt
            
        except Exception as e:
            pol.write(3, f"⚠️ Erreur lors de l'arrêt: {e}", "log")
            #print(f"⚠️ Erreur lors de l'arrêt: {e}")

        pol.write(1, "👋 Au revoir !", "log")
        sys.exit(0)
    
    # ✅ INSTALLER le gestionnaire de signal
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # Termination
    
    # ✅ IMPORTANT : Timer pour traiter les signaux dans Qt
    timer = QtCore.QTimer()
    timer.start(100)  # Vérifier les signaux toutes les 100ms
    timer.timeout.connect(lambda: None)  # Permet à Python de traiter les signaux
    
    # ✅ Créer le gestionnaire de configuration et l'assigner à la variable globale
    config = get_config_manager(bus)
    
    # ✅ Passer config au lexique pour hotword
    lexique.set_config_manager(config)
    
    # ✅ Maintenant on peut faire update_SRGS
    pol.write(1, "🎙️ Génération des grammaires SRGS...", "log")
    if not lexique.update_SRGS(force=True):
       pol.write(3, "⚠️ Problème avec la génération des grammaires, continuons...", "log+print")

    # ✅ Créer le gestionnaire de fenêtres AVEC la config
    from core.interface.window_manager import WindowManager
    window_manager = WindowManager(config_manager=config)
    
    # ✅ Créer l'interface principale (SANS window_manager)
    interface = create_interface(bus, config)
    
    # ✅ Gérer la position avec window_manager APRÈS création
    window_manager.get_screen_info()
    
    # ✅ Restaurer la position avant d'afficher
    position_restored = window_manager.restore_window_state(interface, "orion_main")
    if not position_restored:
        # Position par défaut sur l'écran secondaire si disponible
        screens = app.screens()
        if len(screens) > 1:
            # Placer sur le deuxième écran
            secondary_screen = screens[1]
            geometry = secondary_screen.geometry()
            interface.move(geometry.x() + 100, geometry.y() + 100)
            pol.write(1, f"📍 Positionnement sur écran secondaire: {geometry.x() + 100}, {geometry.y() + 100}", "log")
    
    # Afficher l'interface
    interface.show()
    
    # ✅ Connecter la sauvegarde à la fermeture
    def on_close(event):
        pol.write(1, "💾 Sauvegarde de la position de fenêtre...", "log")
        window_manager.save_window_state(interface, "orion_main")
        event.accept()
    
    # ✅ Connecter l'événement de fermeture proprement
    interface.closeEvent = on_close

    pol.write(1, "✅ Interface créée et positionnée", "log")

    # --- abonnement aux événements ---
    bus.subscribe(on_bus_message)

    # ✅ DÉMARRAGE ASYNCHRONE du listen manager (pas de freeze de l'interface)
    listen_thread = threading.Thread(target=start_listen_manager_async, daemon=True)
    listen_thread.start()

    # ❌ SUPPRIMER CES LIGNES :
    # Dans une autre partie du code
    # vcz = Vocalizer(config, bus)
    # vcz.create("piper", "start_orion", "Bonjour je suis votre copilote Orion", "none", True)

    # Dans ton code principal
    #vcz.create("edgetts", "test", "Bonjour Star Citizen", "none", True)

    # ✅ REMPLACER PAR un événement via bus (optionnel) :
    def send_startup_greeting():
        """Envoie un message d'accueil après démarrage"""
        time.sleep(2)  # Attendre 2 secondes après démarrage
        
        # ✅ NOUVEAU : Récupérer le message d'accueil personnalisé depuis la config
        welcome_message = config.get("vocalisation.welcome", "Bonjour, je suis votre copilote Orion. Système en cours de démarrage.")
        
        startup_event = {
            "name": "tts.speak",
            "state": "request",
            "payload": {
                "engine": config.get("vocalisation.engine", "edgetts"),
                "action": "start_orion", 
                "text": welcome_message,  # ✅ Utiliser le message personnalisé
                "effect": config.get("vocalisation.effect", "none"),
                "play_now": True
            }
        }
        bus.publish(startup_event)
        
        pol.write(1, "🎤 Message d'accueil envoyé via bus", "log")

    # Lancer le message d'accueil en thread (optionnel)
    greeting_thread = threading.Thread(target=send_startup_greeting, daemon=True)
    greeting_thread.start()

    # ✅ Boucle principale Qt
    pol.write(1, "🚀 Interface lancée - Listen manager en cours de démarrage...", "log+print")
    pol.write(1, "💡 Utilisez Ctrl+C pour arrêter l'application", "log")

    try:
        exit_code = app.exec()
    except KeyboardInterrupt:
        pol.write(3, "🛑 Interruption clavier détectée", "log+print")
        signal_handler(signal.SIGINT, None)

    pol.write(1, "👋 Au revoir !", "log+print")
    exit(exit_code)

if __name__ == "__main__":
    main()

