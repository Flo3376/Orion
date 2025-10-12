from core.config import CONFIG
from core.loop import GameLoop
from core import services

class App:
    def __init__(self):
        self.loop = GameLoop(CONFIG.target_fps)

    def start(self):
        print("[APP] Init…")
        services.init_audio()
        services.init_network()
        print("[APP] Init OK. Lancement de la loop.")
        self.loop.start()

    def stop(self):
        print("[APP] Arrêt…")
        self.loop.stop()
        print("[APP] Nettoyage terminé.")
