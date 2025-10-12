# bus.py 

# ========== IMPORTS (importation de modules) ==========
# Le mot-clé "from" permet d'importer des éléments spécifiques d'un module
# "typing" est un module Python qui aide à définir les types de données
from typing import Callable, Dict, Any, List

# ========== ALIAS DE TYPES (raccourcis pour les types) ==========
# En Python, on peut créer des "alias" = des raccourcis pour des types complexes

# Message = nom qu'on donne à ce type
# Dict[str, Any] = un dictionnaire avec :
#   - clés de type "str" (string = texte)
#   - valeurs de type "Any" (n'importe quoi : nombre, texte, liste, etc.)
# Exemple : {"name": "son", "volume": 50, "active": True}
Message = Dict[str, Any]

# Callback = nom qu'on donne à ce type
# Callable[[Message], None] = une fonction qui :
#   - prend 1 paramètre de type Message (entre crochets [])
#   - retourne None (rien)
# Exemple : def ma_fonction(msg): print(msg)
Callback = Callable[[Message], None]

# ========== DÉFINITION DE CLASSE ==========
# "class" = mot-clé pour créer une nouvelle classe (un "moule" pour créer des objets)
# "EventBus" = nom de la classe (convention : première lettre majuscule)
# ":" = indique que ce qui suit appartient à la classe
class EventBus:
    # Les """ """ = docstring (documentation de la fonction/classe)
    # C'est optionnel mais c'est une bonne pratique
    """
    Classe qui représente un bus d'événements
    """
    
    # ========== MÉTHODE CONSTRUCTEUR ==========
    # "__init__" = méthode spéciale appelée quand on crée un objet
    # "self" = référence à l'objet lui-même (obligatoire en premier paramètre)
    def __init__(self):
        """
        Constructeur de la classe
        """
        # "self.subscribers" = attribut (variable) de l'objet
        # ":" = annotation de type (optionnel, pour la documentation)
        # "List[Callback]" = liste qui contient des éléments de type Callback
        # "[]" = liste vide
        self.subscribers: List[Callback] = []

    # ========== MÉTHODE DE CLASSE ==========
    # "def" = mot-clé pour définir une fonction/méthode
    # "subscribe" = nom de la méthode
    # "(self, callback: Callback)" = paramètres :
    #   - "self" = référence à l'objet (obligatoire dans une classe)
    #   - "callback" = nom du paramètre
    #   - ": Callback" = annotation de type (optionnel)
    def subscribe(self, callback: Callback):
        """
        Méthode pour ajouter une fonction à la liste des abonnés
        """
        # "self.subscribers" = on accède à l'attribut "subscribers" de cet objet
        # ".append()" = méthode des listes pour ajouter un élément à la fin
        # "callback" = la fonction qu'on veut ajouter
        self.subscribers.append(callback)

    # ========== AUTRE MÉTHODE DE CLASSE ==========
    def publish(self, msg: Message):
        """
        Méthode pour envoyer un message à tous les abonnés
        """
        # ========== ASSERTION ==========
        # "assert" = mot-clé qui vérifie une condition
        # Si la condition est False, le programme s'arrête avec une erreur
        # "in" = opérateur pour vérifier si une clé existe dans un dictionnaire
        # "and" = opérateur logique ET
        assert "name" in msg and "state" in msg
        
        # ========== BOUCLE FOR ==========
        # "for" = mot-clé pour créer une boucle
        # "cb" = variable temporaire qui prend chaque valeur de la liste
        # "in" = mot-clé pour parcourir une collection
        # "self.subscribers" = la liste qu'on parcourt
        for cb in self.subscribers:
            # À chaque tour de boucle, "cb" contient une fonction différente
            # "cb(msg)" = on appelle la fonction "cb" avec le paramètre "msg"
            # Les parenthèses après un nom de fonction = appel de fonction
            cb(msg)


# ========== EXEMPLE D'UTILISATION ==========
# Commented out (commenté) pour ne pas exécuter automatiquement

# Créer un bus d'événements :
# bus = EventBus()

# Créer une fonction qui recevra les messages :
# def ma_fonction_qui_ecoute(message):
#     print(f"Message reçu : {message}")

# S'abonner aux messages :
# bus.subscribe(ma_fonction_qui_ecoute)

# Envoyer un message :
# bus.publish({"name": "test", "state": "active", "data": "hello"})