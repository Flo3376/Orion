"""
🎛️ FX Generator - Module de génération d'effets audio
====================================================

Module dédié à la génération des variantes d'effets en arrière-plan.
Interface simple : fx.create(source_path, effect, force_remake=False)
"""

import threading
import time
import logging
from pathlib import Path
from queue import Queue, PriorityQueue
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import IntEnum
import numpy as np
from scipy.signal import butter, filtfilt
from core.pol import create_pol
pol = create_pol(source_id=51)

class Priority(IntEnum):
    """Priorités des tâches de génération"""
    LOW = 3      # Génération proactive
    NORMAL = 2   # Demande utilisateur
    HIGH = 1     # Régénération forcée
    URGENT = 0   # Erreur de lecture, fallback immédiat

@dataclass
class GenerationJob:
    """Tâche de génération d'effet"""
    priority: Priority
    source_path: str           # Chemin du fichier brut.wav
    target_path: str           # Chemin du fichier effet.wav
    effect_type: str           # "ship", "city", "helmet"
    force_remake: bool = False # True = régénérer même si existe
    timestamp: float = 0.0     # Pour tri temporel
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
    
    def __lt__(self, other):
        # Priorité puis timestamp (FIFO pour même priorité)
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.timestamp < other.timestamp

class FXGenerator:
    """Générateur d'effets audio en arrière-plan"""
    
    def __init__(self, max_workers: int = 1):
        self.max_workers = max_workers
        self.generation_queue = PriorityQueue()
        self.active_jobs = set()  # Éviter les doublons
        self.workers = []
        self.running = False
        self.stats = {
            "generated": 0,
            "errors": 0,
            "skipped": 0,
            "queue_peak": 0
        }
        
        # Configuration des effets
        self.AVAILABLE_EFFECTS = ["ship", "city", "helmet"]
        self.effects_processor = None  # Lazy loading
        
        self._start_workers()
    
    # =========================================================================
    # 🎯 API PUBLIQUE
    # =========================================================================
    
    def create_async(self, source_path: str, effect: str, force_remake: bool = False, priority: Priority = Priority.NORMAL) -> bool:
        """
        Programme la génération d'un effet (asynchrone)
        
        Args:
            source_path: Chemin du fichier brut.wav
            effect: Type d'effet ("ship", "city", "helmet")
            force_remake: True = régénérer même si existe
            priority: Priorité de la tâche
            
        Returns:
            True si ajouté à la queue, False si erreur
        """
        
        # Validation
        if not self._validate_inputs(source_path, effect):
            return False
        
        target_path = self._get_target_path(source_path, effect)
        
        # Vérifier si déjà existe (sauf si force_remake)
        if not force_remake and Path(target_path).exists():
            pol.write(1, f"Effet déjà existant: {effect} pour {Path(source_path).name}", mode="log")
            #logging.debug(f"✅ Effet déjà existant: {effect} -> {Path(target_path).name}")
            return True
        
        # Éviter les doublons dans la queue
        job_key = f"{source_path}:{effect}"
        if job_key in self.active_jobs and not force_remake:
            pol.write(1, f"Job déjà en queue: {job_key}", mode="log")
            #logging.debug(f"⏸️ Job déjà en queue: {job_key}")
            return True
        
        # Créer et ajouter le job
        job = GenerationJob(
            priority=priority,
            source_path=source_path,
            target_path=target_path,
            effect_type=effect,
            force_remake=force_remake
        )
        
        self.active_jobs.add(job_key)
        self.generation_queue.put(job)
        
        # Statistiques
        queue_size = self.generation_queue.qsize()
        if queue_size > self.stats["queue_peak"]:
            self.stats["queue_peak"] = queue_size
        
        pol.write(1, f"Job programmé: {effect} pour {Path(source_path).parent.name} (priorité: {priority.name})", mode="log")
        #print(f"📋 Job programmé: {effect} pour {Path(source_path).parent.name} (priorité: {priority.name})")
        return True
    
    # =========================================================================
    # 🔧 TRAITEMENT DES JOBS
    # =========================================================================
    
    def _process_job_sync(self, job: GenerationJob) -> bool:
        """Traite un job de manière synchrone"""
        
        try:
            # Initialiser le processeur si nécessaire
            if self.effects_processor is None:
                self._init_effects_processor()
            
            # Charger l'audio source
            if not self.effects_processor.load_audio(job.source_path):
                pol.write(3, f"❌ Impossible de charger: {job.source_path}", mode="log+print")
                self.stats["errors"] += 1
                return False
            
            # Vérifier si target existe déjà (sauf force_remake)
            if not job.force_remake and Path(job.target_path).exists():
                pol.write(1, f"⏭️ Effet déjà existant: {Path(job.target_path).name}", mode="log")
                self.stats["skipped"] += 1
                return True
            
            # Traitement de l'effet
            start_time = time.time()
            effect_config = self._get_effect_config(job.effect_type)
            
            processed = self.effects_processor._apply_environment_effects(
                self.effects_processor.audio_data.copy(),
                effect_config
            )
            
            # Créer le répertoire cible si nécessaire
            Path(job.target_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Sauvegarder le résultat
            import soundfile as sf
            sf.write(job.target_path, processed, self.effects_processor.sample_rate)
            
            processing_time = time.time() - start_time
            self.stats["generated"] += 1
            pol.write(1, f"✅ Généré {job.effect_type}: {Path(job.target_path).name} ({processing_time:.2f}s)", mode="log")
            return True
            
        except Exception as e:
            pol.write(3, f"❌ Erreur génération {job.effect_type}: {e}", mode="log+print")
            self.stats["errors"] += 1
            return False
    
    def _process_job_async(self, job: GenerationJob):
        """Traite un job de manière asynchrone (worker thread)"""
        
        job_key = f"{job.source_path}:{job.effect_type}"
        
        try:
            success = self._process_job_sync(job)
            
            if success:
                # Logger seulement si succès
                try:
                    pol.write(1, f"✅ Effet {job.effect_type} généré: {Path(job.target_path).name}", mode="log")
                except:
                    pass  # Ignorer les erreurs de logging
            
        except Exception as e:
            # 🔧 FIX: Gestion d'erreur plus robuste
            try:
                pol.write(3, f"❌ Erreur génération {job.effect_type}: {type(e).__name__}", mode="log+print")
            except:
                pass  # Ignorer les erreurs de logging
                
        finally:
            # Nettoyer le job des actifs dans tous les cas
            try:
                self.active_jobs.discard(job_key)
            except:
                pass  # Même si ça échoue, continuer

    def _worker_loop(self):
        """Boucle principale d'un worker"""
        
        while self.running:
            try:
                # Attendre un job (timeout pour permettre l'arrêt)
                job = self.generation_queue.get(timeout=1.0)
                
                # Traiter le job
                self._process_job_async(job)
                
                # Marquer comme terminé
                self.generation_queue.task_done()
                
                # Pause pour limiter l'impact CPU
                time.sleep(0.1)  # 100ms entre jobs
                
            except Exception as e:
                # 🔧 FIX: Gestion plus robuste des erreurs
                error_type = type(e).__name__
                
                if "Empty" in str(e) or error_type == "Empty":
                    # Timeout normal de la queue, continuer silencieusement
                    continue
                else:
                    # Vraie erreur à logger
                    try:
                        pol.write(3, f"❌ Erreur worker FX ({error_type}): {e}", mode="log+print")
                        # Ne pas faire de traceback complet pour éviter les exceptions en cascade
                    except:
                        # Si même le print échoue, juste continuer
                        pass
                    
                    # Continuer le worker même en cas d'erreur
                    continue
    
    # =========================================================================
    # 🛠️ MÉTHODES UTILITAIRES
    # =========================================================================
    
    def _validate_inputs(self, source_path: str, effect: str) -> bool:
        """Valide les paramètres d'entrée"""
        
        if not Path(source_path).exists():
            pol.write(3, f"⚠️ Fichier source inexistant: {source_path}", mode="log+print")
            return False
        
        if effect not in self.AVAILABLE_EFFECTS:
            pol.write(3, f"⚠️ Effet inconnu: {effect}. Disponibles: {self.AVAILABLE_EFFECTS}", mode="log+print" )
            return False
        
        return True
    
    def _get_target_path(self, source_path: str, effect: str) -> Path:
        """Calcule le chemin de sortie depuis le chemin source"""
        
        source = Path(source_path)
        
        # ✅ FIX: Détecter si source est un fichier skin.wav
        if source.name == "skin.wav":
            # Source = /path/to/action/skin.wav
            # Target = /path/to/action/effect.wav (même dossier)
            target_dir = source.parent
            target_file = target_dir / f"{effect}.wav"
            
            pol.write(1, f"🎨 Source SKIN détectée: {source.name} → {target_file.name}", mode="log")
            return target_file
        
        elif source.name == "brut.wav":
            # Source = /path/to/action/brut.wav  
            # Target = /path/to/action/effect.wav (même dossier)
            target_dir = source.parent
            target_file = target_dir / f"{effect}.wav"
            
            pol.write(1, f"🎤 Source BRUT détectée: {source.name} → {target_file.name}", mode="log")
            return target_file
        
        else:
            # Logique existante pour autres cas
            # ...reste du code existant...
            pass
    
    def _get_effect_config(self, effect: str) -> Dict:
        """Retourne la configuration d'effet"""
        
        base_config = {
            "type": effect,
            "intensity": 100,
            "use_ffmpeg": True,
        }
        
        if effect == "ship":
            base_config["ship"] = {
                "echo_gain": 88,
                "echo_delay": 45,
                "compressor": 60,
                "metallic_boost": 30,
                "volume_pre": 50,
                "volume_post": 150,
            }
        elif effect == "city":
            base_config["city"] = {
                "highpass": 300,
                "lowpass": 3000,
                "volume_boost": 8,
                "echo_radio": 0,
            }
        elif effect == "helmet":
            # 🔧 FIX: Configuration helmet corrigée pour éviter l'erreur FFmpeg
            base_config["helmet"] = {
                "delay": 25,
                "lowpass_cutoff": 2000,
                "highpass": 300,
                "compression": 0.6,        # ← Entre 0 et 1
                "eq_cut": -6,             # ← Négatif en dB
                "volume_boost": -3        # ← Négatif pour baisse
            }
            base_config["use_ffmpeg"] = False  # ← TEMPORAIRE: Utiliser numpy pour helmet
        
        return base_config
    
    def _init_effects_processor(self):
        """Initialise le processeur d'effets (lazy loading)"""
        try:
            from test_voice_effects import VoiceEffectsProcessor
            self.effects_processor = VoiceEffectsProcessor()
            pol.write(1, "🔧 Processeur d'effets initialisé", mode="log+print")
        except ImportError as e:
            pol.write(3, f"❌ Impossible d'importer VoiceEffectsProcessor: {e}", mode="log+print")
            pol.write(3, "💡 Assurez-vous que test_voice_effects.py est accessible", mode="log+print")
            raise
    
    def _apply_helmet_numpy(self, audio_data: np.ndarray, sample_rate: int, config: Dict) -> np.ndarray:
        """Applique effet helmet avec numpy (pas FFmpeg)"""
        try:
            pol.write(1, "🌍 Environment Numpy: HELMET", mode="log")

            # Paramètres simplifiés
            helmet_config = config.get("helmet", {})
            
            # Filtre passe-bas simple (simulation casque)
            # Lowpass à 2000Hz pour simulation casque
            lowpass_freq = helmet_config.get("lowpass_cutoff", 2000)
            nyquist = sample_rate / 2
            low_cutoff = min(lowpass_freq / nyquist, 0.95)  # Éviter les erreurs
            
            b, a = butter(4, low_cutoff, btype='low')
            filtered_audio = filtfilt(b, a, audio_data)
            
            # Réduction volume
            volume_factor = 0.7  # -3dB approximatif
            result = filtered_audio * volume_factor
            
            # Éviter le clipping
            result = np.clip(result, -1.0, 1.0)
            
            pol.write(1, f"✅ Helmet numpy appliqué (lowpass: {lowpass_freq}Hz, volume: {volume_factor})", mode="log+print")
            return result
            
        except Exception as e:
            pol.write(3, f"❌ Erreur helmet numpy: {e}", mode="log+print")
            return audio_data  # Retourner original en cas d'erreur
    
    def _apply_effect_numpy(self, audio_data: np.ndarray, sample_rate: int, effect: str, config: Dict) -> Optional[np.ndarray]:
        """Applique l'effet avec numpy (fallback)"""
        
        if effect == "ship":
            return self._apply_ship_numpy(audio_data, sample_rate, config)
        elif effect == "city":
            return self._apply_city_numpy(audio_data, sample_rate, config)
        elif effect == "helmet":
            return self._apply_helmet_numpy(audio_data, sample_rate, config)  # ← NOUVEAU
        else:
            pol.write(3, f"❌ Effet numpy non supporté: {effect}", mode="log+print")
            return None
    
    # =========================================================================
    # 📊 MONITORING ET CONTRÔLE
    # =========================================================================
    
    def get_status(self) -> Dict:
        """Retourne le statut du générateur"""
        return {
            "running": self.running,
            "workers_count": len(self.workers),
            "queue_size": self.generation_queue.qsize(),
            "active_jobs": len(self.active_jobs),
            "stats": self.stats.copy(),
            "available_effects": self.AVAILABLE_EFFECTS.copy()
        }
    
    def stop(self, timeout: float = 5.0):
        """Arrête le générateur proprement"""
        if not self.running:
            return
        
        pol.write(1, "🛑 Arrêt du FX Generator...", mode="log+print")
        self.running = False
        
        # Attendre que les workers se terminent
        for worker in self.workers:
            if worker.is_alive():
                worker.join(timeout=timeout/len(self.workers))
        
        # Vider la queue
        while not self.generation_queue.empty():
            try:
                self.generation_queue.get_nowait()
            except:
                break
        
        self.workers.clear()
        self.active_jobs.clear()
        pol.write(1, f"✅ FX Generator arrêté. Stats: {self.stats}", mode="log")
        

    def _start_workers(self):
        """Démarre les workers de génération"""
        if not self.running:
            self.running = True
                
            for i in range(self.max_workers):
                worker = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name=f"FXGenerator-{i+1}"
                )
                worker.start()
                self.workers.append(worker)

            pol.write(1, f"🔧 {self.max_workers} worker(s) FX démarré(s)", mode="log+print")
# =============================================================================
# 🎯 INSTANCE GLOBALE
# =============================================================================

# Instance globale du générateur (singleton pattern)
fx_generator = FXGenerator(max_workers=1)

# Ajouter ces méthodes dans la section "🏃 WORKERS ET GESTION THREADS" :



def create_async(source_path: str, effect: str, force_remake: bool = False) -> bool:
    """Interface simplifiée pour génération asynchrone"""
    return fx_generator.create_async(source_path, effect, force_remake)

def get_status() -> Dict:
    """Interface simplifiée pour le statut"""
    return fx_generator.get_status()

def stop():
    """Interface simplifiée pour l'arrêt"""
    fx_generator.stop()