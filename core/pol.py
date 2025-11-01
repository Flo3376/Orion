"""
Module POL (Print Or Log)
Système de logging par module avec gestion des niveaux et modes d'affichage

=====================================================
RAPPEL NIVEAUX POL - Print Or Log
=====================================================

UTILISATION :
from core.pol import create_pol
pol = create_pol(source_id=XX)  # XX = ID libre de ton choix
pol.write(niveau, "message", mode)

NIVEAUX DISPONIBLES :
1 = LEGER    - Étapes intéressantes, messages manuels importants
               Ex: "Démarrage module", "Configuration chargée"

2 = WARNING  - Ça catouille mais pas grave, exceptions gérées
               Ex: "Fichier manquant (utilisation défaut)", "Timeout réseau"

3 = ERROR    - On a un souci, erreurs importantes
               Ex: "Échec connexion base", "Fichier corrompu"

4 = PARANO   - On surveille tout, debug détaillé
               Ex: "Variable X=42", "Entrée fonction avec params Y"

5 = HABILLAGE- Sessions, séparateurs, structure
               Ex: "=== SESSION DÉMARRÉE ===", "--- FIN MODULE ---"

MODES D'AFFICHAGE :
"log"        - Écrit seulement dans logs/orion.log (par défaut)
"log+print"  - Écrit dans le log ET affiche sur console

EXEMPLES :
pol.write(1, "Module audio initialisé", "log+print")
pol.write(2, "Port audio par défaut utilisé")  # mode="log" par défaut
pol.write(3, "Impossible de charger le driver audio", "log+print")
pol.write(4, "Valeur buffer_size=1024")
pol.write(5, "=== DÉBUT INITIALISATION AUDIO ===", "log+print")

NOTE : MUET n'existe pas comme niveau d'écriture !
MUET sera un filtre dans l'interface pour masquer/afficher les logs
=====================================================
"""

import os
from datetime import datetime
from pathlib import Path
import threading


class POLLogger:
    """Logger POL pour un module spécifique"""
    
    def __init__(self, source_id, log_file_path="logs/orion.log"):
        self.source_id = source_id
        self.log_file_path = log_file_path
        self._lock = threading.Lock()  # Thread-safe pour écriture
        
        # Niveaux disponibles (MUET retiré - c'est un filtre d'affichage interface)
        self.LEVELS = {
            1: "LEGER", 
            2: "WARNING",
            3: "ERROR",
            4: "PARANO",
            5: "HABILLAGE"
        }
        
        # Modes disponibles
        self.MODES = ["log", "log+print"]
    
    def write(self, level, message, mode="log"):
        """
        Fonction principale POL simplifiée
        
        Args:
            level (int): Niveau de log (1-5)
            message (str): Message à logger
            mode (str): "log" ou "log+print"
        """
        try:
            # Validation des paramètres
            if level not in self.LEVELS:
                print(f"⚠️ POL: Niveau invalide {level}, utilisation du niveau 1 (LEGER)")
                level = 1
                
            if mode not in self.MODES:
                print(f"⚠️ POL: Mode invalide '{mode}', utilisation du mode 'log'")
                mode = "log"
                
            # Créer la ligne de log
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{level}][{self.source_id:02d}][{timestamp}]{message}"
            
            # Écrire dans le fichier log
            self._write_to_file(log_line)
            
            # Afficher sur console si demandé
            if mode == "log+print":
                level_name = self.LEVELS[level]
                print(f"[{level_name}][{self.source_id:02d}] {message}")
                
        except Exception as e:
            # Fallback en cas d'erreur POL
            print(f"❌ Erreur POL: {e}")
            print(f"🔄 Message original: {message}")
    
    def _write_to_file(self, log_line):
        """
        Écrit une ligne dans le fichier log de façon thread-safe
        
        Args:
            log_line (str): Ligne formatée à écrire
        """
        try:
            with self._lock:
                # S'assurer que le répertoire existe
                log_path = Path(self.log_file_path)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Écrire la ligne
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(log_line + '\n')
                    
        except Exception as e:
            print(f"❌ Erreur écriture log: {e}")


def create_pol(source_id, log_file_path="logs/orion.log"):
    """
    Créer une instance POL pour un module
    
    Args:
        source_id (int): Identifiant unique du module/source
        log_file_path (str): Chemin vers le fichier de log
        
    Returns:
        POLLogger: Instance POL configurée pour ce module
        
    Example:
        # Dans un module
        from core.pol import create_pol
        pol = create_pol(source_id=22)
        
        pol.write(1, "Démarrage module", "log+print")  # LEGER avec affichage
        pol.write(3, "Erreur critique")                # ERROR log seulement
        pol.write(4, "Debug variable X=42", "log")     # PARANO log seulement
    """
    return POLLogger(source_id, log_file_path)


# Test du module si exécuté directement
if __name__ == "__main__":
    print("🧪 Test du module POL simplifié")
    
    # Créer une instance de test
    pol = create_pol(source_id=99)
    
    # Tester tous les niveaux et modes
    pol.write(5, "=== TEST POL DÉMARRÉ ===", "log+print")
    pol.write(1, "Test niveau LEGER", "log+print")
    pol.write(2, "Test niveau WARNING", "log")
    pol.write(3, "Test niveau ERROR", "log+print") 
    pol.write(4, "Test niveau PARANO", "log")
    pol.write(5, "=== TEST POL TERMINÉ ===", "log+print")
    
    print("✅ Test terminé - Vérifiez le fichier logs/orion.log")