"""
📚 Lexique Manager - Gestionnaire du lexique de commandes vocales
"""

import yaml
import xml.etree.ElementTree as ET
import re
import time
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# ✅ DÉFINIR LexiqueAction directement ici
@dataclass
class LexiqueAction:
    """Représente une action du lexique avec toutes ses propriétés"""
    root: str
    cat: str
    effect: str
    questions: List[str]
    responses: List[str]
    description: str
    ambiance_player: str = "none"
    ambiance_track: str = ""
    interact_output: str = "none"
    interact_type: str = "none"
    interact_input: str = ""

class SRGSGenerator:
    """Générateur de grammaires SRGS depuis le lexique avec support des règles dynamiques"""
    
    def __init__(self, lexique_manager, grammar_dir: str = "./core/grammar/"):
        self.lexique_manager = lexique_manager
        self.grammar_dir = Path(grammar_dir)
        self.grammar_dir.mkdir(exist_ok=True)
    
    def generate_all_by_root(self) -> bool:
        """Génère les grammaires SRGS (statiques + dynamiques)"""
        try:
            lexique_data = self.lexique_manager.load_lexique()
            
            if not lexique_data or not isinstance(lexique_data, dict):
                print(f"⚠️ Erreur chargement lexique: {type(lexique_data)} = {lexique_data}")
                return False
            
            print(f"📚 Lexique chargé: {len(lexique_data)} entrées")
            
            # Filtrer les actions valides (exclure 'global')
            actions = {k: v for k, v in lexique_data.items() 
                      if k != 'global' and isinstance(v, dict) and 'root' in v}
            
            if not actions:
                print("⚠️ Aucune action trouvée dans le lexique")
                return False
            
            # Séparer règles statiques et dynamiques
            static_actions = {}
            dynamic_actions = {}
            
            for action_name, action_data in actions.items():
                if action_name.endswith('_x'):
                    dynamic_actions[action_name] = action_data
                else:
                    static_actions[action_name] = action_data
            
            print(f"🎙️ Génération SRGS: {len(static_actions)} statiques + {len(dynamic_actions)} dynamiques")
            
            generated_count = 0
            
            # Générer les règles statiques (comme avant)
            for action_name, action_data in static_actions.items():
                root_name = action_data.get('root')
                if root_name and self._generate_root_grammar(root_name, action_data):
                    generated_count += 1
            
            # Générer les règles dynamiques (nouveau)
            for action_name, action_data in dynamic_actions.items():
                if self._generate_dynamic_grammar(action_name, action_data):
                    generated_count += 1
            
            print(f"✅ {generated_count}/{len(actions)} grammaires générées")
            return generated_count > 0
            
        except Exception as e:
            print(f"❌ Erreur génération grammaires: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _generate_dynamic_grammar(self, action_name: str, action_data: dict) -> bool:
        """Génère une grammaire SRGS pour une règle dynamique (_x)"""
        try:
            # Analyser le type de règle dynamique
            questions = self._extract_questions(action_data)
            dynamic_info = self._analyze_dynamic_patterns(questions)
            
            if dynamic_info["type"] == "numeric":
                return self._generate_numeric_multi_rule(action_name, action_data, dynamic_info)
            else:
                print(f"⚠️ Type dynamique non supporté pour {action_name}: {dynamic_info['type']}")
                return False
                
        except Exception as e:
            print(f"❌ Erreur génération dynamique {action_name}: {e}")
            return False
    
    def _analyze_dynamic_patterns(self, questions: List[str]) -> dict:
        """Analyse les patterns dynamiques dans les questions"""
        patterns = []
        
        for question in questions:
            # Chercher les patterns {xxx}
            found_patterns = re.findall(r'\{([^}]+)\}', question)
            patterns.extend(found_patterns)
        
        # Analyser les patterns trouvés
        for pattern in patterns:
            if pattern.startswith('x_') and pattern.count('_') == 3:
                # Pattern numérique : {x_min_max_step}
                parts = pattern.split('_')
                if len(parts) == 4 and parts[0] == 'x':
                    try:
                        min_val = int(parts[1])
                        max_val = int(parts[2])
                        step_val = int(parts[3])
                        return {
                            "type": "numeric",
                            "pattern": pattern,
                            "min": min_val,
                            "max": max_val,
                            "step": step_val
                        }
                    except ValueError:
                        continue
        
        return {"type": "unknown", "patterns": patterns}
    
    def _generate_numeric_multi_rule(self, action_name: str, action_data: dict, numeric_info: dict) -> bool:
        """Génère UN fichier SRGS avec plusieurs règles pour les valeurs numériques"""
        
        # Extraire les informations numériques
        min_val = numeric_info["min"]
        max_val = numeric_info["max"] 
        step_val = numeric_info["step"]
        pattern = numeric_info["pattern"]
        
        # Générer toutes les valeurs possibles
        values = list(range(min_val, max_val + 1, step_val))
        
        # Questions template depuis le lexique
        questions_template = self._extract_questions(action_data)
        
        # Nom du fichier sans le "_x"
        base_root_name = action_name.replace('_x', '')
        
        # Générer le XML avec règles multiples
        xml_content = self._create_multi_rule_srgs(base_root_name, questions_template, values, pattern, action_data)
        
        # Sauvegarder
        output_path = self.grammar_dir / f"{base_root_name}.xml"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        
        category = action_data.get('cat', 'unknown')
        print(f"✅ Grammaire multi-règles générée: {output_path.name} ({len(values)} valeurs {min_val}-{max_val}, cat: {category})")
        return True
    
    def _create_multi_rule_srgs(self, base_root_name: str, questions_template: List[str], values: List[int], pattern: str, action_data: dict) -> str:
        """Crée le XML SRGS avec plusieurs règles pour chaque valeur"""
        
        # Hotword depuis config
        hotword = self._get_hotword()
        
        # Infos pour les commentaires
        category = action_data.get('cat', 'unknown')
        description = action_data.get('rules', [{}])[0].get('description', f'Commandes {base_root_name}')
        
        # Header XML
        xml_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<grammar version="1.0" xml:lang="fr-FR" mode="voice" root="{base_root_name}" xmlns="http://www.w3.org/2001/06/grammar" tag-format="semantics/1.0">
    <!-- 
        Grammaire multi-règles générée depuis lexique.yaml
        Root: {base_root_name}
        Catégorie: {category}
        Description: {description}
        Valeurs: {len(values)} ({min(values)} à {max(values)} par pas de {values[1] - values[0] if len(values) > 1 else 1})
        Généré le: {time.strftime("%Y-%m-%d %H:%M:%S")}
    -->
    
    <!-- RÈGLE PUBLIQUE PRINCIPALE -->
    <rule id="{base_root_name}" scope="public">
        <tag>out.action=new Object();</tag>
        <item>{hotword}</item>
        <one-of>'''
        
        # Ajouter une option pour chaque valeur
        for value in values:
            xml_content += f'''
            <item>
                <ruleref uri="#{base_root_name}_{value}"/>
                <tag>out.action.action="{base_root_name}_{value}";</tag>
            </item>'''
        
        xml_content += '''
        </one-of>
    </rule>
    '''
        
        # Ajouter les règles privées pour chaque valeur
        for value in values:
            xml_content += f'''
    <!-- RÈGLE POUR VALEUR {value} -->
    <rule id="{base_root_name}_{value}" scope="private">
        <one-of>'''
            
            # Remplacer le pattern dans chaque question
            for question_template in questions_template:
                if question_template.strip():
                    # Remplacer {x_0_100_5} par la valeur en lettres
                    number_word = self._number_to_french(value)
                    question = question_template.replace(f"{{{pattern}}}", number_word)
                    xml_content += f'''
            <item>{question}</item>'''
            
            xml_content += '''
        </one-of>
    </rule>
    '''
        
        xml_content += '''
</grammar>'''
        
        return xml_content
    
    def _number_to_french(self, number: int) -> str:
        """Convertit un nombre en mot français (basé sur les références GitHub)"""
        
        # Dictionnaire des nombres de base
        ones = {
            0: "zéro", 1: "un", 2: "deux", 3: "trois", 4: "quatre", 5: "cinq",
            6: "six", 7: "sept", 8: "huit", 9: "neuf", 10: "dix",
            11: "onze", 12: "douze", 13: "treize", 14: "quatorze", 15: "quinze",
            16: "seize", 17: "dix-sept", 18: "dix-huit", 19: "dix-neuf"
        }
        
        tens = {
            20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante",
            60: "soixante", 70: "soixante-dix", 80: "quatre-vingts", 90: "quatre-vingt-dix"
        }
        
        if number in ones:
            return ones[number]
        elif number in tens:
            return tens[number]
        elif 20 <= number <= 99:
            ten = (number // 10) * 10
            one = number % 10
            
            if ten == 70:  # Cas spécial français : 70-79
                return f"soixante-{ones[10 + one]}"
            elif ten == 90:  # Cas spécial français : 90-99
                return f"quatre-vingt-{ones[10 + one]}"
            elif one == 0:
                return tens[ten]
            elif one == 1 and ten in [20, 30, 40, 50, 60]:
                return f"{tens[ten]}-et-un"
            else:
                return f"{tens[ten]}-{ones[one]}"
        elif number == 100:
            return "cent"
        else:
            return str(number)  # Fallback
    
    def _extract_questions(self, action_data: dict) -> List[str]:
        """Extrait toutes les questions d'une action"""
        questions = []
        rules = action_data.get('rules', [])
        
        for rule in rules:
            rule_questions = rule.get('questions', [])
            questions.extend([q for q in rule_questions if q and q.strip()])
        
        return questions
    
    def _get_hotword(self) -> str:
        """Récupère le hotword depuis la config"""
        hotword = "Swan"  # Valeur par défaut
        if hasattr(self.lexique_manager, 'config_manager') and self.lexique_manager.config_manager:
            try:
                hotword = self.lexique_manager.config_manager.get("listen.Hotword", "Swan")
            except:
                pass
        return hotword
    
    def _generate_root_grammar(self, root_name: str, action_data: dict) -> bool:
        """Génère une grammaire SRGS pour une règle statique (ancienne méthode)"""
        try:
            # Extraire les questions de l'action
            questions = self._extract_questions(action_data)
            
            if not questions:
                print(f"⚠️ Aucune question trouvée pour {root_name}")
                return False
            
            # Générer le XML SRGS classique
            xml_content = self._create_srgs_xml_for_root(root_name, questions, action_data)
            
            # Sauvegarder le fichier
            output_path = self.grammar_dir / f"{root_name}.xml"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            category = action_data.get('cat', 'unknown')
            print(f"✅ Grammaire générée: {output_path.name} ({len(questions)} questions, cat: {category})")
            return True
            
        except Exception as e:
            print(f"❌ Erreur génération {root_name}: {e}")
            return False
    
    def _create_srgs_xml_for_root(self, root_name: str, questions: List[str], action_data: dict) -> str:
        """Crée le contenu XML SRGS pour un root (format statique classique)"""
        
        # Infos depuis le lexique
        category = action_data.get('cat', 'unknown')
        description = action_data.get('rules', [{}])[0].get('description', f'Commandes {root_name}')
        
        # Hotword depuis config
        hotword = self._get_hotword()
        
        # Template XML compatible ancien format
        xml_template = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<grammar version="1.0" xml:lang="fr-FR" mode="voice" root="{root_name}" xmlns="http://www.w3.org/2001/06/grammar" tag-format="semantics/1.0">
    <!-- 
        Grammaire générée automatiquement depuis lexique.yaml
        Root: {root_name}
        Catégorie: {category}
        Description: {description}
        Questions: {len(questions)}
        Généré le: {time.strftime("%Y-%m-%d %H:%M:%S")}
    -->
    
    <rule id="{root_name}" scope="public">
        <tag>out.action=new Object();</tag>
        <item>{hotword}</item>
        <one-of>'''
        
        # Ajouter TOUTES les questions de l'action
        for question in questions:
            if question.strip():
                clean_question = question.strip()
                xml_template += f'\n            <item>{clean_question}</item>'
        
        xml_template += f'''
        </one-of>
        <tag>out.action.action="{root_name}";</tag>
    </rule>
</grammar>'''
        
        return xml_template
    
    def should_regenerate(self) -> bool:
        """Vérifie si les grammaires doivent être régénérées"""
        try:
            lexique_path = self.lexique_manager.lexique_path
            
            if not lexique_path.exists():
                return False
            
            lexique_mtime = lexique_path.stat().st_mtime
            
            # Vérifier si des fichiers de grammaire existent
            grammar_files = list(self.grammar_dir.glob("*.xml"))
            if not grammar_files:
                print("🔍 Aucun fichier de grammaire trouvé → Régénération nécessaire")
                return True
            
            # Vérifier si le lexique est plus récent que les grammaires
            for grammar_file in grammar_files:
                grammar_mtime = grammar_file.stat().st_mtime
                if lexique_mtime > grammar_mtime:
                    print(f"🔍 Lexique plus récent que {grammar_file.name} → Régénération nécessaire")
                    return True
            
            return False
            
        except Exception as e:
            print(f"⚠️ Erreur vérification régénération: {e}")
            return True  # En cas d'erreur, on régénère par sécurité
    
    # ... reste des méthodes existantes (_generate_numeric_multi_rule, etc.) ...

class LexiqueManager:
    """Gestionnaire du lexique de commandes vocales"""
    
    def __init__(self, lexique_path: str = "./core/config/lexique.yaml"):
        self.lexique_path = Path(lexique_path)
        self.actions: Dict[str, LexiqueAction] = {}
        self.global_config: Dict[str, Any] = {}
        self.categories: Dict[str, List[str]] = {}
        
        # ✅ Attributs pour cache et config
        self._cache = None
        self._last_modified = None
        self.config_manager = None  # ✅ AJOUTER pour accès config
        
        # Statistiques
        self.stats = {
            "total_actions": 0,
            "total_questions": 0,
            "total_responses": 0,
            "categories_count": 0,
            "last_reload": None
        }
        
        # ✅ Créer le générateur APRÈS (il utilisera config_manager)
        self.srgs_generator = SRGSGenerator(self)
        
        self.load_lexique()
    
    def set_config_manager(self, config_manager):
        """Définit le gestionnaire de configuration pour accès au hotword"""
        self.config_manager = config_manager
        print("🔧 LexiqueManager: Configuration définie pour génération SRGS")

    def load_lexique(self) -> dict:
        """Charge le fichier lexique YAML"""
        try:
            if not self.lexique_path.exists():
                print(f"❌ Fichier lexique non trouvé: {self.lexique_path}")
                return {}
            
            # Vérifier si recharge nécessaire
            current_mtime = self.lexique_path.stat().st_mtime
            if self._cache is None or self._last_modified != current_mtime:
                print(f"🔄 Rechargement lexique: {self.lexique_path}")
                
                with open(self.lexique_path, 'r', encoding='utf-8') as f:
                    raw_data = yaml.safe_load(f)
                    self._last_modified = current_mtime
                
                # ✅ VÉRIFIER que le YAML est valide
                if not isinstance(raw_data, dict):
                    print(f"❌ Lexique YAML invalide: {type(raw_data)}")
                    return {}
                
                # ✅ PARSER le lexique et remplir les collections
                self._parse_lexique_data(raw_data)
                
                # ✅ Cacher les données RAW pour SRGS
                self._cache = raw_data
                
                print(f"✅ Lexique chargé: {len(raw_data)} entrées, {len(self.actions)} actions parsées")
        
            return self._cache
        
        except Exception as e:
            print(f"❌ Erreur chargement lexique: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _parse_lexique_data(self, raw_data: dict):
        """Parse les données YAML et remplit les collections"""
        # Réinitialiser les collections
        self.actions.clear()
        self.categories.clear()
        
        # Extraire la config globale
        self.global_config = raw_data.get("global", {})
        
        # Parser chaque action
        for action_name, action_data in raw_data.items():
            if action_name == "global" or not isinstance(action_data, dict):
                continue
            
            # Parser l'action
            parsed_action = self._parse_action(action_name, action_data)
            if parsed_action:
                self.actions[action_name] = parsed_action
                
                # Ajouter à la catégorie
                category = parsed_action.cat
                if category not in self.categories:
                    self.categories[category] = []
                self.categories[category].append(action_name)
        
        # Mettre à jour les stats
        self._update_stats()
    
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
    
    def update_SRGS(self, force: bool = False) -> bool:
        """
        Met à jour les grammaires SRGS
        
        Args:
            force: Force la régénération même si pas nécessaire
            
        Returns:
            bool: True si succès, False sinon
        """
        try:
            if force:
                print("🔄 Régénération forcée des grammaires SRGS...")
                return self.srgs_generator.generate_all_by_root()
            else:
                print("🔍 Vérification des grammaires SRGS...")
                if self.srgs_generator.should_regenerate():
                    print("🔄 Lexique modifié → Régénération des grammaires nécessaire")
                    return self.srgs_generator.generate_all_by_root()
                else:
                    print("✅ Grammaires à jour")
                    return True
                
        except Exception as e:
            print(f"❌ Erreur update_SRGS: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def invalidate_cache_and_update_SRGS(self) -> bool:
        """
        Invalide le cache lexique ET met à jour les grammaires
        Utile quand le lexique.yaml a été modifié externalement
        """
        print("🔄 Invalidation cache lexique + mise à jour SRGS...")
        
        # Invalider le cache
        self._cache = None
        self._last_modified = None
        
        # Forcer la régénération
        return self.update_SRGS(force=True)

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