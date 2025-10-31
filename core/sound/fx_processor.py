"""
🔧 FX Processor - Moteur unifié pour tous les effets audio
=========================================================

Processeur unifié qui applique TOUS les effets audio :
- Effets SKIN : pitch, speed, helium, metallic, robotic, etc.
- Effets ENVIRONMENT : ship, city, helmet

Utilise FFmpeg en priorité avec fallback numpy.
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional
import subprocess
import tempfile
import numpy as np
from core.config.manager import ConfigManager
from core.bus import EventBus

class FXProcessor:
    """Processeur unifié pour tous les effets audio"""
    
    def __init__(self, config_manager: ConfigManager, event_bus: EventBus):
        self.config_manager = config_manager
        self.event_bus = event_bus
        
        if self._get_config_value("debug_sw", False): print("🔧 FXProcessor initialisé")
    
    def apply_skin_effects(self, source_path: str, target_path: str, skin_params: dict) -> bool:
        """Applique les effets skin depuis brut.wav vers skin.wav avec FFmpeg"""
        try:
            # ✅ DEBUG : Afficher TOUS les paramètres reçus
            if self._get_config_value("debug_sw", False): print(f"🔍 DEBUG skin_params REÇUS: {skin_params}")
            
            source = Path(source_path)
            target = Path(target_path)
            
            if not source.exists():
                print(f"❌ Fichier source introuvable: {source}")
                return False
            
            # Créer le dossier parent si nécessaire
            target.parent.mkdir(parents=True, exist_ok=True)
            
            # Extraire les paramètres skin
            pitch = skin_params.get("pitch", 0)
            speed = skin_params.get("speed", 0)
            highpass = skin_params.get("highpass", 0)  # ← NOUVEAU
            lowpass = skin_params.get("lowpass", 0)    # ← NOUVEAU
            metallic = skin_params.get("metallic", 0)
            distortion = skin_params.get("distortion", 0)
            reverb = skin_params.get("reverb", 0)
            echo = skin_params.get("echo", 0)
            vocoder = skin_params.get("vocoder", 0)
            hash = skin_params.get("hash", 0)
            dry_wet = skin_params.get("dry_wet", 100)

            if self._get_config_value("debug_sw", False): print(f"🎛️ Effets skin: pitch={pitch}, speed={speed}, highpass={highpass}, lowpass={lowpass}, metallic={metallic}, dry_wet={dry_wet}, distortion={distortion}, reverb={reverb}, echo={echo}, vocoder={vocoder}, hash={hash}")

            # Construire la chaîne de filtres FFmpeg
            filters = []
            
            # === PITCH SHIFTING ===
            if pitch != 0:
                # Pitch en demi-tons (-12 à +12)
                pitch_ratio = 2 ** (pitch / 12.0)  # ← OK, conversion correcte
                filters.append(f"asetrate=24000*{pitch_ratio:.3f},aresample=24000")
                print(f"   🎵 Pitch: {pitch} demi-tons (ratio: {pitch_ratio:.3f})")
            
            # === SPEED CHANGE ===
            if speed != 0:
                # Convertir % en ratio (speed=50 = 1.5x plus rapide)
                speed_ratio = 1.0 + (speed / 100.0)
                if speed_ratio > 0.1:  # Éviter les valeurs trop extrêmes
                    filters.append(f"atempo={speed_ratio:.3f}")
                    print(f"   ⚡ Vitesse: {speed}% (ratio: {speed_ratio:.3f})")
            
            # === FILTRE PASSE-HAUT ===
            if highpass > 0:
                highpass_freq = 200 + (highpass * 22)  # 200Hz à 2400Hz
                filters.append(f"highpass=f={highpass_freq}")
                print(f"   📈 Passe-haut: {highpass}% (coupure: {highpass_freq}Hz)")
                
            # === EFFET METALLIC (CORRIGER) ===
            if metallic > 0:
                filters.append(f"equalizer=f=3000:t=q:w=1:g={metallic}")
                print(f"   🤖 Metallic: {metallic}% (gain: {metallic}dB)")

            # === FILTRE PASSE-BAS ===
            if lowpass > 0:
                lowpass_freq = 4000 - (lowpass * 35)   # 4000Hz à 500Hz
                if lowpass_freq < 300: lowpass_freq = 300  # Plancher plus réaliste
                filters.append(f"lowpass=f={lowpass_freq}")
                print(f"   📉 Passe-bas: {lowpass}% (coupure: {lowpass_freq}Hz)")
            
            # === DISTORTION (CORRIGER) ===
            if distortion > 0:
                # Utiliser un filtre supporté : amplification + compression
                drive_db = 1 + (distortion * 0.2)  # 1dB à 21dB
                # Utiliser volume + acompressor au lieu d'overdrive
                filters.append(f"volume={drive_db:.1f}dB")
                if distortion > 30:  # Compression forte pour distortion élevée
                    filters.append("acompressor=threshold=-10dB:ratio=4:attack=5:release=50")
                print(f"   🎸 Distortion: {distortion}% (gain: {drive_db:.1f}dB)")
            
            # === VOCODER (NOUVEAU) ===
            if vocoder > 0:
                # Simulation vocoder avec modulation d'amplitude à basse fréquence
                vocoder_freq = 2 + (vocoder * 0.1)  # 2Hz à 12Hz
                vocoder_depth = 0.3 + (vocoder * 0.007)  # 0.3 à 1.0
                filters.append(f"tremolo=f={vocoder_freq:.1f}:d={vocoder_depth:.2f}")
                print(f"   🎛️ Vocoder: {vocoder}% (freq: {vocoder_freq:.1f}Hz, depth: {vocoder_depth:.2f})")
            
            # === HASH / DEGRADATION DIGITALE (NOUVEAU) ===
            if hash > 0:
                # Simulation dégradation : downsampling + bitcrush via decimator
                decimation = 1 + int(hash * 0.08)  # 1x à 8x decimation
                if decimation > 1:
                    filters.append(f"asamplefmt=s16:sample_rate=24000")  # Force 16-bit
                    # Simuler bitcrush avec quantization
                    filters.append(f"volume=0.{100-hash}")  # Réduction dynamique
                    print(f"   📱 Hash: {hash}% (degradation: {decimation}x)")
            
            # === ECHO (AJUSTER AMPLITUDES) ===
            if echo > 0:
                # Amplitudes plus fines pour l'écho
                echo_delay = 50 + (echo * 5)         # 50ms à 550ms (plus court)
                echo_gain = 0.05 + (echo * 0.004)   # 0.05 à 0.45 (plus subtil)
                filters.append(f"aecho=0.8:0.88:{int(echo_delay)}:{echo_gain:.3f}")
                print(f"   📢 Echo: {echo}% (delay: {echo_delay:.0f}ms, gain: {echo_gain:.3f})")
            
            # === REVERB (AJUSTER AMPLITUDES) ===
            if reverb > 0:
                # Amplitudes plus fines pour la réverbération
                reverb_time = 0.05 + (reverb * 0.015)   # 0.05s à 1.55s (plus court)
                reverb_decay = 0.1 + (reverb * 0.004)   # 0.1 à 0.5 (plus subtil)
                filters.append(f"aecho=0.8:0.9:800|1200:{reverb_decay:.3f}|{reverb_decay*0.6:.3f}")
                print(f"   🏛️ Reverb: {reverb}% (time: {reverb_time:.2f}s, decay: {reverb_decay:.3f})")
            
            # === DRY/WET MIX (CORRIGÉ) ===
            if filters and dry_wet < 100:
                wet_ratio = (100 - dry_wet) / 100.0  # 0.0 à 1.0
                dry_ratio = dry_wet / 100.0          # 1.0 à 0.0
                
                print(f"   🌊 Dry/Wet: {dry_wet}% (wet: {wet_ratio:.2f}, dry: {dry_ratio:.2f})")
                
                # ✅ SOLUTION : Mixer les 2 signaux avec amix
                if wet_ratio < 1.0:  # Si on veut du mix
                    # Construire le filtergraph complexe pour mixer dry + wet
                    filter_chain = f"[0:a]volume={dry_ratio}[dry];[0:a]{','.join(filters)}[wet];[dry][wet]amix=inputs=2:weights={dry_ratio} {wet_ratio}[out]"
                    
                    # Commande FFmpeg modifiée pour le mix
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(source),
                        "-filter_complex", filter_chain,
                        "-map", "[out]",
                        "-acodec", "pcm_s16le",
                        "-ar", "24000",
                        "-ac", "1",
                        str(target)
                    ]
                    
                    print(f"🔧 FFmpeg dry/wet mix: dry={dry_ratio:.2f}, wet={wet_ratio:.2f}")
                    
                else:
                    # 100% wet = effets normaux (comme avant)
                    filter_chain = ",".join(filters)
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(source),
                        "-af", filter_chain,
                        "-acodec", "pcm_s16le",
                        "-ar", "24000",
                        "-ac", "1",
                        str(target)
                    ]
                    
                    print(f"🔧 FFmpeg 100% wet: {filter_chain}")

            elif not filters or dry_wet == 100:
                # 100% dry = copie simple (aucun effet)
                print("   ℹ️ Dry/Wet 100% → Copie simple sans effet")
                import shutil
                shutil.copy2(source, target)
                return True

            else:
                # 100% wet avec effets
                filter_chain = ",".join(filters)
                cmd = [
                    "ffmpeg", "-y", 
                    "-i", str(source),
                    "-af", filter_chain,
                    "-acodec", "pcm_s16le",
                    "-ar", "24000",
                    "-ac", "1",
                    str(target)
                ]
                
                print(f"🔧 FFmpeg 100% wet: {filter_chain}")

            # Exécuter la commande (déplacer cette partie après le if/else)
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    file_size = target.stat().st_size if target.exists() else 0
                    duration = file_size / (24000 * 2) if file_size > 0 else 0
                    print(f"✅ Skin FFmpeg généré: {target.name} ({duration:.2f}s, {file_size} bytes)")
                    return True
                else:
                    print(f"❌ FFmpeg skin error: {result.stderr[:200]}...")
                    return False
                    
            except subprocess.TimeoutExpired:
                print("❌ Timeout FFmpeg skin (30s)")
                return False
            except Exception as e:
                print(f"❌ Erreur subprocess FFmpeg: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur apply_skin_effects: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def apply_environment_effect(self, source_path: str, target_path: str, effect: str) -> bool:
        """
        Applique un effet environment (ship, city, helmet) depuis skin.wav
        
        Args:
            source_path: Chemin vers skin.wav
            target_path: Chemin de sortie (ex: ship.wav)
            effect: Type d'effet ("ship", "city", "helmet")
        """
        try:
            source = Path(source_path)
            target = Path(target_path)
            
            print(f"🌍 Application environment {effect}: {source.name} → {target.name}")
            
            if not source.exists():
                print(f"❌ Fichier source introuvable: {source}")
                return False
            
            # Utiliser le FX Generator existant
            from core.sound.fx_generator import fx_generator
            
            # ✅ FIX: Appel simplifié sans Priority
            success = fx_generator.create_async(str(source), effect, force_remake=True)
            
            if not success:
                print(f"❌ Échec programmation effet {effect}")
                return False
            
            # ✅ ATTENDRE que le fichier soit généré (polling simple)
            import time
            max_wait = 15  # 15 secondes max
            wait_time = 0

            if self._get_config_value("debug_sw", False): print(f"⏳ Attente génération {effect} (max {max_wait}s)...")
            while not target.exists() and wait_time < max_wait:
                time.sleep(0.5)
                wait_time += 0.5
            
            if target.exists() and target.stat().st_size > 0:
                print(f"✅ Environment {effect} généré: {target.name}")
                return True
            else:
                print(f"❌ Timeout génération {effect} après {max_wait}s")
                return False
            
        except Exception as e:
            print(f"❌ Erreur apply_environment_effect: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_config_value(self, key: str, default: int) -> int:
        """
        Récupère la valeur d'un paramètre de configuration avec une valeur par défaut.
        
        Args:
            key: Clé du paramètre dans la configuration
            default: Valeur par défaut si le paramètre n'est pas trouvé
        
        Returns:
            La valeur entière du paramètre de configuration
        """
        # Utiliser ConfigManager pour accéder à la configuration
        value = self.config_manager.get(key, default)
        
        # S'assurer que la valeur est bien un entier
        if isinstance(value, int):
            return value
        else:
            return default

    def apply_skin_effects_with_config(self, source_path: str, target_path: str) -> bool:
        """Applique les effets skin en utilisant les valeurs de configuration"""
        try:
            # Extraire les paramètres skin depuis la configuration
            skin_params = {
                "pitch": self._get_config_value("effects.skin.pitch", 0),
                "speed": self._get_config_value("effects.skin.speed", 0),
                "highpass": self._get_config_value("effects.skin.highpass", 0),
                "metallic": self._get_config_value("effects.skin.metallic", 0),
                "lowpass": self._get_config_value("effects.skin.lowpass", 0),
                "distortion": self._get_config_value("effects.skin.distortion", 0),
                "reverb": self._get_config_value("effects.skin.reverb", 0),
                "echo": self._get_config_value("effects.skin.echo", 0),
                "vocoder": self._get_config_value("effects.skin.vocoder", 0),
                "hash": self._get_config_value("effects.skin.hash", 0),
                "dry_wet": self._get_config_value("effects.skin.dry_wet", 100)
            }
            
            print(f"🎛️ Paramètres skin extraits de la config: {skin_params}")
            
            # Appliquer les effets skin avec les paramètres extraits
            return self.apply_skin_effects(source_path, target_path, skin_params)
        
        except Exception as e:
            print(f"❌ Erreur apply_skin_effects_with_config: {e}")
            import traceback
            traceback.print_exc()
            return False

    def apply_environment_effect_with_config(self, source_path: str, target_path: str) -> bool:
        """
        Applique un effet environment (ship, city, helmet) en utilisant les valeurs de configuration
        
        Args:
            source_path: Chemin vers skin.wav
            target_path: Chemin de sortie (ex: ship.wav)
        """
        try:
            # Déterminer le type d'effet depuis la configuration
            effect = self.config_manager.get("effects.environment.type", "ship")
            
            print(f"🌍 Application environment {effect} avec config: {source_path} → {target_path}")
            
            # Appliquer l'effet environment avec le type déterminé
            return self.apply_environment_effect(source_path, target_path, effect)
        
        except Exception as e:
            print(f"❌ Erreur apply_environment_effect_with_config: {e}")
            import traceback
            traceback.print_exc()
            return False
