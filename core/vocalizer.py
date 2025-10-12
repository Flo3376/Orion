# /core/vocalizer.py
"""
Module Vocalizer - Synthèse vocale unifiée pour Orion
Gère tous les moteurs TTS (Piper, Revoicer, OpenAI, Azure) de manière unifiée
"""

from __future__ import annotations
from pathlib import Path
from abc import ABC, abstractmethod
import threading
import time
import subprocess
import json
import requests
from urllib.parse import urlencode
from core.sound.fx_manager import get_fx_manager


class Vocalizer:
    """
    Point d'entrée unique pour la synthèse vocale
    Cache intelligent par action/moteur
    """
    
    def __init__(self, config_manager, event_bus):
        """
        Initialise le vocaliseur avec les dépendances
        
        Args:
            config_manager: Gestionnaire de configuration
            event_bus: Bus d'événements pour publication audio
        """
        self.config_manager = config_manager
        self.event_bus = event_bus
        
        # Cache et chemins
        self.base_output_path = Path("./sound/output_sound/")
        self.sound_bank_path = Path(config_manager.get("sound_bank.path_output", "./sound/output_sound/sound_bank/"))
        
        # Moteurs TTS disponibles
        self.engines = {
            "piper": PiperEngine(config_manager),
            "openai": OpenAIEngine(config_manager),  # ✅ NOUVEAU
            "edgetts": EdgeTTSEngine(config_manager),  # ✅ NOUVEAU
        }
        
        # ✅ NOUVEAU : Initialiser le FX Manager
        self.fx_manager = get_fx_manager(config_manager, event_bus)
        
        print(f"🎤 Vocalizer initialisé avec {len(self.engines)} moteur(s)")
    
    def create(self, engine: str, action_code: str, text: str, 
               effect: str = "none", play_now: bool = True, skin_test: bool = False) -> str:
        """Point d'entrée UNIQUE pour la synthèse vocale avec système de couches"""
        
        print(f"🎵 VCZ.create(engine={engine}, action={action_code}, text='{text[:30]}...', effect={effect}, play={play_now}, skin_test={skin_test})")
        
        try:
            # =========================================================================
            # 🎤 ÉTAPE 1 : GÉNÉRATION DU BRUT (inchangée)
            # =========================================================================
            
            base_file = self._get_cached_file_path(engine, action_code, text)
            
            # Toujours convertir vers structure répertoire/brut.wav
            if base_file.name != "brut.wav":
                audio_dir = base_file.parent / base_file.stem
                brut_file = audio_dir / "brut.wav"
            else:
                brut_file = base_file
            
            brut_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Générer BRUT si manquant
            if not brut_file.exists() or brut_file.stat().st_size == 0:
                print(f"🔧 Cache MISS brut: Génération TTS en cours...")
                success = self._generate_and_cache_tts(engine, action_code, text, base_file)
                
                if not success:
                    self._handle_error(effect, play_now)
                    return ""
                
                print(f"✅ BRUT généré: {brut_file.name}")
            else:
                print(f"⚡ Cache HIT brut: {brut_file.name}")
            
            # =========================================================================
            # 🎨 ÉTAPE 2 : GÉNÉRATION DU SKIN + EFFECTS via FX Manager
            # =========================================================================
            
            # ✅ NOUVEAU : Utiliser fx_manager au lieu de la logique interne
            if skin_test:
                # Mode test skin → créer skin seulement
                print(f"🎵 Mode test skin → génération skin uniquement")
                skin_success = self.fx_manager.create_skin_for(str(brut_file))
                
                if skin_success:
                    skin_file = brut_file.parent / "skin.wav"
                    if play_now:
                        self._publish_audio_event(skin_file, "none", action_code)
                    return str(skin_file)
                else:
                    print("❌ Échec génération skin → lecture BRUT")
                    if play_now:
                        self._publish_audio_event(brut_file, "none", action_code)
                    return str(brut_file)
            
            # Mode normal → créer skin + effects selon demande
            if effect == "none":
                # Pas d'effet environment → créer skin + programmer tous les environments
                print(f"🎵 Pas d'effet → génération skin + programmation environments")
                
                # Créer skin + tous les environments en arrière-plan
                success = self.fx_manager.create_for(str(brut_file), effects="all")
                
                # Lire le skin en attendant
                skin_file = brut_file.parent / "skin.wav"
                if skin_file.exists():
                    if play_now:
                        self._publish_audio_event(skin_file, "none", action_code)
                    return str(skin_file)
                else:
                    # Fallback vers brut si skin échoue
                    if play_now:
                        self._publish_audio_event(brut_file, "none", action_code)
                    return str(brut_file)
            
            else:
                # Effet environment demandé → vérifier s'il existe
                environment_file = brut_file.parent / f"{effect}.wav"
                
                if environment_file.exists() and environment_file.stat().st_size > 0:
                    print(f"⚡ Cache HIT environment: {environment_file.name}")
                    if play_now:
                        self._publish_audio_event(environment_file, "none", action_code)
                    return str(environment_file)
                
                # Environment n'existe pas → créer skin + cet environment
                print(f"🔧 Cache MISS environment {effect} → génération via fx_manager")
                
                # Créer skin + cet environment spécifique
                success = self.fx_manager.create_for(str(brut_file), effects="all")
                print(f"🎯 Effet demandé: {effect} (tous générés)")
                
                # Vérifier si l'environment a été créé
                if environment_file.exists() and environment_file.stat().st_size > 0:
                    if play_now:
                        self._publish_audio_event(environment_file, "none", action_code)
                    return str(environment_file)
                else:
                    # Fallback vers skin si environment échoue
                    skin_file = brut_file.parent / "skin.wav"
                    if skin_file.exists():
                        print(f"⚠️ Environment {effect} échoué → lecture skin")
                        if play_now:
                            self._publish_audio_event(skin_file, "none", action_code)
                        return str(skin_file)
                    else:
                        # Fallback final vers brut
                        print(f"⚠️ Skin + environment échoués → lecture brut")
                        if play_now:
                            self._publish_audio_event(brut_file, "none", action_code)
                        return str(brut_file)
        
        except Exception as e:
            print(f"❌ Erreur VCZ.create: {e}")
            import traceback
            traceback.print_exc()
            self._handle_error(effect, play_now)
            return ""
    
    def _get_cached_file_path(self, engine: str, action_code: str, text: str) -> Path:
        """
        Calcule le chemin du fichier en cache avec structure par voix
        
        Returns:
            Path: Chemin du fichier audio (peut ne pas exister)
        """
        # Nettoyer le nom de fichier avec longueur maximale Windows
        clean_filename = self._sanitize_filename(text, max_chars=200)  # ✅ MODIFIÉ: 200 au lieu de 25
        
        # ✅ NOUVEAU: Récupérer la voix actuelle selon le moteur
        voice_name = self._get_current_voice(engine)
        
        # ✅ NOUVEAU: Ajouter préfixe rate/pitch pour EdgeTTS
        prefix = self._get_voice_prefix(engine)
        if prefix:
            clean_filename = f"{prefix}_{clean_filename}"
        
        # Structure: ./sound/output_sound/{engine}/{voice}/{action_code}/{filename}.wav
        cached_file = (
            self.base_output_path / 
            engine / 
            self._sanitize_voice_name(voice_name) / 
            action_code / 
            f"{clean_filename}.wav"
        )
        
        return cached_file
    
    def _get_current_voice(self, engine: str) -> str:
        """Récupère le nom de la voix configurée pour un moteur donné"""
        voice_mapping = {
            "piper": "piper.default_voice",
            "openai": "openAI.assistant_voice",
            "edgetts": "edgetts.default_voice",  # ✅ CORRIGÉ: edgetts au lieu de edege-tts
        }
        
        config_key = voice_mapping.get(engine, f"{engine}.default_voice")
        voice_name = self.config_manager.get(config_key, "default")
        
        return voice_name
    
    def _sanitize_voice_name(self, voice_name: str) -> str:
        """
        Nettoie un nom de voix pour le système de fichiers
        
        Args:
            voice_name: Nom brut de la voix (ex: "fr-FR-DeniseNeural")
            
        Returns:
            str: Nom nettoyé (ex: "deniseneural")
        """
        # "fr-FR-DeniseNeural" → "deniseneural"
        clean = voice_name.lower()
        clean = clean.replace("-", "")
        clean = clean.replace("_", "")
        clean = clean.replace(".", "")
        
        # Garder seulement les lettres et chiffres
        clean = ''.join(c for c in clean if c.isalnum())
        
        return clean[:15]  # Limiter la longueur
    
    def _sanitize_filename(self, text: str, max_chars: int = 200) -> str:  # ✅ MODIFIÉ: 200 par défaut
        """
        Nettoie un texte pour l'utiliser comme nom de fichier
        Limite Windows: 260 caractères pour le chemin complet, on garde une marge
        
        Args:
            text: Texte à nettoyer
            max_chars: Nombre maximum de caractères (200 = sécurisé pour Windows)
            
        Returns:
            str: Nom de fichier sécurisé
        """
        import re
        
        # Remplacer les caractères interdits par des underscores
        clean = re.sub(r'[<>:"/\\|?*]', '_', text)
        
        # Remplacer les espaces par des underscores
        clean = clean.replace(' ', '_')
        
        # Supprimer les caractères de contrôle
        clean = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean)
        
        # Limiter la longueur (garder marge pour chemin complet + extension)
        if len(clean) > max_chars:
            clean = clean[:max_chars]
        
        # Éviter les noms réservés Windows
        reserved = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
        if clean.upper() in reserved:
            clean = f"_{clean}"
        
        # S'assurer qu'on ne finit pas par un point
        clean = clean.rstrip('.')
        
        return clean or "audio"  # Fallback si le texte était vide
    
    def _get_voice_prefix(self, engine: str) -> str:
        """
        Génère un préfixe basé sur les paramètres de voix pour EdgeTTS
        """
        if engine != "edgetts":
            return ""
        
        try:
            # ✅ RÉCUPÉRER LES VALEURS ENTIÈRES
            rate_int = self.config_manager.get("edgetts.rate", 0)
            pitch_int = self.config_manager.get("edgetts.pitch", 0)
            
            print(f"🔧 Debug prefix - Rate: {rate_int}, Pitch: {pitch_int}")
            
            # ✅ GÉNÉRATION SIMPLIFIÉE DU PRÉFIXE
            if rate_int == 0 and pitch_int == 0:
                return ""  # Pas de préfixe si tout est par défaut
            
            rate_prefix = f"r{rate_int:+d}" if rate_int != 0 else "r0"
            pitch_prefix = f"p{pitch_int:+d}" if pitch_int != 0 else "p0"
            
            prefix = f"{rate_prefix}_{pitch_prefix}"
            print(f"✅ Préfixe final: '{prefix}'")
            return prefix
            
        except Exception as e:
            print(f"⚠️ Erreur génération préfixe voix: {e}")
            return ""
          
    def _generate_and_cache_tts(self, engine: str, action_code: str, text: str, output_file: Path) -> bool:
        """
        Génère uniquement le TTS brut (sans effets) vers la structure répertoire/brut.wav
        
        Args:
            engine: Moteur TTS à utiliser
            action_code: Code d'action
            text: Texte à synthétiser
            output_file: Fichier de sortie PRÉVU (sera converti en répertoire/brut.wav)
            
        Returns:
            bool: True si succès
        """
        print(f"🏗️ Génération TTS {engine} pour action '{action_code}'...")
        
        # 🔧 FIX: Convertir vers structure répertoire/brut.wav
        if output_file.name != "brut.wav":
            # r0_p-10_phrase.wav → r0_p-10_phrase/brut.wav
            audio_dir = output_file.parent / output_file.stem
            actual_output = audio_dir / "brut.wav"
            
            print(f"🔄 Conversion: {output_file.name} → {actual_output.relative_to(output_file.parent.parent)}")
        else:
            actual_output = output_file
        
        # Créer le dossier si nécessaire
        actual_output.parent.mkdir(parents=True, exist_ok=True)
        
        # Appeler le bon moteur TTS vers le bon chemin
        success = False
        if engine in self.engines:
            engine_instance = self.engines[engine]
            success = engine_instance.generate(text, actual_output)  # ← Générer vers brut.wav
        else:
            print(f"❌ Moteur TTS inconnu: {engine}")
            return False
        
        if success and actual_output.exists() and actual_output.stat().st_size > 0:
            print(f"✅ TTS généré: {actual_output} ({actual_output.stat().st_size} bytes)")
            
            # 🔧 FIX: Mettre à jour self reference pour cohérence
            # Maintenant le brut_file devrait pointer vers le bon brut.wav
            return True
        else:
            print(f"❌ Échec génération TTS {engine}")
            return False
    
    def _get_effect_file_path(self, brut_file: Path, effect: str) -> Path:
        """Calcule le chemin du fichier avec effet"""
        if effect == "none":
            return brut_file
        
        # Convertir la structure fichier → répertoire si nécessaire
        if brut_file.name != "brut.wav":
            # phrase.wav → phrase/brut.wav
            audio_dir = brut_file.parent / brut_file.stem
            
            # 🔧 FIX: Créer TOUS les répertoires parents
            audio_dir.mkdir(parents=True, exist_ok=True)
            
            # Déplacer le fichier original vers brut.wav si nécessaire
            brut_path = audio_dir / "brut.wav"
            if brut_file.exists() and not brut_path.exists():
                import shutil
                shutil.move(str(brut_file), str(brut_path))
            
            # Retourner le chemin effet dans le nouveau répertoire
            return audio_dir / f"{effect}.wav"
        else:
            # Déjà en format répertoire phrase/brut.wav → phrase/effect.wav
            return brut_file.parent / f"{effect}.wav"
    
    def _schedule_effect_generation(self, brut_path: str, effect: str):
        """
        Programme la génération d'un effet via le bus d'événements
        
        Args:
            brut_path: Chemin du fichier brut source
            effect: Type d'effet à générer ("ship", "city", "helmet")
        """
        event = {
            "name": "fx.generate_effect",
            "state": "request",
            "payload": {
                "source_path": brut_path,
                "effect_type": effect,
                "priority": "normal",
                "force_remake": False,
                "requester": "vocalizer"
            }
        }
        
        print(f"📨 Bus: Programmation génération effet {effect}")
        self.event_bus.publish(event)
    
    def _schedule_all_variants_generation(self, brut_path: str):
        """
        Programme la génération de toutes les variantes d'effets via le bus
        
        Args:
            brut_path: Chemin du fichier brut source
        """
        available_effects = ["ship", "city", "helmet"]
        
        event = {
            "name": "fx.generate_all_variants",
            "state": "request",
            "payload": {
                "source_path": brut_path,
                "effects": available_effects,
                "priority": "low",  # Basse priorité pour génération proactive
                "force_remake": False,
                "requester": "vocalizer"
            }
        }
        
        print(f"📨 Bus: Programmation génération toutes variantes ({len(available_effects)} effets)")
        self.event_bus.publish(event)

    def _publish_audio_event(self, audio_file: Path, effect: str, source: str):
        """
        Publie un événement audio sur le bus
        
        Args:
            audio_file: Fichier audio à jouer
            effect: Effet SoundManager à appliquer ("none" si déjà traité)
            source: Source de la demande
        """
        # Chemin relatif pour l'événement
        relative_path = str(audio_file).replace("\\", "/")
        if not relative_path.startswith("./"):
            relative_path = f"./{relative_path}"
        
        event = {
            "name": "audio.play_file",
            "state": "request",
            "payload": {
                "file": relative_path,
                "effect": effect,  # "none" pour fichiers déjà traités, sinon effet SoundManager
                "source": source,
                "priority": "normal"
            }
        }
        
        print(f"🔊 Publication audio: {audio_file.name} (effet SoundManager: {effect})")
        self.event_bus.publish(event)
    
    def _handle_error(self, effect: str, play_now: bool):
        """
        Gère les erreurs de synthèse vocale
        
        Args:
            effect: Effet demandé
            play_now: Si on doit jouer un son d'erreur
        """
        if not play_now:
            return
        
        # Vérifier le mode silence
        silence_mode = self.config_manager.get("tts.silence_on_error", False)
        if silence_mode:
            print("🔇 Mode silence activé - pas de son d'erreur")
            return
        
        # Jouer le son d'erreur
        error_sound = self.config_manager.get("sound_bank.error_sound", 
                                            "./sound/output_sound/sound_bank/error_bip.wav")
        error_file = Path(error_sound)
        
        if error_file.exists():
            print(f"🚨 Son d'erreur: {error_file.name}")
            self._publish_audio_event(error_file, "none", "vocalizer_error")
        else:
            print(f"❌ Son d'erreur introuvable: {error_file}")


