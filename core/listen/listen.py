"""
Module de reconnaissance vocale - Version Python
Remplace le module listen.js Node.js
"""

import subprocess
import threading
import json
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from core.bus import EventBus, Message


class ListenManager:
    """
    Gestionnaire du processus listen.exe avec communication via bus d'événements
    """

    def __init__(self, event_bus: EventBus, DEBUG: bool = False):
        self.event_bus = event_bus
        self.processes: Dict[str, subprocess.Popen] = {}
        self.threads: Dict[str, threading.Thread] = {}
        self.buffers: Dict[str, str] = {}
        self.running: Dict[str, bool] = {}
        self.DEBUG = DEBUG
        
        # === NOUVEAUX DEBUGS ===
        self.stats = {}  # Statistiques par listen_id
        self.last_recognition_time = {}  # Timestamp dernière reconnaissance
        self.process_health = {}  # État de santé des processus
        
        # Chemin vers l'exécutable
        self.listen_exe = Path(__file__).parent.parent / "exe" / "listen" / "listen.exe"
        
        # Messages à exclure du logging (exactement comme dans le JS)
        self.excluded_messages = [
            "AudioStateChanged",
            "recognizer_SpeechRecognitionRejected", 
            "recognizer_SpeechDetected",
            "AudioLevel",
            "MaxAlternates",
            "BabbleTimeout",
            "InitialSilenceTimeout",
            "EndSilenceTimeout",
            "EndSilenceTimeoutAmbiguous",
            "ResponseSpeed",
            "ComplexResponseSpeed",
            "AdaptationOn",
            "PersistedBackgroundAdaptation",
            "Pause listening.",
            "Culture: fr-FR Kinect",
            "Culture: en-US Kinect",
        ]
        
    def start(self, listen_id: str, options: Dict[str, Any]) -> bool:
        """Démarre un processus listen.exe avec l'ID spécifié"""
        try:
            # === DEBUG: INITIALISATION ===
            print(f"🚀 [DEBUG] Démarrage de {listen_id}")
            self._init_stats(listen_id)
            
            # Arrêter le processus existant s'il y en a un
            self.stop(listen_id)
            
            if not options.get('Grammar'):
                raise ValueError("No grammar specified")
                
            # Construire les arguments (exactement comme dans le JS)
            args = [
                str(self.listen_exe),
                '--device=' + str(options['Microphone']),
                '--grammar=' + str(options['Grammar']),
                '--confidence=' + str(options.get('Confidence', '0.7'))
            ]
            
            # Options facultatives
            if options.get('language'):
                args.append('--language=' + options['Language'])
            if options.get('recognizer'):
                args.append('--recognizer=' + options['recognizer'])  
            if options.get('Hotword'):
                args.append('--hotword=' + options['Hotword'])
            
            # === DEBUG: COMMANDE COMPLÈTE ===
            print(f"🔧 [DEBUG] Command Line: {' '.join(args)}")        
            
            # Lancer le processus
            start_time = time.time()
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=False,  # Mode binaire pour éviter les problèmes d'encodage
                bufsize=0
            )
            
            launch_time = time.time() - start_time
            print(f"⏱️ [DEBUG] Processus lancé en {launch_time:.3f}s - PID: {process.pid}")
            
            self.processes[listen_id] = process
            self.running[listen_id] = True
            self.buffers[listen_id] = ""
            
            # === DEBUG: HEALTH CHECK ===
            self.process_health[listen_id] = {
                "pid": process.pid,
                "start_time": time.time(),
                "restart_count": self.process_health.get(listen_id, {}).get("restart_count", 0),
                "last_activity": time.time(),
                "errors": 0
            }
            
            if self.DEBUG:
                print(f"@@@ Starting Process {listen_id} {process.pid}")
            
            # Créer les threads pour lire stdout et stderr
            stdout_thread = threading.Thread(
                target=self._read_stdout, 
                args=(listen_id, process, options),
                daemon=True
            )
            stderr_thread = threading.Thread(
                target=self._read_stderr,
                args=(listen_id, process),
                daemon=True
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            self.threads[listen_id + "_stdout"] = stdout_thread
            self.threads[listen_id + "_stderr"] = stderr_thread
            
            # === DEBUG: THREAD MONITORING ===
            print(f"🧵 [DEBUG] Threads créés pour {listen_id}: stdout={stdout_thread.is_alive()}, stderr={stderr_thread.is_alive()}")
            
            self._publish_event(listen_id, "started", {
                "pid": process.pid, 
                "options": options,
                "launch_time": launch_time,
                "restart_count": self.process_health[listen_id]["restart_count"]
            })
            
            return True
            
        except Exception as e:
            print(f"💥 [DEBUG] ERREUR démarrage {listen_id}: {str(e)}")
            self._publish_error(listen_id, f"Erreur démarrage: {str(e)}")
            return False

    def stop(self, listen_id: str) -> bool:
        """Arrête le processus spécifié"""
        try:
            print(f"🛑 [DEBUG] Arrêt de {listen_id}")
            
            self.running[listen_id] = False
            
            if listen_id in self.processes:
                process = self.processes[listen_id]
                if process and process.poll() is None:
                    # === DEBUG: HEALTH CHECK AVANT ARRÊT ===
                    uptime = time.time() - self.process_health.get(listen_id, {}).get("start_time", time.time())
                    print(f"📊 [DEBUG] Uptime de {listen_id}: {uptime:.1f}s")
                    print(f"📊 [DEBUG] Stats: {self.stats.get(listen_id, {})}")
                    
                    process.terminate()
                    process.wait(timeout=5)
                    print(f"✅ [DEBUG] Processus {listen_id} (PID: {process.pid}) terminé proprement")
                        
                del self.processes[listen_id]
                
            # Nettoyer les buffers et threads
            if listen_id in self.buffers:
                del self.buffers[listen_id]
                
            # === DEBUG: THREAD CLEANUP ===
            stdout_thread = self.threads.get(listen_id + "_stdout")
            stderr_thread = self.threads.get(listen_id + "_stderr")
            if stdout_thread:
                print(f"🧵 [DEBUG] Thread stdout alive: {stdout_thread.is_alive()}")
            if stderr_thread:
                print(f"🧵 [DEBUG] Thread stderr alive: {stderr_thread.is_alive()}")
                
            # Les threads daemon se termineront automatiquement
            
            self._publish_event(listen_id, "stopped", {
                "final_stats": self.stats.get(listen_id, {}),
                "uptime": uptime if 'uptime' in locals() else 0
            })
            return True
            
        except Exception as e:
            print(f"💥 [DEBUG] ERREUR arrêt {listen_id}: {str(e)}")
            self._publish_error(listen_id, f"Erreur arrêt: {str(e)}")
            return False

    def restart(self, listen_id: str, options: Dict[str, Any]) -> bool:
        """Redémarre le processus avec les nouvelles options"""
        self.stop(listen_id)
        return self.start(listen_id, options)

    def stop_all(self):
        """Arrête tous les processus"""
        for listen_id in list(self.processes.keys()):
            self.stop(listen_id)

    def _read_stdout(self, listen_id: str, process: subprocess.Popen, options: Dict[str, Any]):
        """Lit stdout en continu et extrait les JSON (comme handleBuffer dans le JS)"""
        try:
            print(f"🔍 [DEBUG] Thread stdout démarré pour {listen_id}")
            read_count = 0
            
            while self.running.get(listen_id, False) and process.poll() is None:
                # === DEBUG: PROCESS HEALTH CHECK ===
                if read_count % 100 == 0:  # Check toutes les 100 lectures
                    self._update_health(listen_id)
                
                data = process.stdout.read(1024)  # Lire par chunks
                if data:
                    read_count += 1
                    decoded_data = data.decode('utf-8', errors='ignore')
                    
                    # === DEBUG: DATA FLOW ===
                    if read_count % 50 == 0:  # Log toutes les 50 lectures
                        print(f"📡 [DEBUG] {listen_id} - Lecture #{read_count}, taille: {len(data)} bytes")
                    
                    self._handle_buffer(listen_id, decoded_data, options)
                        
            print(f"🔍 [DEBUG] Thread stdout terminé pour {listen_id} (lectures: {read_count})")
                        
        except Exception as e:
            print(f"💥 [DEBUG] ERREUR thread stdout {listen_id}: {str(e)}")
            self._increment_error(listen_id)
            if self.running.get(listen_id, False):
                self._publish_error(listen_id, f"Erreur lecture stdout: {str(e)}")

    def _read_stderr(self, listen_id: str, process: subprocess.Popen):
        """Lit stderr en continu pour le logging"""
        try:
            print(f"🔍 [DEBUG] Thread stderr démarré pour {listen_id}")
            error_count = 0
            
            while self.running.get(listen_id, False) and process.poll() is None:
                data = process.stderr.read(1024)
                if data:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    
                    # === DEBUG: ERROR TRACKING ===
                    if "error" in decoded_data.lower() or "exception" in decoded_data.lower():
                        error_count += 1
                        print(f"⚠️ [DEBUG] Erreur détectée #{error_count} dans {listen_id}: {decoded_data[:100]}...")
                        self._increment_error(listen_id)
                    
                    self._handle_stderr_data(listen_id, decoded_data)
                        
            print(f"🔍 [DEBUG] Thread stderr terminé pour {listen_id} (erreurs: {error_count})")
                        
        except Exception as e:
            print(f"💥 [DEBUG] ERREUR thread stderr {listen_id}: {str(e)}")
            self._increment_error(listen_id)
            if self.running.get(listen_id, False):
                self._publish_error(listen_id, f"Erreur lecture stderr: {str(e)}")

    def _handle_buffer(self, listen_id: str, data: str, options: Dict[str, Any]):
        """Traite le buffer et extrait les JSON (équivalent de handleBuffer du JS)"""
        
        # Ajouter au buffer
        if listen_id not in self.buffers:
            self.buffers[listen_id] = ""
            
        self.buffers[listen_id] += data
        buffer = self.buffers[listen_id]
        
        # === DEBUG: BUFFER SIZE ===
        if len(buffer) > 10000:  # Buffer trop gros = problème potentiel
            print(f"⚠️ [DEBUG] Buffer très gros pour {listen_id}: {len(buffer)} chars")
        
        # Chercher les balises JSON (exactement comme dans le JS)
        end_pos = buffer.find('</JSON>')
        if end_pos < 0:
            return
            
        start_pos = buffer.find('<JSON>')
        if start_pos < 0:
            return
            
        # Extraire le JSON
        json_str = buffer[start_pos + 6:end_pos]
        self.buffers[listen_id] = buffer[end_pos + 7:]
        
        # === DEBUG: JSON PROCESSING ===
        print(f"🔍 [DEBUG] JSON extrait de {listen_id}: {len(json_str)} chars")
        
        try:
            json_data = json.loads(json_str)
            
            # === DEBUG: ANALYSE FAUX POSITIFS ===
            confidence = self._extract_confidence(json_data)
            is_false_positive = self._analyze_false_positive(listen_id, json_data, confidence)
            
            if self.DEBUG:
                print(f"[JSON REÇU] {json_data}")
            
            # === DEBUG: STATISTICS ===
            self._update_stats(listen_id, json_data, confidence, is_false_positive)
            
            # Publier sur le bus (équivalent du callback dans le JS)
            self._publish_event(listen_id, "recognition", {
                "data": json_data,
                "options": options,
                "confidence": confidence,
                "is_false_positive": is_false_positive,
                "stats": self.stats.get(listen_id, {})
            })
            
        except json.JSONDecodeError as e:
            print(f'💥 [DEBUG] Parsing Error dans {listen_id}: {e}, json: {json_str[:200]}...')
            self._increment_error(listen_id)

    def _handle_stderr_data(self, listen_id: str, data: str):
        """Traite les données stderr avec filtrage (équivalent de stdErr du JS)"""
        
        lines = data.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            # === DEBUG: CRASH DETECTION ===
            crash_keywords = ["access violation", "segmentation fault", "crash", "fatal error", "exception"]
            if any(keyword in line.lower() for keyword in crash_keywords):
                print(f"💥 [DEBUG] CRASH DÉTECTÉ dans {listen_id}: {line}")
                self._publish_event(listen_id, "crash_detected", {"message": line.strip()})
                
            # Vérifier si la ligne doit être exclue (exactement comme dans le JS)
            should_exclude = any(excluded in line for excluded in self.excluded_messages)
            
            if not should_exclude:
                self._log_colored_message(line)
                
                # === DEBUG: RECONNAISSANCE EVENTS ===
                if "SpeechRecognized" in line:
                    self._track_recognition_event(listen_id, line)
                elif "SpeechHypothesized" in line:
                    self._track_hypothesis_event(listen_id, line)
                
                # Publier les messages importants sur le bus SEULEMENT si DEBUG=True
                if self.DEBUG and any(keyword in line for keyword in ["SpeechRecognized", "recognizer_SpeechHypothesized"]):
                    self._publish_event(listen_id, "debug", {"message": line.strip()})

    def _log_colored_message(self, text: str):
        """Affichage coloré des logs (simplifié par rapport au JS)"""
        # Si DEBUG est désactivé, ne pas afficher les logs console
        if not self.DEBUG:
            return
            
        lines = text.split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            if "recognizer_SpeechHypothesized" in line:
                # Extraction de la confiance comme dans le JS
                import re
                match = re.search(r'=>\s([\d,]+)', line)
                info_match = re.search(r'recognizer_SpeechHypothesized(.*?)=>', line)
                
                if match and info_match:
                    info = info_match.group(1)
                    words = info.strip().split()
                    
                    if len(words) > 3:
                        confidence = float(match.group(1).replace(',', '.'))
                        if confidence > 0.75:
                            print(f"    {len(words)} mots consécutifs détectés")
                            print(f"    {line.strip()}")
                            
            elif any(keyword in line for keyword in ["Init recognizer", "Start listening...", "Loading grammar cache"]):
                print(f"    {line.strip()}")
            elif "SpeechRecognized" in line:
                print(f"            {line.strip()}")
            else:
                print(f"        {line.strip()}")

    def _publish_event(self, listen_id: str, state: str, payload: Dict[str, Any] = None):
        """Publie un événement sur le bus"""
        if payload is None:
            payload = {}
        
        # Message est juste un alias pour Dict[str, Any], on crée un dictionnaire
        message = {
            "name": f"listen.{listen_id}",  # Nom du module
            "state": state,                 # État (started, stopped, recognition, etc.)
            "payload": payload              # Données
        }
        self.event_bus.publish(message)

    def _publish_error(self, listen_id: str, error_msg: str):
        """Publie une erreur sur le bus"""
        self._publish_event(listen_id, "error", {"message": error_msg})

    # === NOUVELLES MÉTHODES DE DEBUG ===
    
    def _init_stats(self, listen_id: str):
        """Initialise les statistiques pour un listen_id"""
        self.stats[listen_id] = {
            "recognitions": 0,
            "false_positives": 0,
            "hypotheses": 0,
            "errors": 0,
            "avg_confidence": 0.0,
            "low_confidence_count": 0,
            "rapid_fire_count": 0,  # Reconnaissances trop rapprochées
            "start_time": time.time(),
            "last_recognition": 0,
            "recognition_intervals": []  # Pour détecter les patterns
        }
        
    def _extract_confidence(self, json_data: Dict[str, Any]) -> float:
        """Extrait la confiance du JSON de reconnaissance"""
        try:
            # Chercher dans différents emplacements possibles
            if "confidence" in json_data:
                return float(json_data["confidence"])
            elif "Confidence" in json_data:
                return float(json_data["Confidence"])
            elif isinstance(json_data.get("alternatives"), list) and len(json_data["alternatives"]) > 0:
                return float(json_data["alternatives"][0].get("confidence", 0.0))
            return 0.0
        except (ValueError, TypeError, KeyError):
            return 0.0
            
    def _analyze_false_positive(self, listen_id: str, json_data: Dict[str, Any], confidence: float) -> bool:
        """Analyse si une reconnaissance est probablement un faux positif"""
        now = time.time()
        stats = self.stats.get(listen_id, {})
        
        # Critère 1: Confiance trop faible
        if confidence < 0.5:
            print(f"🚨 [DEBUG] Faux positif potentiel {listen_id}: confiance faible ({confidence:.2f})")
            return True
            
        # Critère 2: Reconnaissances trop rapprochées (< 1 seconde)
        last_rec = stats.get("last_recognition", 0)
        if last_rec > 0 and (now - last_rec) < 1.0:
            print(f"🚨 [DEBUG] Faux positif potentiel {listen_id}: trop rapide ({now - last_rec:.2f}s)")
            return True
            
        # Critère 3: Texte suspect (trop court, caractères bizarres)
        text = str(json_data.get("text", ""))
        if len(text.strip()) < 2:
            print(f"🚨 [DEBUG] Faux positif potentiel {listen_id}: texte trop court ('{text}')")
            return True
            
        return False
        
    def _update_stats(self, listen_id: str, json_data: Dict[str, Any], confidence: float, is_false_positive: bool):
        """Met à jour les statistiques"""
        if listen_id not in self.stats:
            self._init_stats(listen_id)
            
        stats = self.stats[listen_id]
        now = time.time()
        
        stats["recognitions"] += 1
        if is_false_positive:
            stats["false_positives"] += 1
            
        if confidence < 0.6:
            stats["low_confidence_count"] += 1
            
        # Intervalle depuis dernière reconnaissance
        if stats["last_recognition"] > 0:
            interval = now - stats["last_recognition"]
            stats["recognition_intervals"].append(interval)
            if interval < 1.0:
                stats["rapid_fire_count"] += 1
                
        stats["last_recognition"] = now
        
        # Moyenne mobile de la confiance
        total_conf = stats["avg_confidence"] * (stats["recognitions"] - 1) + confidence
        stats["avg_confidence"] = total_conf / stats["recognitions"]
        
        # Alertes
        false_positive_rate = stats["false_positives"] / stats["recognitions"]
        if false_positive_rate > 0.3:  # Plus de 30% de faux positifs
            print(f"🚨 [ALERT] Taux de faux positifs élevé pour {listen_id}: {false_positive_rate:.1%}")
            
    def _track_recognition_event(self, listen_id: str, line: str):
        """Suit les événements de reconnaissance dans stderr"""
        now = time.time()
        self.last_recognition_time[listen_id] = now
        
        # Extraire des infos de la ligne si possible
        confidence_match = re.search(r'confidence[:\s]+([\d.]+)', line.lower())
        if confidence_match:
            conf = float(confidence_match.group(1))
            print(f"📊 [DEBUG] SpeechRecognized {listen_id}: confidence={conf:.2f}")
            
    def _track_hypothesis_event(self, listen_id: str, line: str):
        """Suit les hypothèses dans stderr"""
        if listen_id not in self.stats:
            self._init_stats(listen_id)
        self.stats[listen_id]["hypotheses"] += 1
        
        # Analyser la ligne pour détecter les patterns suspects
        if "=>" in line:
            confidence_match = re.search(r'=>\s*([\d,]+)', line)
            if confidence_match:
                conf_str = confidence_match.group(1).replace(',', '.')
                try:
                    conf = float(conf_str)
                    if conf < 0.3:
                        print(f"⚠️ [DEBUG] Hypothèse très faible {listen_id}: {conf:.2f}")
                except ValueError:
                    pass
                    
    def _update_health(self, listen_id: str):
        """Met à jour l'état de santé du processus"""
        if listen_id in self.process_health:
            self.process_health[listen_id]["last_activity"] = time.time()
            
            # Check si le processus est toujours vivant
            if listen_id in self.processes:
                process = self.processes[listen_id]
                if process.poll() is not None:
                    print(f"💀 [DEBUG] Processus {listen_id} est mort ! Exit code: {process.poll()}")
                    self._publish_event(listen_id, "process_died", {
                        "exit_code": process.poll(),
                        "uptime": time.time() - self.process_health[listen_id]["start_time"]
                    })
                    
    def _increment_error(self, listen_id: str):
        """Incrémente le compteur d'erreurs"""
        if listen_id in self.stats:
            self.stats[listen_id]["errors"] += 1
        if listen_id in self.process_health:
            self.process_health[listen_id]["errors"] += 1
            
        # Alerte si trop d'erreurs
        error_count = self.process_health.get(listen_id, {}).get("errors", 0)
        if error_count > 10:
            print(f"🚨 [ALERT] Trop d'erreurs pour {listen_id}: {error_count}")
            
    def get_debug_info(self, listen_id: str = None) -> Dict[str, Any]:
        """Retourne les informations de debug"""
        if listen_id:
            return {
                "stats": self.stats.get(listen_id, {}),
                "health": self.process_health.get(listen_id, {}),
                "running": self.running.get(listen_id, False),
                "buffer_size": len(self.buffers.get(listen_id, ""))
            }
        else:
            return {
                "all_stats": self.stats,
                "all_health": self.process_health,
                "running_processes": list(self.running.keys()),
                "total_processes": len(self.processes)
            }

    def __del__(self):
        """Nettoyage automatique"""
        self.stop_all()


# Fonction de convenience pour créer et gérer une instance globale
_listen_manager: Optional[ListenManager] = None

def get_listen_manager(event_bus: EventBus, DEBUG: bool = False) -> ListenManager:
    """Retourne l'instance du gestionnaire de reconnaissance vocale"""
    global _listen_manager
    if _listen_manager is None:
        _listen_manager = ListenManager(event_bus, DEBUG=DEBUG)
    return _listen_manager