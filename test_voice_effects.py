"""
🎵 Test Voice Effects - Laboratoire d'effets vocaux pour Orion
===============================================================

Script indépendant pour tester les effets de voix avant intégration.
Prend un fichier TTS et applique différents effets (tone, speed, helium, etc.)

Usage:
    python test_voice_effects.py
    
Modifiez les variables TEST_* en haut du script pour vos tests.
"""

import numpy as np
import soundfile as sf
import sounddevice as sd
import subprocess
import tempfile
import time
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

# =============================================================================
# 🎛️ CONFIGURATION DE TEST - MODIFIEZ ICI
# =============================================================================

# Fichier audio source (sortie TTS à traiter)
TEST_AUDIO_FILE = "./sound/output_sound/edgetts/frcharianeneura/start_orion/r0_p-10_Bonjour,_je_suis_votre_copilote_Orion._Système_initialisé.wav"

# 🎚️ PARAMÈTRES D'EFFETS SKIN (0-100 ou valeurs spécifiques)
EFFECTS_CONFIG = {
    # Effets de base
    "tone": 0,           # -50 à +50 (changement de pitch en demi-tons)
    "speed": 0,          # -50 à +50 (% de changement de vitesse)
    "helium": 0,         # 0-100 (effet hélium, monte dans les aigus)
    
    # Effets de personnalité
    "metallic": 0,       # 0-100 (résonance métallique)
    "robotic": 0,        # 0-100 (vocoder-like)
    "distortion": 0,     # 0-100 (saturation)
    "vocoder": 0,        # 0-100 (synthétiseur vocal)
    "hash": 0,           # 0-100 (dégradation digitale)
    
    # Effets spatiaux
    "reverb": 0,         # 0-100 (réverbération)
    "echo": 0,           # 0-100 (écho/delay)
    
    # Mix final
    "dry_wet": 100,      # 0-100 (% d'effet vs son original)
}

# 🌍 CONFIGURATION ENVIRONNEMENTS - PARAMÈTRES FFmpeg
ENVIRONMENT_CONFIG = {
    "type": "helmet",      # "none", "ship", "city", "helmet"
    "intensity": 100,    # 0-100 (multiplicateur global pour tous les effets)
    "use_ffmpeg": True,  # True = FFmpeg (qualité pro), False = numpy (test rapide)
    
    # === VAISSEAU SPATIAL ===
    "ship": {
        "echo_gain": 88,         # 0-100 (gain de l'écho 0.6-1.0)
        "echo_delay": 45,        # 0-100 (délai écho 30-60ms)
        "compressor": 60,        # 0-100 (niveau compresseur 2:1-8:1)
        "metallic_boost": 30,    # 0-100 (boost EQ métallique 0-8dB)
        "volume_pre": 50,        # 0-100 (volume initial)
        "volume_post": 150,      # 0-200 (volume final)
    },
    
    # === VILLE/MONTRE ===
    "city": {
        "highpass": 300,         # Hz (fréquence de coupure basse)
        "lowpass": 3000,         # Hz (fréquence de coupure haute)
        "volume_boost": 8,       # dB (amplification petit HP)
        "echo_radio": 0,         # 0-100 (écho radio optionnel)
    },
    
    # === CASQUE SPATIAL ===
    "helmet": {
        "delay": 25,             # 0-100 (délai stéréo 200-500ms)
        "lowpass_cutoff": 70,    # 0-100 (étouffement 4000-1600Hz)
        "highpass": 300,         # Hz (coupure graves)
        "compression": 50,       # 0-100 (niveau compand)
        "eq_cut": 20,            # 0-100 (coupure EQ 1kHz)
    }
}

# 🔊 PARAMÈTRES AUDIO
PLAYBACK_VOLUME = 0.8    # Volume de lecture (0.0-1.0)
AUTO_PLAY = True         # Jouer automatiquement après traitement
SAVE_OUTPUT = True       # Sauvegarder le résultat traité
OUTPUT_FILE = "./test_output_with_effects.wav"