# === MOTEURS TTS ===

class BaseEngine(ABC):
    """Interface de base pour tous les moteurs TTS"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    @abstractmethod
    def generate(self, text: str, output_file: Path) -> bool:
        """Génère un fichier audio depuis du texte"""
        pass


class PiperEngine(BaseEngine):
    """Moteur TTS Piper (local, gratuit)"""
    
    def generate(self, text: str, output_file: Path) -> bool:
        """
        Génère un fichier audio avec Piper
        
        Args:
            text: Texte à synthétiser
            output_file: Fichier de sortie
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            print(f"🤖 Génération Piper: '{text[:50]}...'")
            
            # Configuration depuis config.yaml
            voice_name = self.config_manager.get("piper.default_voice", "gilles")
            models_path = Path(self.config_manager.get("piper.model_path", "./core/models_tts/piper/"))
            
            print(f"🎤 Voix: {voice_name}")
            print(f"📁 Modèles: {models_path}")
            
            # Rechercher le modèle correspondant à la voix
            model_file = self._find_model_file(models_path, voice_name)
            if not model_file:
                print(f"❌ Modèle Piper introuvable pour la voix: {voice_name}")
                return False
            
            print(f"✅ Modèle trouvé: {model_file.name}")
            
            # Commande Piper
            cmd = [
                "piper",
                "--model", str(model_file),
                "--output_file", str(output_file)
            ]
            
            print(f"🔧 Commande: {' '.join(cmd)}")
            
            # Exécuter Piper avec timeout
            process = subprocess.run(
                cmd,
                input=text,
                text=True,
                capture_output=True,
                timeout=30,
                cwd=Path.cwd()
            )
            
            if process.returncode == 0:
                if output_file.exists() and output_file.stat().st_size > 0:
                    print(f"✅ Piper: Génération réussie ({output_file.stat().st_size} bytes)")
                    return True
                else:
                    print("❌ Piper: Fichier vide ou inexistant")
                    return False
            else:
                print(f"❌ Piper: Erreur {process.returncode}")
                if process.stderr:
                    print(f"   STDERR: {process.stderr}")
                if process.stdout:
                    print(f"   STDOUT: {process.stdout}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Piper: Timeout (30s)")
            return False
        except FileNotFoundError:
            print("❌ Piper: Exécutable 'piper' introuvable")
            print("💡 Installez Piper: https://github.com/rhasspy/piper")
            return False
        except Exception as e:
            print(f"❌ Piper: Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _find_model_file(self, models_path: Path, voice_name: str) -> Path | None:
        """
        Recherche le fichier modèle correspondant à la voix
        
        Args:
            models_path: Dossier des modèles
            voice_name: Nom de la voix (ex: "gilles")
            
        Returns:
            Path: Chemin du modèle .onnx ou None si introuvable
        """
        if not models_path.exists():
            print(f"❌ Dossier modèles inexistant: {models_path}")
            return None
        
        # Rechercher tous les fichiers .onnx contenant le nom de la voix
        pattern = f"*{voice_name}*.onnx"
        model_files = list(models_path.rglob(pattern))
        
        if not model_files:
            print(f"❌ Aucun modèle trouvé pour '{voice_name}' dans {models_path}")
            
            # Lister les modèles disponibles
            all_models = list(models_path.rglob("*.onnx"))
            if all_models:
                print("📄 Modèles disponibles:")
                for model in all_models[:5]:  # Limiter l'affichage
                    print(f"   - {model.name}")
            else:
                print("📄 Aucun modèle .onnx trouvé")
                print("💡 Utilisez le bouton 'Télécharger' dans la config")
            
            return None
        
        # Prendre le premier modèle trouvé
        selected_model = model_files[0]
        
        # Vérifier que le fichier de config existe aussi
        config_file = selected_model.with_suffix('.onnx.json')
        if not config_file.exists():
            print(f"⚠️ Fichier config manquant: {config_file.name}")
            print("💡 Téléchargez le modèle complet avec sa config")
        
        return selected_model

# /core/vocalizer.py
# Ajouter après PiperEngine

class OpenAIEngine(BaseEngine):
    """Moteur TTS OpenAI (payant, haute qualité)"""
    
    def generate(self, text: str, output_file: Path) -> bool:
        """
        Génère un fichier audio avec OpenAI TTS
        
        Args:
            text: Texte à synthétiser
            output_file: Fichier de sortie
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            print(f"🤖 Génération OpenAI TTS: '{text[:50]}...'")
            
            # Configuration depuis config.yaml
            api_key = self.config_manager.get("openAI.apiKey", "")
            voice_name = self.config_manager.get("openAI.assistant_voice", "nova")
            model = self.config_manager.get("openAI.tts_model", "tts-1")
            
            print(f"🎤 Voix: {voice_name}")
            print(f"📡 Modèle: {model}")
            
            # Vérifier la clé API
            if not api_key or api_key.startswith("xxxx") or api_key.startswith("sk-xxx"):
                print("❌ Clé API OpenAI manquante ou invalide")
                print("💡 Configurez votre clé API dans la section Sécurité")
                return False
            
            # Import OpenAI
            try:
                import openai
            except ImportError:
                print("❌ Module OpenAI non installé")
                print("💡 Installez avec: pip install openai")
                return False
            
            # Configuration du client OpenAI
            client = openai.OpenAI(api_key=api_key)
            
            # Paramètres de la requête
            request_params = {
                "model": model,
                "voice": voice_name,
                "input": text,
                "response_format": "wav"  # Format WAV pour compatibilité
            }
            
            print(f"🔧 Requête OpenAI: {request_params}")
            
            # Appel API OpenAI TTS
            with client.audio.speech.with_streaming_response.create(**request_params) as response:
                if response.status_code == 200:
                    # Écrire le contenu audio dans le fichier
                    with open(output_file, 'wb') as audio_file:
                        for chunk in response.iter_bytes(chunk_size=1024):
                            audio_file.write(chunk)
                    
                    # Vérifier que le fichier a été créé
                    if output_file.exists() and output_file.stat().st_size > 0:
                        print(f"✅ OpenAI TTS: Génération réussie ({output_file.stat().st_size} bytes)")
                        return True
                    else:
                        print("❌ OpenAI TTS: Fichier vide ou non créé")
                        return False
                else:
                    print(f"❌ OpenAI TTS: Erreur HTTP {response.status_code}")
                    return False
                    
        except openai.AuthenticationError:
            print("❌ OpenAI TTS: Clé API invalide")
            print("💡 Vérifiez votre clé API OpenAI")
            return False
        except openai.RateLimitError:
            print("❌ OpenAI TTS: Limite de taux dépassée")
            print("💡 Attendez avant de refaire une requête")
            return False
        except openai.APIError as e:
            print(f"❌ OpenAI TTS: Erreur API: {e}")
            return False
        except Exception as e:
            print(f"❌ OpenAI TTS: Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return False
# === AUTRES MOTEURS (à implémenter plus tard) ===


class EdgeTTSEngine(BaseEngine):
    """Moteur TTS Edge-TTS (gratuit, Microsoft, haute qualité)"""
    
    def generate(self, text: str, output_file: Path) -> bool:
        """
        Génère un fichier audio avec Edge-TTS
        
        Args:
            text: Texte à synthétiser
            output_file: Fichier de sortie
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            print(f"🌐 Génération Edge-TTS: '{text[:50]}...'")
            
            # Configuration depuis config.yaml
            voice_name = self.config_manager.get("edgetts.default_voice", "fr-FR-DeniseNeural")
            rate_int = self.config_manager.get("edgetts.rate", 0)      # ✅ Entier
            pitch_int = self.config_manager.get("edgetts.pitch", 0)    # ✅ Entier  
            volume_int = self.config_manager.get("edgetts.volume", 0)  # ✅ Entier
            
            # ✅ CONVERSION VERS FORMAT EDGETTS
            rate = f"+{rate_int}%" if rate_int >= 0 else f"{rate_int}%"
            pitch = f"+{pitch_int}Hz" if pitch_int >= 0 else f"{pitch_int}Hz"
            volume = f"+{volume_int}%" if volume_int >= 0 else f"{volume_int}%"
            
            
            print(f"🎤 Voix: {voice_name}")
            print(f"⚡ Vitesse: {rate}, Pitch: {pitch}, Volume: {volume}")
            
            # Import edge-tts
            try:
                import edge_tts
                import asyncio
                import concurrent.futures  # ✅ AJOUTÉ: Import manquant
            except ImportError:
                print("❌ Module edge-tts non installé")
                print("💡 Installez avec: pip install edge-tts")
                return False
            
            # Créer le dossier si nécessaire
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Fonction async pour générer l'audio
            async def _generate_audio():
                # Configuration de la voix avec paramètres SSML
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=voice_name,
                    rate=rate,
                    pitch=pitch,
                    volume=volume
                )
                
                # Générer et sauvegarder
                await communicate.save(str(output_file))
            
            # ✅ SOLUTION ULTRA-SIMPLE : Toujours forcer une nouvelle boucle propre
            try:
                # Fermer toute boucle existante dans ce thread si elle existe
                try:
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        loop.close()
                except:
                    pass
                
                # Créer et utiliser une nouvelle boucle propre
                asyncio.set_event_loop(asyncio.new_event_loop())
                asyncio.run(_generate_audio())
                
            except Exception as async_error:
                print(f"❌ Erreur async EdgeTTS: {async_error}")
                return False
            
            # Vérifier que le fichier a été créé
            if output_file.exists() and output_file.stat().st_size > 0:
                print(f"✅ Edge-TTS: Génération réussie ({output_file.stat().st_size} bytes)")
                return True
            else:
                print("❌ Edge-TTS: Fichier vide ou non créé")
                return False
                
        except Exception as e:
            print(f"❌ Edge-TTS: Erreur inattendue: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def list_voices(self) -> list:
        """
        Récupère la liste des voix disponibles
        
        Returns:
            list: Liste des voix avec leurs informations
        """
        try:
            import edge_tts
            
            voices = await edge_tts.list_voices()
            
            # Filtrer pour les voix françaises si configuré
            language_filter = self.config_manager.get("edgetts.language_filter", "fr")
            if language_filter:
                voices = [v for v in voices if v['Locale'].startswith(language_filter)]
            
            return voices
            
        except Exception as e:
            print(f"❌ Erreur listage voix Edge-TTS: {e}")
            return []
    
    def _generate_skin_from_brut(self, brut_file: Path, skin_file: Path) -> bool:
        """Génère le fichier skin depuis le fichier brut"""
        try:
            # Récupérer les paramètres skin depuis la config
            skin_params = self._get_current_skin_params()
            
            print(f"🎨 Paramètres skin: {skin_params}")
            
            # Publier événement de génération skin
            skin_event = {
                "name": "skin.generate",
                "state": "request",
                "payload": {
                    "source_path": str(brut_file),
                    "target_path": str(skin_file),
                    "skin_params": skin_params,
                    "requester": "vocalizer_skin_layer"
                }
            }
            
            # Publier et attendre (synchrone pour le test)
            print(f"📨 Bus: Publication événement skin.generate")
            self.event_bus.publish(skin_event)
            
            # Attendre que le skin soit généré (polling simple)
            import time
            max_wait = 10  # 10 secondes max
            wait_time = 0
            
            print(f"⏳ Attente génération skin (max {max_wait}s)...")
            while not skin_file.exists() and wait_time < max_wait:
                time.sleep(0.5)
                wait_time += 0.5
                
            if skin_file.exists() and skin_file.stat().st_size > 0:
                print(f"✅ Skin généré: {skin_file.name}")
                return True
            else:
                print(f"❌ Timeout génération skin après {max_wait}s")
                return False
                
        except Exception as e:
            print(f"❌ Erreur génération skin: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_current_skin_params(self) -> dict:
        """Récupère les paramètres skin actuels depuis la config"""
        return {
            "pitch": self.config_manager.get("effects.skin.pitch", 0),
            "speed": self.config_manager.get("effects.skin.speed", 0),
            "helium": self.config_manager.get("effects.skin.helium", 0),
            "metallic": self.config_manager.get("effects.skin.metallic", 0),
            "robotic": self.config_manager.get("effects.skin.robotic", 0),
            "distortion": self.config_manager.get("effects.skin.distortion", 0),
            "vocoder": self.config_manager.get("effects.skin.vocoder", 0),
            "hash": self.config_manager.get("effects.skin.hash", 0),
            "reverb": self.config_manager.get("effects.skin.reverb", 0),
            "echo": self.config_manager.get("effects.skin.echo", 0),
            "dry_wet": self.config_manager.get("effects.skin.dry_wet", 100)
        }