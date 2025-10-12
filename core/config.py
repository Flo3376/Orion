from dataclasses import dataclass

@dataclass
class Config:
    target_fps: int = 2        # limite la vitesse de la loop
    verbose: bool = True        # toggle logs verbeux
    feature_x_enabled: bool = True

CONFIG = Config()