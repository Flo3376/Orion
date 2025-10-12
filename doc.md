# 🎵 Documentation des Modules Audio - Projet Orion

## 📋 Vue d'ensemble

Ce projet contient deux modules principaux pour gérer l'audio :
- **`SpotifyController`** : Contrôle Spotify via l'API
- **`SoundManager`** : Lecteur audio local (musique, journal, infos)

---

## 🎧 Module Spotify (`core/sound/spotify.py`)

### 🚀 Création du contrôleur

```python
from core.sound.spotify import SpotifyController
from core.bus import EventBus

bus = EventBus()
bus.subscribe(ma_fonction_qui_ecoute)  # IMPORTANT : s'abonner AVANT !

spotify = SpotifyController(
    client_id="ton_client_id",
    client_secret="ton_client_secret", 
    redirect_uri="http://localhost:8888/callback",
    event_bus=bus,                    # Obligatoire pour recevoir les événements
    poll_interval=1.0,                # Fréquence de vérification (secondes)
    open_app_if_needed=True,          # Ouvre Spotify automatiquement
    device_name_preference=None,      # Nom d'appareil préféré (optionnel)
    payload_minimal=True,             # Messages courts ou détaillés
)
```

### 🎮 Commandes de contrôle

#### ▶️ Lecture
```python
# Reprendre la lecture (chanson en cours)
spotify.play()

# Jouer une chanson spécifique
spotify.play("spotify:track:4iV5W9uYEdYUVa79Axb7Rh")

# Jouer un album/playlist
spotify.play(context_uri="spotify:album:4aawyAB9vmqN3uQ7FjRGTy")

# Reprendre à une position spécifique (millisecondes)
spotify.play(position_ms=30000)  # Commencer à 30 secondes
```

#### ⏸️ Pause
```python
spotify.pause()
```

#### ⏭️ Navigation
```python
spotify.next()      # Chanson suivante
spotify.previous()  # Chanson précédente
```

#### 🔊 Contrôle du volume
```python
# Volume précis (0-100)
spotify.set_volume(50)

# Augmenter le volume
spotify.volume_up()     # +5 par défaut
spotify.volume_up(10)   # +10

# Diminuer le volume  
spotify.volume_down()   # -5 par défaut
spotify.volume_down(15) # -15
```

#### 🛑 Arrêt
```python
spotify.stop()  # Arrête le polling et nettoie les ressources
```

### 📨 Messages du bus d'événements

Le SpotifyController envoie ces messages sur le bus :

#### 🟢 État prêt
```python
{
    "name": "spotify",
    "state": "ready", 
    "payload": {
        "device": {"id": "...", "name": "Mon PC", "type": "Computer"}
    }
}
```

#### 🎵 Lecture en cours
```python
{
    "name": "spotify",
    "state": "playback",
    "payload": {
        "playing": True,
        "title": "Bohemian Rhapsody",
        "artists": ["Queen"],
        "album": "A Night at the Opera",
        "pos": 45000,        # Position en millisecondes
        "dur": 354000,       # Durée totale
        "volume": 80,        # Volume actuel
        "device": "Mon PC"   # Nom de l'appareil
    }
}
```

#### 🔄 Changement de piste
```python
{
    "name": "spotify", 
    "state": "track_changed",
    "payload": {
        "track_id": "4iV5W9uYEdYUVa79Axb7Rh",
        "title": "Don't Stop Me Now",
        "artists": ["Queen"]
    }
}
```

#### ⏸️ États de lecture
```python
# En pause
{"name": "spotify", "state": "paused", "payload": {...}}

# En lecture
{"name": "spotify", "state": "playing", "payload": {...}}

# Aucune lecture
{"name": "spotify", "state": "idle", "payload": {}}
```

#### ❌ Erreurs
```python
{
    "name": "spotify",
    "state": "error", 
    "payload": {
        "code": "play_failed",
        "message": "Impossible de démarrer la lecture"
    }
}
```

---

## 🔊 Module SoundManager (`core/sound/player.py`)

### 🏗️ Création du gestionnaire

```python
from core.sound.player import SoundManager
from core.bus import EventBus

bus = EventBus()
bus.subscribe(ma_fonction_qui_ecoute)

sound_manager = SoundManager(event_bus=bus)

# Configuration initiale
sound_manager.init({
    "master_volume": 1.0,      # Volume général (0.0 - 1.0)
    "music_volume": 0.6,       # Volume musique
    "journal_volume": 0.7,     # Volume journal  
    "info_volume": 0.8,        # Volume infos
    "duck_fade_ms": 200,       # Durée du fade pour duck
    "log_full_paths": False,   # Afficher chemins complets dans logs
})
```

