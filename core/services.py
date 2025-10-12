def init_audio():
    print("[SERVICES] init_audio() : OK (factice)")

def init_network():
    print("[SERVICES] init_network() : OK (factice)")

def poll_inputs():
    # Ici tu lirais clavier/souris/manette… On simule :
    print("[SERVICES] poll_inputs() : (factice) -> aucune entrée")

def update_game_state(dt: float):
    # dt = temps écoulé depuis le dernier tick
    print(f"[SERVICES] update_game_state(dt={dt:.3f}s) : (factice)")

def render_frame():
    # Dans un vrai projet : dessin UI / logs / métriques…
    print("[SERVICES] render_frame() : (factice)")
