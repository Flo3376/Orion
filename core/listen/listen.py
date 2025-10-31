"""
Module de reconnaissance vocale - Version Python
Remplace le module listen.js Node.js
"""

import subprocess
import threading
import json
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
            #afficher la ligne de commande complète en mode debug
            if self.DEBUG:
                print(f"@@@ Command Line: {' '.join(args)}")        
            # Lancer le processus
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=False,  # Mode binaire pour éviter les problèmes d'encodage
                bufsize=0
            )
            
            self.processes[listen_id] = process
            self.running[listen_id] = True
            self.buffers[listen_id] = ""
            
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
            
            self._publish_event(listen_id, "started", {"pid": process.pid, "options": options})
            
            return True
            
        except Exception as e:
            self._publish_error(listen_id, f"Erreur démarrage: {str(e)}")
            return False

    def stop(self, listen_id: str) -> bool:
        """Arrête le processus spécifié"""
        try:
            self.running[listen_id] = False
            
            if listen_id in self.processes:
                process = self.processes[listen_id]
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
                    if self.DEBUG:
                        print(f"@@@ Killing [{listen_id}] PID: {process.pid}")
                        
                del self.processes[listen_id]
                
            # Nettoyer les buffers et threads
            if listen_id in self.buffers:
                del self.buffers[listen_id]
                
            # Les threads daemon se termineront automatiquement
            
            self._publish_event(listen_id, "stopped")
            return True
            
        except Exception as e:
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
            while self.running.get(listen_id, False) and process.poll() is None:
                data = process.stdout.read(1024)  # Lire par chunks
                if data:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    self._handle_buffer(listen_id, decoded_data, options)
                        
        except Exception as e:
            if self.running.get(listen_id, False):
                self._publish_error(listen_id, f"Erreur lecture stdout: {str(e)}")

    def _read_stderr(self, listen_id: str, process: subprocess.Popen):
        """Lit stderr en continu pour le logging"""
        try:
            while self.running.get(listen_id, False) and process.poll() is None:
                data = process.stderr.read(1024)
                if data:
                    decoded_data = data.decode('utf-8', errors='ignore')
                    self._handle_stderr_data(listen_id, decoded_data)
                        
        except Exception as e:
            if self.running.get(listen_id, False):
                self._publish_error(listen_id, f"Erreur lecture stderr: {str(e)}")

    def _handle_buffer(self, listen_id: str, data: str, options: Dict[str, Any]):
        """Traite le buffer et extrait les JSON (équivalent de handleBuffer du JS)"""
        
        # Ajouter au buffer
        if listen_id not in self.buffers:
            self.buffers[listen_id] = ""
            
        self.buffers[listen_id] += data
        buffer = self.buffers[listen_id]
        
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
        
        try:
            json_data = json.loads(json_str)
            
            if self.DEBUG:
                print(f"[JSON REÇU] {json_data}")
            
            # Publier sur le bus (équivalent du callback dans le JS)
            self._publish_event(listen_id, "recognition", {
                "data": json_data,
                "options": options
            })
            
        except json.JSONDecodeError as e:
            print(f'Parsing Error: {e}, json: {json_str}')

    def _handle_stderr_data(self, listen_id: str, data: str):
        """Traite les données stderr avec filtrage (équivalent de stdErr du JS)"""
        
        lines = data.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            # Vérifier si la ligne doit être exclue (exactement comme dans le JS)
            should_exclude = any(excluded in line for excluded in self.excluded_messages)
            
            if not should_exclude:
                self._log_colored_message(line)
                
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