### 🎵 Contrôleur Musique (`sound_manager.music`)

#### ▶️ Lecture
```python
# Jouer un fichier
sound_manager.music.play("./music/ma_chanson.mp3")

# Avec volume spécifique pour ce fichier (0.0 - 1.0)
sound_manager.music.play("./music/ma_chanson.mp3", volume_item=0.8)
```

#### 🛑 Contrôles
```python
sound_manager.music.stop()     # Arrête et vide la playlist
sound_manager.music.pause()    # Met en pause
sound_manager.music.resume()   # Reprend la lecture
sound_manager.music.next()     # Passe à la chanson suivante
sound_manager.music.clear()    # Vide la playlist sans arrêter
```

#### 🔊 Volume
```python
# Définir le volume
sound_manager.music.set_volume(0.5)

# Récupérer le volume actuel
vol = sound_manager.music.get_volume()  # {"ok": True, "volume": 0.5}
```

#### 📊 État
```python
state = sound_manager.music.get_state()
# Retourne : {"ok": True, "playing": "chemin/vers/fichier.mp3", "queue": ["file1.mp3", "file2.mp3"]}
```

### 📰 Contrôleur Journal (`sound_manager.journal`)

Le journal joue **un seul son à la fois** et remplace automatiquement le précédent.

#### ▶️ Lecture
```python
# Lecture simple
sound_manager.journal.play("./voices/journal.mp3")

# Avec options avancées
sound_manager.journal.play(
    "./voices/journal.mp3",
    volume_item=0.9,        # Volume pour ce fichier
    auto_resume=True,       # Reprendre la musique après (défaut: True)
    fade_ms=300            # Durée du fade musique en ms
)
```

#### 🛑 Contrôles
```python
sound_manager.journal.stop()
sound_manager.journal.pause()
sound_manager.journal.resume()
```

#### 🔊 Volume et État
```python
sound_manager.journal.set_volume(0.7)
vol = sound_manager.journal.get_volume()
state = sound_manager.journal.get_state()
```

### 📢 Contrôleur Info (`sound_manager.info`)

Le système d'infos a **deux priorités** :

#### 🟡 Priorité LOW (par défaut)
- Met en file d'attente
- Applique un "duck" (baisse le volume musique/journal temporairement)
- Ne stoppe rien

```python
# Info basse priorité
sound_manager.info.play("./alerts/notification.mp3")  # priority="low" par défaut
sound_manager.info.play("./alerts/info.mp3", priority="low", volume_item=1.0)
```

#### 🔴 Priorité HIGH
- **Interrompt** les infos low en cours
- **Purge** toute la file des infos low
- **Stoppe** musique et journal immédiatement
- Pas de duck, coupe tout

```python
# Info haute priorité (urgente)
sound_manager.info.play("./alerts/emergency.mp3", priority="high")
```

#### 🛑 Contrôles
```python
# Arrête TOUTES les infos et retire le duck
sound_manager.info.stop_all()
```

#### 🔊 Volume et État
```python
sound_manager.info.set_volume(0.8)
vol = sound_manager.info.get_volume()
state = sound_manager.info.get_state()
# Retourne: {"ok": True, "current": ("path", "priority"), "queue_low": 2, "queue_high": 0}
```

### 🎛️ Contrôles globaux du SoundManager

#### 🔊 Volume maître
```python
sound_manager.set_master_volume(0.8)
vol = sound_manager.get_master_volume()  # {"ok": True, "master_volume": 0.8}
```

#### 🔊 Volume par rôle
```python
sound_manager.set_volume("music", 0.6)
sound_manager.set_volume("journal", 0.7) 
sound_manager.set_volume("info", 0.8)
```

#### 📊 État complet
```python
state = sound_manager.get_state()
# Retourne un objet avec tous les états et volumes
```

#### ⚙️ Configuration
```python
# Mettre à jour la config
sound_manager.init({
    "music_volume": 0.5,
    "duck_fade_ms": 300
})

# Récupérer la config actuelle
config = sound_manager.get_config()
```

### 📨 Messages du bus d'événements (SoundManager)