# =============================================================================
# 🎵 MOTEUR D'EFFETS VOCAUX HYBRIDE (Numpy + FFmpeg)
# =============================================================================

class VoiceEffectsProcessor:
    """Processeur d'effets vocaux hybride (skin numpy + environment FFmpeg)"""
    
    def __init__(self):
        self.sample_rate = 44100
        self.processed_data = None
        self.processing_time = 0.0
        self.temp_dir = Path(tempfile.gettempdir()) / "orion_effects"
        self.temp_dir.mkdir(exist_ok=True)
    
    def load_audio(self, file_path: str) -> bool:
        """Charge un fichier audio"""
        try:
            self.audio_data, self.sample_rate = sf.read(file_path, dtype='float32')
            if self.audio_data.ndim == 1:
                self.audio_data = self.audio_data.reshape(-1, 1)  # Mono → stéréo
            print(f"✅ Audio chargé: {file_path}")
            print(f"   📊 Format: {self.audio_data.shape[1]} canaux, {self.sample_rate}Hz")
            print(f"   ⏱️  Durée: {len(self.audio_data) / self.sample_rate:.2f}s")
            return True
        except Exception as e:
            print(f"❌ Erreur de chargement: {e}")
            return False
    
    def process_effects(self, effects: Dict[str, float], environment: Dict[str, Any] = None) -> np.ndarray:
        """Applique la chaîne d'effets : skin (numpy) + environment (FFmpeg)"""
        if self.audio_data is None:
            raise ValueError("Aucun audio chargé")
        
        start_time = time.time()
        processed = self.audio_data.copy()
        
        print("🎛️ Application des effets:")
        
        # === COUCHE 1 : EFFETS SKIN (Numpy) ===
        processed = self._apply_skin_effects(processed, effects)
        
        # === COUCHE 2 : ENVIRONNEMENT (FFmpeg ou Numpy) ===
        if environment and environment.get("type") != "none":
            processed = self._apply_environment_effects(processed, environment)
        
        # === MIX DRY/WET FINAL ===
        dry_wet = effects.get("dry_wet", 100) / 100.0
        if dry_wet < 1.0:
            processed = self.audio_data * (1 - dry_wet) + processed * dry_wet
            print(f"   🎚️ Mix: {dry_wet*100:.0f}% effet")
        
        # Normalisation pour éviter clipping
        processed = self._normalize(processed)
        
        self.processing_time = time.time() - start_time
        self.processed_data = processed
        
        print(f"✅ Traitement terminé en {self.processing_time:.3f}s")
        return processed
    
    def _apply_skin_effects(self, data: np.ndarray, effects: Dict[str, float]) -> np.ndarray:
        """Applique les effets de skin (personnalité vocale) avec numpy"""
        processed = data.copy()
        
        # === EFFETS DE BASE ===
        if effects.get("tone", 0) != 0:
            processed = self._apply_pitch_shift(processed, effects["tone"])
            print(f"   🎵 Tone: {effects['tone']:+.0f} demi-tons")
        
        if effects.get("speed", 0) != 0:
            processed = self._apply_speed_change(processed, effects["speed"])
            print(f"   🏃 Speed: {effects['speed']:+.0f}%")
        
        if effects.get("helium", 0) > 0:
            processed = self._apply_helium(processed, effects["helium"])
            print(f"   🎈 Helium: {effects['helium']:.0f}%")
        
        # === EFFETS DE PERSONNALITÉ ===
        if effects.get("metallic", 0) > 0:
            processed = self._apply_metallic(processed, effects["metallic"])
            print(f"   🤖 Metallic: {effects['metallic']:.0f}%")
        
        if effects.get("robotic", 0) > 0:
            processed = self._apply_robotic(processed, effects["robotic"])
            print(f"   🦾 Robotic: {effects['robotic']:.0f}%")
        
        if effects.get("distortion", 0) > 0:
            processed = self._apply_distortion(processed, effects["distortion"])
            print(f"   ⚡ Distortion: {effects['distortion']:.0f}%")
        
        if effects.get("vocoder", 0) > 0:
            processed = self._apply_vocoder(processed, effects["vocoder"])
            print(f"   🎹 Vocoder: {effects['vocoder']:.0f}%")
        
        if effects.get("hash", 0) > 0:
            processed = self._apply_hash(processed, effects["hash"])
            print(f"   📻 Hash: {effects['hash']:.0f}%")
        
        # === EFFETS SPATIAUX ===
        if effects.get("reverb", 0) > 0:
            processed = self._apply_reverb(processed, effects["reverb"])
            print(f"   🏛️ Reverb: {effects['reverb']:.0f}%")
        
        if effects.get("echo", 0) > 0:
            processed = self._apply_echo(processed, effects["echo"])
            print(f"   🔊 Echo: {effects['echo']:.0f}%")
        
        return processed
    
    def _apply_environment_effects(self, data: np.ndarray, environment: Dict[str, Any]) -> np.ndarray:
        """Applique les effets d'environnement (FFmpeg ou numpy)"""
        env_type = environment.get("type", "none")
        env_intensity = environment.get("intensity", 100) / 100.0
        use_ffmpeg = environment.get("use_ffmpeg", True)
        
        if env_type == "none" or env_intensity == 0:
            return data
        
        if use_ffmpeg:
            return self._apply_environment_ffmpeg(data, env_type, environment, env_intensity)
        else:
            return self._apply_environment_numpy(data, env_type, environment, env_intensity)
    
    def _apply_environment_ffmpeg(self, data: np.ndarray, env_type: str, environment: Dict[str, Any], global_intensity: float) -> np.ndarray:
        """Applique les effets d'environnement avec FFmpeg (qualité professionnelle)"""
        
        # Créer fichier temporaire d'entrée
        temp_input = self.temp_dir / f"temp_input_{int(time.time()*1000)}.wav"
        temp_output = self.temp_dir / f"temp_output_{int(time.time()*1000)}.wav"
        
        try:
            # Sauvegarder l'audio temporaire
            sf.write(temp_input, data, self.sample_rate)
            
            # Construire la chaîne de filtres FFmpeg
            filters = self._build_ffmpeg_filters(env_type, environment, global_intensity)
            
            if not filters:
                return data
            
            # Exécuter FFmpeg
            success = self._execute_ffmpeg(str(temp_input), str(temp_output), filters)
            
            if success and temp_output.exists():
                # Recharger l'audio traité
                processed_data, _ = sf.read(temp_output, dtype='float32')
                if processed_data.ndim == 1:
                    processed_data = processed_data.reshape(-1, 1)
                
                print(f"   🌍 Environment FFmpeg: {env_type.upper()}")
                return processed_data
            else:
                print(f"   ❌ FFmpeg failed, using numpy fallback")
                return self._apply_environment_numpy(data, env_type, environment, global_intensity)
                
        except Exception as e:
            print(f"   ❌ FFmpeg error: {e}, using numpy fallback")
            return self._apply_environment_numpy(data, env_type, environment, global_intensity)
        
        finally:
            # Nettoyer les fichiers temporaires
            try:
                if temp_input.exists():
                    temp_input.unlink()
                if temp_output.exists():
                    temp_output.unlink()
            except:
                pass
    
    def _build_ffmpeg_filters(self, env_type: str, environment: Dict[str, Any], global_intensity: float) -> List[str]:
        """Construit la chaîne de filtres FFmpeg selon l'environnement"""
        
        filters = []
        params = environment.get(env_type, {})
        
        if env_type == "ship":
            # Volume initial
            volume_pre = params.get("volume_pre", 50) / 100.0 * global_intensity
            filters.append(f"volume={volume_pre:.2f}")
            
            # Echo vaisseau
            echo_gain = params.get("echo_gain", 88) / 100.0 * global_intensity
            echo_delay = params.get("echo_delay", 45)
            
            if echo_gain > 0:
                in_gain = 0.6 + echo_gain * 0.4    # 0.6-1.0
                out_gain = 0.7 + echo_gain * 0.3    # 0.7-1.0
                delay_ms = 30 + (echo_delay / 100.0) * 30  # 30-60ms
                decay = 0.2 + echo_gain * 0.3       # 0.2-0.5
                filters.append(f"aecho={in_gain:.2f}:{out_gain:.2f}:{delay_ms:.0f}:{decay:.2f}")
            
            # Compresseur intercom
            compressor_level = params.get("compressor", 60) / 100.0 * global_intensity
            if compressor_level > 0:
                threshold = -12 - compressor_level * 12  # -12 à -24 dB
                ratio = 2 + compressor_level * 6         # 2:1 à 8:1
                filters.append(f"acompressor=attack=20:release=1000:threshold={threshold:.0f}dB:ratio={ratio:.1f}")
            
            # Volume final
            volume_post = params.get("volume_post", 150) / 100.0
            filters.append(f"volume={volume_post:.2f}")
            
            # EQ métallique
            metallic_boost = params.get("metallic_boost", 30) / 100.0 * global_intensity
            if metallic_boost > 0:
                freq = 800 + metallic_boost * 400   # 800-1200 Hz
                gain = metallic_boost * 8           # 0-8 dB
                filters.append(f"equalizer=f={freq:.0f}:width_type=h:width=500:g={gain:.1f}")
        
        elif env_type == "city":
            # Filtre passe-haut
            highpass_freq = params.get("highpass", 300)
            if highpass_freq > 0:
                filters.append(f"highpass=f={highpass_freq}")
            
            # Filtre passe-bas
            lowpass_freq = params.get("lowpass", 3000)
            if lowpass_freq > 0:
                filters.append(f"lowpass=f={lowpass_freq}")
            
            # Echo radio optionnel
            echo_radio = params.get("echo_radio", 0) / 100.0 * global_intensity
            if echo_radio > 0:
                in_gain = 0.8
                out_gain = 0.9
                delay_ms = 50
                decay = 0.3 * echo_radio
                filters.append(f"aecho={in_gain}:{out_gain}:{delay_ms}:{decay:.2f}")
            
            # Volume boost
            volume_boost = params.get("volume_boost", 8) * global_intensity
            if volume_boost > 0:
                filters.append(f"volume={volume_boost:.1f}dB")
        
        elif env_type == "helmet":
            # Delay stéréo
            delay_level = params.get("delay", 25) / 100.0 * global_intensity
            if delay_level > 0:
                delay_ms = 200 + delay_level * 300  # 200-500ms
                filters.append(f"adelay={delay_ms:.0f}|{delay_ms:.0f}")
            
            # Lowpass pour étouffement
            lowpass_level = params.get("lowpass_cutoff", 70) / 100.0 * global_intensity
            base_cutoff = 4000
            cutoff = base_cutoff * (1 - lowpass_level * 0.6)  # 4000-1600 Hz
            filters.append(f"lowpass=f={cutoff:.0f}")
            
            # Highpass pour netteté
            highpass_freq = params.get("highpass", 300)
            if highpass_freq > 0:
                filters.append(f"highpass=f={highpass_freq}")
            
            # EQ coupure (bocal effect)
            eq_cut = params.get("eq_cut", 20) / 100.0 * global_intensity
            if eq_cut > 0:
                gain = -eq_cut * 10  # 0 à -10 dB
                filters.append(f"equalizer=f=1000:width_type=h:width=200:g={gain:.1f}")
            
            # Compression casque
            compression_level = params.get("compression", 50) / 100.0 * global_intensity
            if compression_level > 0:
                filters.append("compand=attacks=0.3:decays=1:soft-knee=6:points=-70/-70|-60/-20|0/-20:gain=0:volume=0.2:delay=0.3")
        
        return filters
    
    def _execute_ffmpeg(self, input_path: str, output_path: str, filters: List[str]) -> bool:
        """Exécute FFmpeg avec la chaîne de filtres"""
        try:
            filter_chain = ",".join(filters)
            
            cmd = [
                "ffmpeg", "-y",           # Overwrite output
                "-i", input_path,         # Input file
                "-af", filter_chain,      # Audio filters
                "-c:a", "pcm_s16le",      # Audio codec (WAV)
                "-ar", str(self.sample_rate),  # Sample rate
                output_path               # Output file
            ]
            
            # Exécution silencieuse
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            if result.returncode == 0:
                for filter_name in filters:
                    print(f"      🎛️ {filter_name}")
                return True
            else:
                print(f"      ❌ FFmpeg stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("      ❌ FFmpeg timeout (>30s)")
            return False
        except FileNotFoundError:
            print("      ❌ FFmpeg non trouvé - installez FFmpeg")
            return False
        except Exception as e:
            print(f"      ❌ FFmpeg error: {e}")
            return False
    
    def _apply_environment_numpy(self, data: np.ndarray, env_type: str, environment: Dict[str, Any], global_intensity: float) -> np.ndarray:
        """Fallback numpy pour les environnements (si FFmpeg échoue)"""
        params = environment.get(env_type, {})
        
        print(f"   🌍 Environment Numpy: {env_type.upper()}")
        
        if env_type == "city":
            # Filtre passe-bande simple
            return self._apply_bandpass_filter(data, params.get("highpass", 300), params.get("lowpass", 3000))
        
        elif env_type == "helmet":
            # Filtre passe-bas simple
            cutoff = 4000 * (1 - (params.get("lowpass_cutoff", 70) / 100.0 * global_intensity) * 0.6)
            return self._apply_lowpass_filter(data, cutoff)
        
        else:  # ship ou autres
            # Echo simple
            return self._apply_echo(data, 40)
    
    # =========================================================================
    # 🔧 IMPLÉMENTATIONS DES EFFETS SKIN (Numpy)
    # =========================================================================
    
    def _apply_pitch_shift(self, data: np.ndarray, semitones: float) -> np.ndarray:
        """Change la hauteur sans affecter la vitesse (pitch shift)"""
        if semitones == 0:
            return data
        
        factor = 2 ** (semitones / 12.0)
        new_length = int(len(data) / factor)
        indices = np.linspace(0, len(data) - 1, new_length)
        resampled = np.zeros((new_length, data.shape[1]), dtype=data.dtype)
        
        for ch in range(data.shape[1]):
            resampled[:, ch] = np.interp(indices, np.arange(len(data)), data[:, ch])
        
        original_length = len(data)
        stretch_indices = np.linspace(0, len(resampled) - 1, original_length)
        stretched = np.zeros_like(data)
        
        for ch in range(data.shape[1]):
            stretched[:, ch] = np.interp(stretch_indices, np.arange(len(resampled)), resampled[:, ch])
        
        return stretched
    
    def _apply_speed_change(self, data: np.ndarray, speed_percent: float) -> np.ndarray:
        """Change la vitesse de lecture (affecte pitch et tempo)"""
        if speed_percent == 0:
            return data
        
        factor = 1.0 + (speed_percent / 100.0)
        new_length = int(len(data) / factor)
        indices = np.linspace(0, len(data) - 1, new_length)
        result = np.zeros((new_length, data.shape[1]), dtype=data.dtype)
        
        for ch in range(data.shape[1]):
            result[:, ch] = np.interp(indices, np.arange(len(data)), data[:, ch])
        
        return result
    
    def _apply_helium(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Effet hélium (monte dans les aigus)"""
        if intensity == 0:
            return data
        shift_semitones = (intensity / 100.0) * 12
        return self._apply_pitch_shift(data, shift_semitones)
    
    def _apply_metallic(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Effet métallique (ring modulation)"""
        if intensity == 0:
            return data
        
        mod_freq = 800 + (intensity * 10)
        t = np.linspace(0, len(data) / self.sample_rate, len(data))
        modulator = np.sin(2 * np.pi * mod_freq * t)
        
        result = data.copy()
        for ch in range(data.shape[1]):
            result[:, ch] *= (1 + (intensity / 100.0) * modulator * 0.5)
        
        return result
    
    def _apply_distortion(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Distortion/saturation agressive"""
        if intensity == 0:
            return data
        
        result = data.copy()
        drive = 1.0 + (intensity / 100.0) * 19.0
        
        for ch in range(data.shape[1]):
            driven = result[:, ch] * drive
            driven = np.where(driven > 1.0, 1.0 - (driven - 1.0) * 0.3, driven)
            driven = np.where(driven < -1.0, -1.0 - (driven + 1.0) * 0.3, driven)
            driven = np.tanh(driven * 2) * 0.8
            result[:, ch] = driven
        
        return result * 0.6
    
    def _apply_robotic(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Effet robotique (vocoder simple + harmoniques artificielles)"""
        if intensity == 0:
            return data
        
        result = data.copy()
        bits = max(2, int(8 * (1 - intensity / 100.0)))
        levels = 2 ** bits
        
        for ch in range(data.shape[1]):
            quantized = np.round(result[:, ch] * levels) / levels
            
            t = np.linspace(0, len(data) / self.sample_rate, len(data))
            square1 = np.sign(np.sin(2 * np.pi * 150 * t))
            square2 = np.sign(np.sin(2 * np.pi * 300 * t))
            robot_mod = (square1 + square2 * 0.5) / 1.5
            
            robot_voice = quantized * (1 + robot_mod * (intensity / 100.0) * 0.3)
            mix_ratio = intensity / 100.0
            result[:, ch] = quantized * (1 - mix_ratio) + robot_voice * mix_ratio
        
        return result
    
    def _apply_vocoder(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Effet vocoder (synthétiseur vocal avec porteuse)"""
        if intensity == 0:
            return data
        
        result = data.copy()
        
        for ch in range(data.shape[1]):
            t = np.linspace(0, len(data) / self.sample_rate, len(data))
            carrier_freq = 220
            sawtooth = 2 * (t * carrier_freq % 1) - 1
            sine = np.sin(2 * np.pi * carrier_freq * t)
            carrier = (sawtooth + sine) / 2
            
            envelope = np.abs(data[:, ch])
            window_size = max(1, int(self.sample_rate * 0.01))
            if window_size < len(envelope):
                envelope = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')
            
            vocoded = carrier * envelope * (intensity / 100.0) * 2
            mix_ratio = intensity / 100.0
            result[:, ch] = data[:, ch] * (1 - mix_ratio) + vocoded * mix_ratio
        
        return result
    
    def _apply_hash(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Effet hash/digital (bit crushing + sample rate reduction)"""
        if intensity == 0:
            return data
        
        result = data.copy()
        
        for ch in range(data.shape[1]):
            bits = max(1, int(16 * (1 - intensity / 100.0)))
            levels = 2 ** bits
            crushed = np.round(result[:, ch] * levels) / levels
            
            downsample_factor = max(1, int(1 + (intensity / 100.0) * 15))
            downsampled = crushed[::downsample_factor]
            upsampled = np.repeat(downsampled, downsample_factor)
            
            if len(upsampled) > len(crushed):
                upsampled = upsampled[:len(crushed)]
            elif len(upsampled) < len(crushed):
                padding = np.full(len(crushed) - len(upsampled), upsampled[-1] if len(upsampled) > 0 else 0)
                upsampled = np.concatenate([upsampled, padding])
            
            noise_intensity = intensity / 100.0 * 0.1
            digital_noise = np.random.uniform(-noise_intensity, noise_intensity, len(upsampled))
            noisy = upsampled + digital_noise
            final_crushed = np.round(noisy * levels) / levels
            
            result[:, ch] = final_crushed
        
        return result
    
    def _apply_reverb(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Réverbération simple"""
        if intensity == 0:
            return data
        
        delays = [0.03, 0.05, 0.07, 0.09, 0.11]
        decay = 0.6 * (intensity / 100.0)
        result = data.copy()
        
        for delay in delays:
            delay_samples = int(delay * self.sample_rate)
            if delay_samples < len(data):
                for ch in range(data.shape[1]):
                    delayed = np.zeros_like(data[:, ch])
                    delayed[delay_samples:] = data[:-delay_samples, ch] * decay
                    result[:, ch] += delayed
        
        return result
    
    def _apply_echo(self, data: np.ndarray, intensity: float) -> np.ndarray:
        """Écho/delay"""
        if intensity == 0:
            return data
        
        delay_sec = 0.2 + (intensity / 100.0) * 0.3
        delay_samples = int(delay_sec * self.sample_rate)
        feedback = 0.4 * (intensity / 100.0)
        
        if delay_samples >= len(data):
            return data
        
        result = data.copy()
        for ch in range(data.shape[1]):
            echo = np.zeros_like(data[:, ch])
            echo[delay_samples:] = data[:-delay_samples, ch] * feedback
            result[:, ch] += echo
        
        return result
    
    def _apply_bandpass_filter(self, data: np.ndarray, low_freq: float, high_freq: float) -> np.ndarray:
        """Filtre passe-bande simple (numpy)"""
        result = data.copy()
        
        for ch in range(data.shape[1]):
            fft_data = np.fft.rfft(result[:, ch])
            freqs = np.fft.rfftfreq(len(result[:, ch]), 1/self.sample_rate)
            
            mask = np.ones_like(freqs)
            low_mask = freqs < low_freq
            high_mask = freqs > high_freq
            
            if np.any(low_mask):
                mask[low_mask] *= np.maximum(0.1, freqs[low_mask] / low_freq)
            if np.any(high_mask):
                mask[high_mask] *= np.maximum(0.1, high_freq / freqs[high_mask])
            
            result[:, ch] = np.fft.irfft(fft_data * mask, len(result[:, ch]))
        
        return result
    
    def _apply_lowpass_filter(self, data: np.ndarray, cutoff_freq: float) -> np.ndarray:
        """Filtre passe-bas simple (numpy)"""
        result = data.copy()
        
        for ch in range(data.shape[1]):
            fft_data = np.fft.rfft(result[:, ch])
            freqs = np.fft.rfftfreq(len(result[:, ch]), 1/self.sample_rate)
            
            mask = np.ones_like(freqs)
            high_mask = freqs > cutoff_freq
            if np.any(high_mask):
                rolloff = np.exp(-(freqs[high_mask] - cutoff_freq) / (cutoff_freq * 0.4))
                mask[high_mask] = rolloff * 0.2
            
            result[:, ch] = np.fft.irfft(fft_data * mask, len(result[:, ch]))
        
        return result
    
    def _normalize(self, data: np.ndarray) -> np.ndarray:
        """Normalise l'audio pour éviter le clipping"""
        max_val = np.max(np.abs(data))
        if max_val > 0.95:
            return data * (0.95 / max_val)
        return data
    
    def save_processed(self, output_path: str) -> bool:
        """Sauvegarde l'audio traité"""
        if self.processed_data is None:
            print("❌ Aucun audio traité à sauvegarder")
            return False
        
        try:
            sf.write(output_path, self.processed_data, self.sample_rate)
            print(f"💾 Audio sauvegardé: {output_path}")
            return True
        except Exception as e:
            print(f"❌ Erreur de sauvegarde: {e}")
            return False
    
    def play_audio(self, data: Optional[np.ndarray] = None, volume: float = 1.0) -> None:
        """Joue l'audio avec sounddevice"""
        audio_to_play = data if data is not None else self.processed_data
        
        if audio_to_play is None:
            print("❌ Aucun audio à jouer")
            return
        
        try:
            print(f"🔊 Lecture... (Volume: {volume:.0%})")
            sd.play(audio_to_play * volume, self.sample_rate)
            sd.wait()
            print("✅ Lecture terminée")
        except Exception as e:
            print(f"❌ Erreur de lecture: {e}")
    
    def cleanup(self):
        """Nettoie les fichiers temporaires"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except:
            pass

# =============================================================================
# 🚀 SCRIPT PRINCIPAL
# =============================================================================

def main():
    print("🎵 Voice Effects Tester - Laboratoire d'effets vocaux")
    print("=" * 60)
    
    # Vérification du fichier source
    if not os.path.exists(TEST_AUDIO_FILE):
        print(f"❌ Fichier non trouvé: {TEST_AUDIO_FILE}")
        print("\n💡 Créez un fichier audio de test ou modifiez TEST_AUDIO_FILE")
        return
    
    # Initialisation du processeur
    processor = VoiceEffectsProcessor()
    
    try:
        # Chargement de l'audio
        if not processor.load_audio(TEST_AUDIO_FILE):
            return
        
        # Affichage de la configuration SKIN
        print("\n🎛️ Configuration des effets SKIN:")
        active_effects = {k: v for k, v in EFFECTS_CONFIG.items() if v != 0}
        if active_effects:
            for effect, value in active_effects.items():
                print(f"   {effect}: {value}")
        else:
            print("   Aucun effet skin actif")
        
        # Affichage de la configuration ENVIRONNEMENT
        env_type = ENVIRONMENT_CONFIG.get("type", "none")
        env_intensity = ENVIRONMENT_CONFIG.get("intensity", 0)
        use_ffmpeg = ENVIRONMENT_CONFIG.get("use_ffmpeg", True)
        
        if env_type != "none" and env_intensity > 0:
            engine = "FFmpeg" if use_ffmpeg else "Numpy"
            print(f"\n🌍 Configuration environnement: {env_type.upper()} ({env_intensity}%) - {engine}")
            if env_type in ENVIRONMENT_CONFIG:
                env_params = ENVIRONMENT_CONFIG[env_type]
                for param, value in env_params.items():
                    print(f"   {param}: {value}")
        else:
            print("\n🌍 Aucun environnement actif")
        
        # Lecture de l'original si effets actifs
        if active_effects or (env_type != "none" and env_intensity > 0):
            input("\n🎵 Appuyez sur Entrée pour écouter l'ORIGINAL...")
            processor.play_audio(processor.audio_data, PLAYBACK_VOLUME)
        
        # Traitement des effets
        print("\n" + "=" * 60)
        processed_audio = processor.process_effects(EFFECTS_CONFIG, ENVIRONMENT_CONFIG)
        
        # Sauvegarde
        if SAVE_OUTPUT:
            processor.save_processed(OUTPUT_FILE)
        
        # Lecture automatique ou manuelle
        if AUTO_PLAY:
            print(f"\n🔊 Lecture automatique du résultat...")
            time.sleep(1)
            processor.play_audio(volume=PLAYBACK_VOLUME)
        else:
            input("\n🎵 Appuyez sur Entrée pour écouter le RÉSULTAT...")
            processor.play_audio(volume=PLAYBACK_VOLUME)
        
        # Statistiques finales
        print(f"\n📊 Statistiques:")
        print(f"   ⏱️  Temps de traitement: {processor.processing_time:.3f}s")
        print(f"   📏 Durée originale: {len(processor.audio_data) / processor.sample_rate:.2f}s")
        print(f"   📏 Durée traitée: {len(processed_audio) / processor.sample_rate:.2f}s")
        
        print("\n✅ Test terminé !")
    
    finally:
        # Nettoyage des fichiers temporaires
        processor.cleanup()

if __name__ == "__main__":
    main()