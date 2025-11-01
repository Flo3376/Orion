"""
Module de gestion de la rotation des logs
Fonctionnalité : Archive les sessions précédentes à l'ouverture
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def rotate_log_on_startup(log_file_path="logs/orion.log"):
    """
    Effectue la rotation du fichier de log au démarrage
    
    Args:
        log_file_path (str): Chemin vers le fichier de log principal
        
    Returns:
        bool: True si rotation effectuée, False sinon
    """
    try:
        log_path = Path(log_file_path)
        
        # Vérifier si le fichier existe et n'est pas vide
        if not log_path.exists() or log_path.stat().st_size == 0:
            print(f"🔄 Aucune rotation nécessaire - fichier inexistant ou vide")
            return False
        
        # Lire la première ligne pour extraire la date
        with open(log_path, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
        
        # Vérifier si c'est une ligne de session
        if not first_line.startswith("=== SESSION DÉMARRÉE"):
            print(f"🔄 Aucune rotation - première ligne non reconnue: {first_line[:50]}...")
            return False
        
        # Extraire la date de la première ligne
        # Format attendu: "=== SESSION DÉMARRÉE 2025-11-01 11:31:24 ==="
        try:
            date_part = first_line.split("SESSION DÉMARRÉE ")[1].split(" ===")[0]
            session_datetime = datetime.strptime(date_part, "%Y-%m-%d %H:%M:%S")
            
            # Créer le nom du fichier archive
            archive_name = f"session_{session_datetime.strftime('%Y-%m-%d_%H-%M-%S')}.log"
            archive_path = log_path.parent / archive_name
            
            # Renommer le fichier existant
            shutil.move(str(log_path), str(archive_path))
            print(f"🔄 Session précédente archivée: {archive_name}")
            
            return True
            
        except (IndexError, ValueError) as e:
            print(f"❌ Erreur parsing date de session: {e}")
            # En cas d'erreur, on archive quand même avec timestamp actuel
            fallback_name = f"session_corrupted_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
            fallback_path = log_path.parent / fallback_name
            shutil.move(str(log_path), str(fallback_path))
            print(f"🔄 Session corrompue archivée: {fallback_name}")
            return True
            
    except Exception as e:
        print(f"❌ Erreur rotation log: {e}")
        return False


def ensure_log_directory(log_file_path="logs/orion.log"):
    """
    S'assure que le répertoire de logs existe
    
    Args:
        log_file_path (str): Chemin vers le fichier de log
    """
    try:
        log_path = Path(log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"📁 Répertoire de logs vérifié: {log_path.parent}")
    except Exception as e:
        print(f"❌ Erreur création répertoire logs: {e}")


def init_new_session(log_file_path="logs/orion.log"):
    """
    Initialise une nouvelle session de log
    
    Args:
        log_file_path (str): Chemin vers le fichier de log
    """
    try:
        # S'assurer que le répertoire existe
        ensure_log_directory(log_file_path)
        
        # Effectuer la rotation si nécessaire
        rotate_log_on_startup(log_file_path)
        
        # Créer/vider le fichier pour la nouvelle session
        with open(log_file_path, 'w', encoding='utf-8') as f:
            session_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"=== SESSION DÉMARRÉE {session_start} ===\n")
        
        print(f"🚀 Nouvelle session de log initialisée: {log_file_path}")
        return True
        
    except Exception as e:
        print(f"❌ Erreur initialisation session: {e}")
        return False


if __name__ == "__main__":
    # Test du module
    print("🧪 Test du module log_manager")
    result = init_new_session()
    print(f"✅ Résultat: {result}")