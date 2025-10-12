import time
from core.config import CONFIG
from core import services

class GameLoop:
    def __init__(self, target_fps: int | None = None):
        self.target_fps = target_fps or CONFIG.target_fps
        self._running = False
        self._spf = 1.0 / float(self.target_fps)  # seconds per frame

    def start(self):
        print(f"[LOOP] Démarre à {self.target_fps} FPS (spf={self._spf:.4f}s)")
        self._running = True
        last = time.perf_counter()

        while self._running:
            now = time.perf_counter()
            dt = now - last
            last = now

            # --- Phase "update" (CPU logique)
            services.poll_inputs()
            services.update_game_state(dt)

            # --- Phase "render/log"
            services.render_frame()

            # --- Throttle: dort le temps nécessaire pour tenir la cadence
            elapsed = time.perf_counter() - now
            sleep_time = self._spf - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self._running = False
        print("[LOOP] Arrêt demandé.")
