"""
📚 Lexique Manager - Gestionnaire du lexique de commandes vocales
================================================================

Module de gestion du fichier lexique.yaml contenant :
- Actions et leurs variantes de reconnaissance
- Réponses vocales associées
- Interactions (clavier, souris, spotify, etc.)
- Catégories et effets audio
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import random

@dataclass
class LexiqueAction:
    """Représente une action du lexique"""
    root: str
    cat: str                    # Catégorie (swan, ship, music, etc.)
    effect: str                 # Effet audio (casque, vaisseau, none)
    questions: List[str]        # Phrases de reconnaissance
    responses: List[str]        # Réponses possibles
    description: str            # Description de l'action
    
    # Ambiance
    ambiance_player: str        # Lecteur (spotify, local, none)
    ambiance_track: str         # Piste/playlist
    
    # Interaction
    interact_output: str        # Type de sortie (keyboard, mouse, none)
    interact_type: str          # Type d'action (combo, phrase, sequence, cyclique)
    interact_input: str         # Commande à exécuter

class LexiqueManager:
    """Gestionnaire du lexique de commandes vocales"""
    
    def __init__(self, lexique_path: str = "./core/config/lexique.yaml"):
        self.lexique_path = Path(lexique_path)
        self.actions: Dict[str, LexiqueAction] = {}
        self.global_config: Dict[str, Any] = {}
        self.categories: Dict[str, List[str]] = {}  # cat -> [action_names]
        
        # Statistiques
        self.stats = {
            "total_actions": 0,
            "total_questions": 0,
            "total_responses": 0,
            "categories_count": 0,
            "last_reload": None
        }
        
        self.load_lexique()
    
    def load_lexique(self) -> bool:
        """
        Charge le fichier lexique.yaml
        
        Returns:
            bool: True si chargement réussi
        """
        
        try:
            if not self.lexique_path.exists():
                print(f"❌ Fichier lexique introuvable: {self.lexique_path}")
                return False
            
            with open(self.lexique_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Extraire la config globale
            self.global_config = data.get("global", {})
            
            # Parser les actions
            self.actions.clear()
            self.categories.clear()
            
            for action_name, action_data in data.items():
                if action_name == "global":
                    continue  # Ignorer la section globale
                
                # Parser l'action
                action = self._parse_action(action_name, action_data)
                if action:
                    self.actions[action_name] = action
                    
                    # Organiser par catégorie
                    if action.cat not in self.categories:
                        self.categories[action.cat] = []
                    self.categories[action.cat].append(action_name)
            
            # Mettre à jour les statistiques
            self._update_stats()
            
            print(f"✅ Lexique chargé: {self.stats['total_actions']} actions, {self.stats['categories_count']} catégories")
            return True
            
        except Exception as e:
            print(f"❌ Erreur chargement lexique: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_action(self, action_name: str, action_data: Dict) -> Optional[LexiqueAction]:
        """Parse une action du YAML vers LexiqueAction"""
        
        try:
            # Données principales
            root = action_data.get("root", action_name)
            cat = action_data.get("cat", "unknown")
            effect = action_data.get("effect", "none")
            
            # Ambiance
            ambiance = action_data.get("ambiance", {})
            ambiance_player = ambiance.get("player", "none")
            ambiance_track = ambiance.get("track", "")
            
            # Rules (première rule seulement pour l'instant)
            rules = action_data.get("rules", [])
            if not rules:
                print(f"⚠️ Action sans rules: {action_name}")
                return None
            
            first_rule = rules[0]  # Prendre la première rule
            
            # Extraction de la rule
            description = first_rule.get("description", action_name)
            questions = first_rule.get("questions", [])
            responses = first_rule.get("responses", [])
            
            # Interaction
            interact = first_rule.get("interact", {})
            interact_output = interact.get("output", "none")
            interact_type = interact.get("type", "none")
            interact_input = interact.get("action_input", "")
            
            # Nettoyer les questions/réponses (enlever les espaces)
            questions = [q.strip() for q in questions if q.strip()]
            responses = [r.strip() for r in responses if r.strip()]
            
            return LexiqueAction(
                root=root,
                cat=cat,
                effect=effect,
                questions=questions,
                responses=responses,
                description=description,
                ambiance_player=ambiance_player,
                ambiance_track=ambiance_track,
                interact_output=interact_output,
                interact_type=interact_type,
                interact_input=interact_input
            )
            
        except Exception as e:
            print(f"❌ Erreur parsing action {action_name}: {e}")
            return None
    
    def _update_stats(self):
        """Met à jour les statistiques"""
        import time
        
        self.stats["total_actions"] = len(self.actions)
        self.stats["total_questions"] = sum(len(action.questions) for action in self.actions.values())
        self.stats["total_responses"] = sum(len(action.responses) for action in self.actions.values())
        self.stats["categories_count"] = len(self.categories)
        self.stats["last_reload"] = time.time()
    
    # =========================================================================
    # 🎯 API PUBLIQUE
    # =========================================================================
    
    def get_action(self, action_name: str) -> Optional[LexiqueAction]:
        """Récupère une action par son nom"""
        return self.actions.get(action_name)
    
    def get_actions_by_category(self, category: str) -> List[LexiqueAction]:
        """Récupère toutes les actions d'une catégorie"""
        action_names = self.categories.get(category, [])
        return [self.actions[name] for name in action_names if name in self.actions]
    
    def get_random_response(self, action_name: str) -> Optional[str]:
        """Récupère une réponse aléatoire pour une action"""
        action = self.get_action(action_name)
        if action and action.responses:
            return random.choice(action.responses)
        return None
    
    def find_action_by_question(self, question: str) -> Optional[str]:
        """
        Trouve une action correspondant à une question (recherche exacte)
        
        Args:
            question: Question à chercher
            
        Returns:
            str: Nom de l'action trouvée, None sinon
        """
        question_lower = question.lower().strip()
        
        for action_name, action in self.actions.items():
            for q in action.questions:
                if q.lower().strip() == question_lower:
                    return action_name
        
        return None
    
    def search_actions(self, query: str, category: Optional[str] = None) -> List[str]:
        """
        Recherche d'actions par mots-clés
        
        Args:
            query: Mots-clés à chercher
            category: Catégorie à filtrer (optionnel)
            
        Returns:
            List[str]: Noms des actions trouvées
        """
        query_lower = query.lower()
        results = []
        
        actions_to_search = self.actions.items()
        if category:
            action_names = self.categories.get(category, [])
            actions_to_search = [(name, self.actions[name]) for name in action_names if name in self.actions]
        
        for action_name, action in actions_to_search:
            # Chercher dans le nom, description, questions
            if (query_lower in action_name.lower() or
                query_lower in action.description.lower() or
                any(query_lower in q.lower() for q in action.questions)):
                results.append(action_name)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du lexique"""
        return self.stats.copy()
    
    def get_categories(self) -> List[str]:
        """Retourne la liste des catégories"""
        return list(self.categories.keys())
    
    def reload(self) -> bool:
        """Recharge le lexique depuis le fichier"""
        print("🔄 Rechargement du lexique...")
        return self.load_lexique()

# =============================================================================
# 🎯 INSTANCE GLOBALE
# =============================================================================

# Instance globale du gestionnaire (singleton pattern)
_lexique_manager = None

def get_lexique_manager(lexique_path: str = "./core/config/lexique.yaml") -> LexiqueManager:
    """Retourne l'instance globale du gestionnaire de lexique"""
    global _lexique_manager
    
    if _lexique_manager is None:
        _lexique_manager = LexiqueManager(lexique_path)
    
    return _lexique_manager

# Fonctions utilitaires
def get_action(action_name: str) -> Optional[LexiqueAction]:
    """Interface simplifiée pour récupérer une action"""
    return get_lexique_manager().get_action(action_name)

def get_random_response(action_name: str) -> Optional[str]:
    """Interface simplifiée pour récupérer une réponse aléatoire"""
    return get_lexique_manager().get_random_response(action_name)

def find_action_by_question(question: str) -> Optional[str]:
    """Interface simplifiée pour trouver une action par question"""
    return get_lexique_manager().find_action_by_question(question)