#### 🎵 Événements musique
```python
{"name": "music.enqueued", "state": "ready", "payload": {...}}
{"name": "music.started", "state": "playing", "payload": {...}}
{"name": "music.finished", "state": "stopped", "payload": {...}}
{"name": "music.paused", "state": "paused", "payload": {...}}
{"name": "music.resumed", "state": "playing", "payload": {...}}
```

#### 📰 Événements journal
```python
{"name": "journal.started", "state": "playing", "payload": {...}}
{"name": "journal.finished", "state": "stopped", "payload": {...}}
{"name": "journal.paused", "state": "paused", "payload": {...}}
```

#### 📢 Événements info
```python
{"name": "info.low.started", "state": "playing", "payload": {...}}
{"name": "info.high.started", "state": "playing", "payload": {...}}
{"name": "info.low.finished", "state": "stopped", "payload": {...}}
{"name": "duck.on", "state": "active", "payload": {...}}    # Duck activé
{"name": "duck.off", "state": "inactive", "payload": {...}} # Duck désactivé
```

---

## 🎯 Exemples pratiques

### Exemple 1 : Lecteur musical simple
```python
# Démarrer la musique
sound_manager.music.play("./playlist/song1.mp3")
sound_manager.music.play("./playlist/song2.mp3")  # Ajouté à la queue

# Contrôles
sound_manager.music.pause()
sound_manager.music.resume()
sound_manager.music.next()    # Passe à song2.mp3
sound_manager.music.stop()    # Arrête tout
```

### Exemple 2 : Système de notifications
```python
# Notification normale (avec duck)
sound_manager.info.play("./sounds/notification.mp3", priority="low")

# Alerte urgente (coupe tout)
sound_manager.info.play("./sounds/emergency.mp3", priority="high") 
```

### Exemple 3 : Journal parlé avec reprise automatique
```python
# La musique va être mise en pause automatiquement
sound_manager.journal.play("./voice/news.mp3", auto_resume=True)
# À la fin, la musique reprendra automatiquement
```

### Exemple 4 : Contrôle Spotify + Son local
```python
# Spotify en arrière-plan
spotify.play()
spotify.set_volume(30)

# Son local urgent par-dessus
sound_manager.info.play("./alerts/incoming_call.mp3", priority="high")
```

---

## 🔧 Conseils et bonnes pratiques

### ⚠️ Ordre d'initialisation IMPORTANT
```python
# ❌ FAUX - On rate les premiers messages
spotify = SpotifyController(event_bus=bus)
spotify.play()
bus.subscribe(ma_fonction)  # Trop tard !

# ✅ CORRECT - S'abonner AVANT
bus.subscribe(ma_fonction)
spotify = SpotifyController(event_bus=bus)
spotify.play()  # Les messages seront reçus
```

### 📁 Formats de fichiers supportés
- **Recommandés** : WAV, FLAC, OGG
- **MP3** : Peut nécessiter des dépendances supplémentaires
- **Vérification** : Le système diagnostique automatiquement les problèmes

### 🎛️ Gestion des volumes
- **master_volume** : Affecte TOUT (0.0 = muet, 1.0 = max)
- **[role]_volume** : Volume par catégorie (music, journal, info)
- **volume_item** : Volume pour un fichier spécifique
- **Calcul final** : `master × role × item = volume final`

### 🔄 Duck automatique
Le "duck" baisse automatiquement musique/journal quand une info `low` joue :
- **Niveau de duck** : 30% du volume original  
- **Durée du fade** : Configurable via `duck_fade_ms`
- **Auto-retour** : Volume remonte à la fin des infos low

---

## ❓ FAQ

**Q : Pourquoi mes messages Spotify ne passent pas ?**  
R : Vérifiez que vous vous abonnez au bus AVANT de créer le SpotifyController.

**Q : Le MP3 ne fonctionne pas ?**  
R : Installez les dépendances : `pip install soundfile[mp3]`

**Q : Comment avoir plusieurs musiques en même temps ?**  
R : Utilisez différents rôles : musique d'ambiance + effets sonores via `info.play()`

**Q : Le volume ne change pas ?**  
R : Vérifiez que le volume maître n'est pas à 0, et que l'appareil Spotify est actif.

---

*Cette documentation couvre les fonctionnalités principales. N'hésitez pas à explorer le code source pour des usages avancés !*
