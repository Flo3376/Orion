"""
Gestionnaire de sons avancé pour application interactive (musique, journal, info)
=================================================================================

Version adaptée au **bus unidirectionnel** défini :
- Les modules **publient** uniquement des événements d'état vers un `EventBus` externe.
- Le `main` écoute le bus et **pilote les modules directement** via leurs classes/objets.
- Tous les messages bus suivent la convention :
    {
        "name": <str>,        # domaine (ex: "music", "journal", "info", "duck", "config", "volume")
        "state": <str>,       # état (ex: "started", "finished", "low_started", ...)
        "payload": { ... }    # données associées (facultatif)
    }

Dépendances : numpy, soundfile, sounddevice
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Literal, Tuple

import numpy as np
import soundfile as sf
import sounddevice as sd
from contextlib import contextmanager
from core.bus import EventBus  # Doit fournir: subscribe(callback), publish(message: dict)

# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float, hi: float) -> float:
    """Contraint `value` dans [lo, hi]. Utilisé pour les volumes (0.0..1.0)."""
    return max(lo, min(hi, float(value)))

@contextmanager
def _suppress_stderr():
    """Supprime temporairement la sortie **stderr** au niveau C (libmpg123, etc.).
    Laisse nos `print()` (stdout) intacts. À utiliser autour de l'ouverture/stream.
    """
    import sys
    try:
        sys.stderr.flush()
    except Exception:
        pass
    try:
        saved_fd = os.dup(2)
    except Exception:
        # fallback: si dup échoue, ne rien faire
        yield
        return
    try:
        with open(os.devnull, "w") as devnull:
            try:
                os.dup2(devnull.fileno(), 2)
            except Exception:
                pass
        yield
    finally:
        try:
            os.dup2(saved_fd, 2)
        except Exception:
            pass
        try:
            os.close(saved_fd)
        except Exception:
            pass

# --- Logs: chemin complet ou nom de fichier seulement ---
LOG_FULL_PATHS: bool = False  # False = n'afficher que le nom du fichier

def _fmt_path(path: str) -> str:
    import os
    try:
        return os.path.abspath(path) if LOG_FULL_PATHS else os.path.basename(path)
    except Exception:
        return str(path)

# ---------------------------------------------------------------------------
# Defaults (en dur)
# ---------------------------------------------------------------------------
DEFAULT_MASTER_VOLUME: float = 1.0
DEFAULT_MUSIC_VOLUME: float = 0.6
DEFAULT_JOURNAL_VOLUME: float = 0.7
DEFAULT_INFO_VOLUME: float = 0.8

DEFAULT_DUCK_FADE_MS: int = 200   # (utilisé plus tard pour INFO low)
DUCK_LEVEL_PERCENT: int = 30      # idem, pour plus tard

ACCEPTED_CONFIG_KEYS = {
    "master_volume",
    "music_volume",
    "journal_volume",
    "info_volume",
    "duck_fade_ms",
    "log_full_paths",
}


# ---------------------------------------------------------------------------
# Configuration minimale
# ---------------------------------------------------------------------------
@dataclass
class Config:
    master_volume: float = DEFAULT_MASTER_VOLUME
    music_volume: float = DEFAULT_MUSIC_VOLUME
    journal_volume: float = DEFAULT_JOURNAL_VOLUME
    info_volume: float = DEFAULT_INFO_VOLUME
    duck_fade_ms: int = DEFAULT_DUCK_FADE_MS
    log_full_paths: bool = False 

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        cfg = cls()
        if not isinstance(data, dict):
            return cfg
        if "master_volume" in data:
            cfg.master_volume = _clamp(data["master_volume"], 0.0, 1.0)
        if "music_volume" in data:
            cfg.music_volume = _clamp(data["music_volume"], 0.0, 1.0)
        if "journal_volume" in data:
            cfg.journal_volume = _clamp(data["journal_volume"], 0.0, 1.0)
        if "info_volume" in data:
            cfg.info_volume = _clamp(data["info_volume"], 0.0, 1.0)
        if "duck_fade_ms" in data:
            cfg.duck_fade_ms = max(int(data["duck_fade_ms"]), 0)
        return cfg

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


Role = Literal["music", "info", "journal"]

class MusicController:
    def __init__(self, manager: "SoundManager") -> None:
        self._m = manager
        self._player = _MusicPlayer(
            get_master=lambda: self._m.config.master_volume,
            get_music_vol=lambda: self._m.config.music_volume,
            emit=lambda evt: self._m.emit(evt),  # route vers EventBus
        )

    def play(self, path: str, *, volume_item: float = 1.0) -> dict:
        return self._player.play(path, volume_item)

    def stop(self) -> dict:
        res = self._player.stop()
        self._m._emit_event({"name": "music", "state": "stopped", "payload": {}})
        return res

    def pause(self) -> dict:
        res = self._player.pause()
        self._m._emit_event({"name": "music", "state": "paused", "payload": {}})
        return res

    def resume(self) -> dict:
        res = self._player.resume()
        self._m._emit_event({"name": "music", "state": "resumed", "payload": {}})
        return res

    def next(self) -> dict:
        res = self._player.next()
        self._m._emit_event({"name": "music", "state": "next", "payload": {}})
        return res

    def clear(self) -> dict:
        res = self._player.clear()
        self._m._emit_event({"name": "music", "state": "queue_cleared", "payload": res})
        return res

    def set_volume(self, value: float, *, fade_ms: int | None = None) -> dict:
        self._m.config.music_volume = max(0.0, min(1.0, float(value)))
        return {"ok": True, "volume": self._m.config.music_volume}

    def get_volume(self) -> dict:
        return {"ok": True, "volume": self._m.config.music_volume}

    def get_state(self) -> dict:
        s = self._player.get_state()
        return {"ok": True, **s}

# ---------------------------------------------------------------------------
# MUSIQUE — Playlist + streaming, diagnostics + silencer + fin fiable
# ---------------------------------------------------------------------------
class _MusicPlayer:
    """
    Lecteur de musique principal (playlist, streaming, diagnostics, gestion thread).
    Utilisé via MusicController. Fournit : play, stop, pause, resume, next, clear, get_state.
    """
    def __init__(self, get_master: callable, get_music_vol: callable, emit: callable | None = None) -> None:
        self._get_master = get_master
        self._get_music_vol = get_music_vol
        self._emit = emit or (lambda *_a, **_k: None)

        self._queue: deque[tuple[str, float]] = deque()  # (path, volume_item)
        self._lock = threading.Lock()

        self._thread: Optional[threading.Thread] = None
        self._stop_all = threading.Event()
        self._paused = threading.Event()   # True ⇒ en pause
        self._request_next = threading.Event()

        self._state_playing: Optional[str] = None  # chemin de la piste en cours

    # --------- Pré‑vérification : retourne (ok, payload) ---------
    def _preflight(self, path: str) -> Tuple[bool, Dict[str, Any]]:
        abs_path = os.path.abspath(path)
        if not os.path.exists(path):
            return False, {
                "ok": False,
                "error": "file_not_found",
                "message": f"Fichier introuvable : {abs_path}",
                "path": abs_path,
            }
        try:
            with _suppress_stderr():
                info = sf.info(path)  # lit l’entête
            if info.samplerate <= 0 or info.channels <= 0:
                raise RuntimeError(f"Entête invalide (samplerate={info.samplerate}, channels={info.channels})")
            return True, {
                "ok": True,
                "path": abs_path,
                "samplerate": info.samplerate,
                "channels": info.channels,
                "frames": int(info.frames),
                "duration_sec": (float(info.frames) / info.samplerate) if info.samplerate else None,
            }
        except Exception as e:
            ext = os.path.splitext(path)[1].lower()
            fmts = {k.lower() for k in sf.available_formats().keys()}
            if ext == ".mp3" and "mp3" not in fmts:
                return False, {
                    "ok": False,
                    "error": "mp3_unsupported",
                    "message": (f"Le MP3 n’est pas activé dans la bibliothèque audio locale. Fichier : {abs_path}"),
                    "path": abs_path,
                    "details": str(e),
                }
            return False, {
                "ok": False,
                "error": "unreadable_media",
                "message": f"Impossible d’ouvrir le média : {abs_path}",
                "path": abs_path,
                "details": str(e),
            }

    # ----------------------------- API publique -----------------------------
    def play(self, path: str, volume_item: float = 1.0) -> Dict[str, Any]:
        ok, diag = self._preflight(path)
        if not ok:
            print(f"[music.play] {diag['error']}: {diag['message']}")
            return diag
        self._emit({
            "name": "music",
            "state": "enqueued",
            "payload": {**diag, "volume_item": float(_clamp(volume_item, 0.0, 1.0))},
        })

        with self._lock:
            self._queue.append((path, _clamp(volume_item, 0.0, 1.0)))
            need_start = self._thread is None or not self._thread.is_alive()
        if need_start:
            self._stop_all.clear()
            self._paused.clear()
            self._request_next.clear()
            self._thread = threading.Thread(target=self._run_loop, name="MusicPlayer", daemon=True)
            self._thread.start()
        return {"ok": True, "enqueued": True, "started": need_start, **diag}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._queue.clear()
            self._state_playing = None
        self._request_next.set()
        self._stop_all.set()
        return {"ok": True, "stopped": True, "cleared": True}

    def pause(self) -> Dict[str, Any]:
        self._paused.set()
        return {"ok": True, "paused": True}

    def resume(self) -> Dict[str, Any]:
        self._paused.clear()
        return {"ok": True, "resumed": True}

    def clear(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self._queue)
            self._queue.clear()
        return {"ok": True, "cleared": n}

    def next(self) -> Dict[str, Any]:
        self._request_next.set()
        return {"ok": True, "skipped": True}

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            q = [p for p, _ in list(self._queue)]
            cur = self._state_playing
        return {"playing": cur, "queue": q}

    # --------------------------- boucle de lecture --------------------------
    def _run_loop(self) -> None:
        while not self._stop_all.is_set():
            pair = self._popleft_or_wait()
            if pair is None:
                break
            path, vol_item = pair
            self._play_one(path, vol_item)
        with self._lock:
            self._state_playing = None

    def _popleft_or_wait(self) -> Optional[tuple[str, float]]:
        while not self._stop_all.is_set():
            with self._lock:
                if self._queue:
                    return self._queue.popleft()
            time.sleep(0.02)
        return None

    def _play_one(self, path: str, vol_item: float) -> None:
        ended_normally = False 
        try:
            with _suppress_stderr():
                snd = sf.SoundFile(path, mode="r")
        except Exception as e:
            print(f"[music] Erreur d'ouverture: {os.path.abspath(path)} → {e}")
            return

        samplerate = snd.samplerate
        channels = snd.channels

        def current_gain() -> np.float32:
            g = self._get_master() * self._get_music_vol() * vol_item
            return np.float32(_clamp(g, 0.0, 2.0))

        local_stop = False

        def callback(outdata, frames, time_info, status):
            nonlocal local_stop, ended_normally
            if status:
                print("[music][cb] status:", status)
            if self._paused.is_set():
                outdata[:] = 0
                return
            if self._request_next.is_set() or self._stop_all.is_set():
                local_stop = True
                ended_normally = False
            if local_stop:
                outdata[:] = 0
                raise sd.CallbackStop()
            
            data = snd.read(frames, dtype="float32", always_2d=True)
            if data.shape[0] == 0:
                ended_normally = True
                local_stop = True
                outdata[:] = 0
                raise sd.CallbackStop()
            
            outdata[: data.shape[0], : data.shape[1]] = data * current_gain()
            if data.shape[0] < frames:
                outdata[data.shape[0] :, :] = 0
                local_stop = True  # dernière tranche partielle
                ended_normally = True
                raise sd.CallbackStop()

        try:
            with self._set_playing(path), _suppress_stderr(), sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                callback=callback,
                blocksize=1024,
                latency="low",
            ) as stream:
                while stream.active and not local_stop and not self._stop_all.is_set():
                    time.sleep(0.05)
        except Exception as e:
            print(f"[music] Erreur de sortie: {os.path.abspath(path)} → {e}")
        finally:
            try:
                snd.close()
            except Exception:
                pass
            self._request_next.clear()
            self._emit({
                "name": "music",
                "state": "finished",
                "payload": {
                    "path": os.path.abspath(path),
                    "ended_normally": ended_normally
                }
            })

    # Contexte pratique pour exposer le nom en cours
    @contextmanager
    def _set_playing(self, path: str):
        with self._lock:
            self._state_playing = path
        try:
            print(f">> [music] Lecture : {_fmt_path(path)}", flush=True)
            self._emit({"name": "music", "state": "started", "payload": {"path": os.path.abspath(path)}})
            yield
        finally:
            with self._lock:
                self._state_playing = None


# ---------------------------------------------------------------------------
# JOURNAL — Remplacement immédiat, pause musique + fade, auto‑resume optionnel
# ---------------------------------------------------------------------------
class _JournalPlayer:
    """
    Lecteur de sons "journal" (un à la fois, remplacement immédiat, callback de fin, fade musique).
    Utilisé via JournalController.
    """
    def __init__(self, get_master: callable, get_journal_vol: callable, emit: callable | None = None) -> None:
        self._get_master = get_master
        self._get_journal_vol = get_journal_vol
        self._emit = emit or (lambda *_a, **_k: None)
                
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._stop_all = threading.Event()
        self._paused = threading.Event()      # True ⇒ en pause
        self._replace_event = threading.Event()  # demandé quand un nouveau play arrive

        self._state_playing: Optional[str] = None   # chemin courant
        self._next: Optional[tuple[str, float]] = None  # (path, volume_item)

        self._on_finished = None  # type: Optional[callable]

    def set_on_finished(self, cb: Optional[callable]) -> None:
        """Callback appelé **après** chaque fin de lecture.
        Signature : `cb(path: str, ended_normally: bool)`
        """
        self._on_finished = cb

    # --------- Pré‑vérification ---------
    def _preflight(self, path: str) -> tuple[bool, Dict[str, Any]]:
        abs_path = os.path.abspath(path)
        if not os.path.exists(path):
            return False, {
                "ok": False,
                "error": "file_not_found",
                "message": f"Fichier introuvable : {abs_path}",
                "path": abs_path,
            }
        try:
            with _suppress_stderr():
                info = sf.info(path)
            if info.samplerate <= 0 or info.channels <= 0:
                raise RuntimeError(
                    f"Entête invalide (samplerate={info.samplerate}, channels={info.channels})"
                )
            return True, {
                "ok": True,
                "path": abs_path,
                "samplerate": info.samplerate,
                "channels": info.channels,
                "frames": int(info.frames),
                "duration_sec": (float(info.frames) / info.samplerate) if info.samplerate else None,
            }
        except Exception as e:
            ext = os.path.splitext(path)[1].lower()
            fmts = {k.lower() for k in sf.available_formats().keys()}
            if ext == ".mp3" and "mp3" not in fmts:
                return False, {
                    "ok": False,
                    "error": "mp3_unsupported",
                    "message": (f"Le MP3 n’est pas activé dans la bibliothèque audio locale. Fichier : {abs_path}"),
                    "path": abs_path,
                    "details": str(e),
                }
            return False, {
                "ok": False,
                "error": "unreadable_media",
                "message": f"Impossible d’ouvrir le média : {abs_path}",
                "path": abs_path,
                "details": str(e),
            }

    # ----------------------------- API publique -----------------------------
    def play(self, path: str, volume_item: float = 1.0) -> Dict[str, Any]:
        ok, diag = self._preflight(path)
        if not ok:
            print(f"[journal.play] {diag['error']}: {diag['message']}")
            return diag
        self._emit({
            "name": "journal",
            "state": "enqueued",
            "payload": {**diag, "volume_item": float(_clamp(volume_item, 0.0, 1.0))},
        })

        with self._lock:
            self._next = (path, _clamp(volume_item, 0.0, 1.0))
            need_start = self._thread is None or not self._thread.is_alive()
        if need_start:
            self._stop_all.clear()
            self._paused.clear()
            self._replace_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="JournalPlayer", daemon=True)
            self._thread.start()
        else:
            self._replace_event.set()  # remplace l'actuel
        return {"ok": True, "started": need_start, **diag}

    def stop(self) -> Dict[str, Any]:
        with self._lock:
            self._next = None
        self._replace_event.set()
        self._stop_all.set()
        return {"ok": True, "stopped": True}

    def pause(self) -> Dict[str, Any]:
        self._paused.set()
        return {"ok": True, "paused": True}

    def resume(self) -> Dict[str, Any]:
        self._paused.clear()
        return {"ok": True, "resumed": True}

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            cur = self._state_playing
        return {"playing": cur}

    # --------------------------- boucle de lecture --------------------------
    def _run_loop(self) -> None:
        while not self._stop_all.is_set():
            pair = self._consume_next()
            if pair is None:
                time.sleep(0.02)
                continue
            path, vol_item = pair
            self._play_one(path, vol_item)
        with self._lock:
            self._state_playing = None

    def _consume_next(self) -> Optional[tuple[str, float]]:
        with self._lock:
            p = self._next
            self._next = None
            return p

    def _play_one(self, path: str, vol_item: float) -> None:
        try:
            with _suppress_stderr():
                snd = sf.SoundFile(path, mode="r")
        except Exception as e:
            print(f"[journal] Erreur d'ouverture: {os.path.abspath(path)} → {e}")
            return

        samplerate = snd.samplerate
        channels = snd.channels

        def current_gain() -> np.float32:
            g = self._get_master() * self._get_journal_vol() * vol_item
            return np.float32(_clamp(g, 0.0, 2.0))

        local_stop = False
        ended_normally = False

        def callback(outdata, frames, time_info, status):
            nonlocal local_stop, ended_normally
            if status:
                print("[journal][cb] status:", status)
            if self._paused.is_set():
                outdata[:] = 0
                return
            if self._replace_event.is_set() or self._stop_all.is_set():
                local_stop = True
            if local_stop:
                outdata[:] = 0
                raise sd.CallbackStop()
            data = snd.read(frames, dtype="float32", always_2d=True)
            if data.shape[0] == 0:
                outdata[:] = 0
                ended_normally = True
                local_stop = True
                raise sd.CallbackStop()
            outdata[: data.shape[0], : data.shape[1]] = data * current_gain()
            if data.shape[0] < frames:
                outdata[data.shape[0] :, :] = 0
                ended_normally = True
                local_stop = True
                raise sd.CallbackStop()

        @contextmanager
        def _set_playing(path: str):
            with self._lock:
                self._state_playing = path
            try:
                #print(f">> [journal] Lecture : {_fmt_path(path)}", flush=True)
                self._emit({"name": "journal", "state": "started", "payload": {"path": os.path.abspath(path)}})
                
                yield
            finally:
                with self._lock:
                    self._state_playing = None

        try:
            with _set_playing(path), _suppress_stderr(), sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                callback=callback,
                blocksize=1024,
                latency="low",
            ) as stream:
                while stream.active and not local_stop and not self._stop_all.is_set():
                    time.sleep(0.05)
        except Exception as e:
            print(f"[journal] Erreur de sortie: {os.path.abspath(path)} → {e}")
        finally:
            try:
                snd.close()
            except Exception:
                pass
            self._replace_event.clear()
            self._emit({
                "name": "journal",
                "state": "finished",
                "payload": {
                    "path": os.path.abspath(path),
                    "ended_normally": ended_normally,
                }
            })
            if self._on_finished is not None:
                try:
                    self._on_finished(path, ended_normally)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# INFO — files low/high + règles (duck sur low, stop musique/journal sur high)
# ---------------------------------------------------------------------------
class _InfoPlayer:
    """Files d'attente pour les infos **low** et **high** + lecture streaming.

    Règles métier :
    - `high` > `low` : la file high est prioritaire.
    - Si un `high` arrive pendant un `low` : on **interrompt** le low en cours et
      on **purge** toutes les `low` en attente (les `high` restent en FIFO).
    - Si un `high` arrive pendant un autre `high` : on **met en file** (FIFO), pas d'interruption.

    Les hooks `on_before(item)` et `on_after(item, ended_normally)` permettent au
    contrôleur parent d'appliquer le DUCK (low) ou de couper musique/journal (high).
    """

    def __init__(self, get_master: callable, get_info_vol: callable) -> None:
        self._get_master = get_master
        self._get_info_vol = get_info_vol

        self._q_low: deque[tuple[str, float, str]] = deque()   # (path, vol_item, "low")
        self._q_high: deque[tuple[str, float, str]] = deque()  # (path, vol_item, "high")

        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

        self._stop_all = threading.Event()
        self._interrupt_low = threading.Event()  # demander d'interrompre un low en cours

        self._state_playing: Optional[tuple[str, str]] = None  # (path, priority)

        self._on_before = None   # type: Optional[callable]
        self._on_after = None    # type: Optional[callable]

    # ---- hooks ----
    def set_on_before(self, cb: Optional[callable]) -> None:
        self._on_before = cb

    def set_on_after(self, cb: Optional[callable]) -> None:
        self._on_after = cb
    
    # --- compat: alias utilisés par InfoController ---
    def set_on_started(self, cb: Optional[callable]) -> None:
        # InfoController attend set_on_started → on route vers notre hook "before"
        self._on_before = cb

    def set_on_finished(self, cb: Optional[callable]) -> None:
        # InfoController attend set_on_finished → on route vers notre hook "after"
        self._on_after = cb

    # --------- Pré‑vérification : retourne (ok, payload) ---------
    def _preflight(self, path: str) -> Tuple[bool, Dict[str, Any]]:
        abs_path = os.path.abspath(path)
        if not os.path.exists(path):
            return False, {"ok": False, "error": "file_not_found", "message": f"Fichier introuvable : {abs_path}", "path": abs_path}
        try:
            with _suppress_stderr():
                info = sf.info(path)
            if info.samplerate <= 0 or info.channels <= 0:
                raise RuntimeError(f"Entête invalide (samplerate={info.samplerate}, channels={info.channels})")
            return True, {"ok": True, "path": abs_path, "samplerate": info.samplerate, "channels": info.channels, "frames": int(info.frames), "duration_sec": (float(info.frames)/info.samplerate) if info.samplerate else None}
        except Exception as e:
            ext = os.path.splitext(path)[1].lower()
            fmts = {k.lower() for k in sf.available_formats().keys()}
            if ext == ".mp3" and "mp3" not in fmts:
                return False, {"ok": False, "error": "mp3_unsupported", "message": f"Le MP3 n’est pas activé. Fichier : {abs_path}", "path": abs_path, "details": str(e)}
            return False, {"ok": False, "error": "unreadable_media", "message": f"Impossible d’ouvrir le média : {abs_path}", "path": abs_path, "details": str(e)}

    # ----------------------------- API publique -----------------------------
    def play(self, path: str, *, priority: Literal["low","high"] = "low", volume_item: float = 1.0) -> Dict[str, Any]:
        ok, diag = self._preflight(path)
        if not ok:
            print(f"[info.play] {diag['error']}: {diag['message']}")
            return diag
        item = (path, _clamp(volume_item, 0.0, 1.0), priority)
        with self._lock:
            if priority == "high":
                self._q_low.clear()           # purge toutes les low en attente
                self._q_high.append(item)
                self._interrupt_low.set()     # si un low joue, on l’interrompt
            else:
                self._q_low.append(item)
            need_start = self._thread is None or not self._thread.is_alive()
        if need_start:
            self._stop_all.clear()
            self._thread = threading.Thread(target=self._run_loop, name="InfoPlayer", daemon=True)
            self._thread.start()
        return {"ok": True, "queued": True, "priority": priority, **diag}

    def stop_all(self) -> Dict[str, Any]:
        with self._lock:
            self._q_low.clear()
            self._q_high.clear()
        self._interrupt_low.set()
        self._stop_all.set()
        return {"ok": True, "stopped": True}

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            cur = self._state_playing
            low_n = len(self._q_low)
            high_n = len(self._q_high)
        return {"current": cur, "queue_low": low_n, "queue_high": high_n}

    # --------------------------- boucle de lecture --------------------------
    def _next_item(self) -> Optional[tuple[str, float, str]]:
        with self._lock:
            if self._q_high:
                return self._q_high.popleft()
            if self._q_low:
                return self._q_low.popleft()
            return None

    def _run_loop(self) -> None:
        while not self._stop_all.is_set():
            item = self._next_item()
            if item is None:
                time.sleep(0.02)
                continue
            path, vol_item, prio = item
            self._play_one(path, vol_item, prio)
        with self._lock:
            self._state_playing = None

    def _play_one(self, path: str, vol_item: float, priority: str) -> None:
        # Hook before (duck/cut)
        if self._on_before:
            try:
                self._on_before(path, priority)
            except Exception:
                pass

        try:
            with _suppress_stderr():
                snd = sf.SoundFile(path, mode="r")
        except Exception as e:
            print(f"[info] Erreur d'ouverture: {os.path.abspath(path)} → {e}")
            return

        samplerate = snd.samplerate
        channels = snd.channels

        def current_gain() -> np.float32:
            g = self._get_master() * self._get_info_vol() * vol_item
            return np.float32(_clamp(g, 0.0, 2.0))

        local_stop = False
        ended_normally = False

        def callback(outdata, frames, time_info, status):
            nonlocal local_stop, ended_normally
            if status:
                print("[info][cb] status:", status)
            # interruption par un HIGH si on joue un LOW
            if priority == "low" and self._interrupt_low.is_set():
                local_stop = True
            if local_stop:
                outdata[:] = 0
                raise sd.CallbackStop()
            data = snd.read(frames, dtype="float32", always_2d=True)
            if data.shape[0] == 0:
                outdata[:] = 0
                ended_normally = True
                local_stop = True
                raise sd.CallbackStop()
            outdata[: data.shape[0], : data.shape[1]] = data * current_gain()
            if data.shape[0] < frames:
                outdata[data.shape[0]:, :] = 0
                ended_normally = True
                local_stop = True
                raise sd.CallbackStop()

        @contextmanager
        def _set_playing(path: str, priority: str):
            with self._lock:
                self._state_playing = (path, priority)
            try:
                print(f">> [info:{priority}] Lecture : {_fmt_path(path)}", flush=True)
                yield
            finally:
                with self._lock:
                    self._state_playing = None

        try:
            with _set_playing(path, priority), _suppress_stderr(), sd.OutputStream(
                samplerate=samplerate,
                channels=channels,
                dtype="float32",
                callback=callback,
                blocksize=1024,
                latency="low",
            ) as stream:
                while stream.active and not local_stop and not self._stop_all.is_set():
                    time.sleep(0.02)
        except Exception as e:
            print(f"[info] Erreur de sortie: {os.path.abspath(path)} → {e}")
        finally:
            try:
                snd.close()
            except Exception:
                pass
            # si on a interrompu un low pour un high, on peut maintenant traiter les high ;
            # la main repasse à _run_loop.
            self._interrupt_low.clear()
            if self._on_after:
                try:
                    self._on_after(path, priority, ended_normally)
                except Exception:
                    pass


class InfoController:
    def __init__(self, manager: "SoundManager") -> None:
        self._m = manager
        self._player = _InfoPlayer(
            get_master=lambda: self._m.config.master_volume,
            get_info_vol=lambda: self._m.config.info_volume,
        )
        self._duck_active = False
        self._duck_prev_music = 0.0
        self._duck_prev_journal = 0.0
        self._duck_lock = threading.Lock()
        self._player.set_on_started(self._on_started)
        self._player.set_on_finished(self._on_finished)
        self._low_active = False  # True pendant un LOW en cours

    def _fade(self, role: Literal["music", "journal"], start: float, end: float, ms: int) -> None:
        start = _clamp(start, 0.0, 1.0)
        end = _clamp(end, 0.0, 1.0)
        steps = max(1, int(ms // 50))
        for i in range(1, steps + 1):
            val = start + (end - start) * (i / steps)
            self._m.set_volume(role, val)
            time.sleep(0.05)

    def _start_duck(self):
        with self._duck_lock:
            if self._duck_active:
                return
            self._duck_active = True
            self._duck_prev_music = self._m.config.music_volume
            self._duck_prev_journal = self._m.config.journal_volume
            factor = max(0.0, min(1.0, DUCK_LEVEL_PERCENT / 100.0))
            target_m = self._duck_prev_music * factor
            target_j = self._duck_prev_journal * factor
            ms = self._m.config.duck_fade_ms
            threading.Thread(target=self._fade, args=("music", self._duck_prev_music, target_m, ms), daemon=True).start()
            threading.Thread(target=self._fade, args=("journal", self._duck_prev_journal, target_j, ms), daemon=True).start()

    def _end_duck(self, *, immediate: bool = False):
        with self._duck_lock:
            if not self._duck_active:
                return
            ms = 0 if immediate else self._m.config.duck_fade_ms
            threading.Thread(target=self._fade, args=("music", self._m.config.music_volume, self._duck_prev_music, ms), daemon=True).start()
            threading.Thread(target=self._fade, args=("journal", self._m.config.journal_volume, self._duck_prev_journal, ms), daemon=True).start()
            self._duck_active = False

    def _on_started(self, path: str, priority: str):
        if priority == "low":
            self._low_active = True
            self._start_duck()
            self._m._emit_event({"name": "duck", "state": "on", "payload": {"path": _fmt_path(path)}})
            self._m._emit_event({"name": "info", "state": "low_started", "payload": {"path": _fmt_path(path)}})
        else:  # high
            # si un LOW tournait, considère-le comme interrompu
            if self._low_active:
                self._low_active = False
                self._m._emit_event({"name": "info", "state": "low_interrupted", "payload": {"by": "high"}})
            self._end_duck(immediate=True)
            self._m.music.stop()
            self._m.journal.stop()
            self._m._emit_event({"name": "info", "state": "high_started", "payload": {"path": _fmt_path(path)}})

    def _on_finished(self, path: str, priority: str, ended_normally: bool):
        if priority == "low":
            self._low_active = False
            st = self._player.get_state()
            if st.get("queue_low", 0) == 0:
                self._end_duck(immediate=False)
                self._m._emit_event({"name": "duck", "state": "off", "payload": {}})
            self._m._emit_event({
                "name": "info",
                "state": "low_finished",
                "payload": {"path": _fmt_path(path), "ended_normally": ended_normally},
            })
        else:  # high
            self._m._emit_event({
                "name": "info",
                "state": "high_finished",
                "payload": {"path": _fmt_path(path), "ended_normally": ended_normally},
            })

    def play(self, path: str, *, priority: Literal["low", "high"] = "low", volume_item: float = 1.0, effects: Optional[list[str]] = None) -> Dict[str, Any]:
        self._m._emit_event({
            "name": "info",
            "state": f"{priority}_enqueued",
            "payload": {
                "path": _fmt_path(path),
                "priority": priority,
                "volume_item": float(_clamp(volume_item, 0.0, 1.0)),
            },
        })
        return self._player.play(path, priority=priority, volume_item=volume_item)

    def stop_all(self) -> Dict[str, Any]:
        self._end_duck(immediate=False)
        evt = self._player.stop_all()
        self._m._emit_event({"name": "info", "state": "stop_all", "payload": evt})
        return evt

    def set_volume(self, value: float, *, fade_ms: Optional[int] = None) -> Dict[str, Any]:
        self._m.config.info_volume = _clamp(value, 0.0, 1.0)
        return {"ok": True, "volume": self._m.config.info_volume}

    def get_volume(self) -> Dict[str, Any]:
        return {"ok": True, "volume": self._m.config.info_volume}

    def get_state(self) -> Dict[str, Any]:
        s = self._player.get_state()
        return {"ok": True, **s}


class JournalController:
    """
    Contrôleur public pour le journal. Wrappe _JournalPlayer et expose une API simple.
    """
    def __init__(self, manager: "SoundManager") -> None:
        self._m = manager
        self._player = _JournalPlayer(
            get_master=lambda: self._m.config.master_volume,
            get_journal_vol=lambda: self._m.config.journal_volume,
            emit=lambda evt: self._m._emit_event(evt),
        )
        # anti-course pause différée vs reprise
        self._pause_cancel = threading.Event()

    def _fade_volume(self, start: float, end: float, ms: int) -> None:
        """Fade linéaire du volume musique dans un petit thread (50 ms / pas)."""
        start = _clamp(start, 0.0, 1.0)
        end = _clamp(end, 0.0, 1.0)
        steps = max(1, int(ms // 50))
        for i in range(1, steps + 1):
            if self._pause_cancel.is_set() and end > start:
                pass
            val = start + (end - start) * (i / steps)
            self._m.config.music_volume = val
            time.sleep(0.05)

    def play(self, path: str, *, volume_item: float = 1.0, effects: Optional[list[str]] = None, auto_resume: bool = True, fade_ms: int = 300) -> Dict[str, Any]:
        """Joue un journal. Règles :
        - Si musique joue, **fade-out** puis **pause** la musique.
        - À la fin, **auto‑resume** + **fade-in** si `auto_resume=True` (défaut).
        """
        prev_music_vol = self._m.config.music_volume
        self._pause_cancel.clear()

        def on_finished(_path: str, ended_normally: bool):
            if not auto_resume:
               # print(f">> [journal] fin (ended_normally={ended_normally}) — pas de reprise auto", flush=True)
                return
            self._pause_cancel.set()
            #print(f">> [journal] fin (ended_normally={ended_normally}) — reprise musique", flush=True)
            self._m.music.resume()
            threading.Thread(target=self._fade_volume, args=(0.0, prev_music_vol, fade_ms), daemon=True).start()

        self._player.set_on_finished(on_finished)

        res = self._player.play(path, volume_item)
        if not res.get("ok", False):
            return res

        threading.Thread(target=self._fade_volume, args=(self._m.config.music_volume, 0.0, fade_ms), daemon=True).start()

        def _pause_after():
            time.sleep(max(0, fade_ms) / 1000.0)
            if not self._pause_cancel.is_set():
                self._m.music.pause()
        threading.Thread(target=_pause_after, daemon=True).start()

        return res

    def stop(self) -> Dict[str, Any]:
        res = self._player.stop()
        self._m._emit_event({"name": "journal", "state": "stopped", "payload": {}})
        return res

    def pause(self) -> Dict[str, Any]:
        res = self._player.pause()
        self._m._emit_event({"name": "journal", "state": "paused", "payload": {}})
        return res

    def resume(self) -> Dict[str, Any]:
        res = self._player.resume()
        self._m._emit_event({"name": "journal", "state": "resumed", "payload": {}})
        return res

    def set_volume(self, value: float, *, fade_ms: Optional[int] = None) -> Dict[str, Any]:
        self._m.config.journal_volume = _clamp(value, 0.0, 1.0)
        return {"ok": True, "volume": self._m.config.journal_volume}

    def get_volume(self) -> Dict[str, Any]:
        return {"ok": True, "volume": self._m.config.journal_volume}

    def get_state(self) -> Dict[str, Any]:
        s = self._player.get_state()
        return {"ok": True, **s}


# ---------------------------------------------------------------------------
# Façade SoundManager
# ---------------------------------------------------------------------------
class SoundManager:

    def __init__(self, event_bus: EventBus) -> None:
        """
        Gestionnaire de sons centralisé.
        
        Args:
            event_bus: Bus d'événements **obligatoire** — Les modules publient dessus.
        """
        self.config: Config = Config()  # defaults

        if event_bus is None:
            raise ValueError("event_bus est obligatoire ! Plus de bus privé autorisé.")
        self.events: EventBus = event_bus

        # contrôleurs
        self.music = MusicController(self)
        self.info = InfoController(self)
        self.journal = JournalController(self)

        # logs
        global LOG_FULL_PATHS
        LOG_FULL_PATHS = bool(self.config.log_full_paths)

    # API d'abonnement (convenience)
    def on_event(self, callback):
        """Abonne un callback au bus (alias pratique)."""
        self.events.subscribe(callback)
        return callback

    def off_event(self, token):
        """No-op (le bus minimal ne gère pas l'unsubscribe)."""
        return None

    def _emit_event(self, evt: dict):
        """Route l'événement vers le bus (attend un evt déjà normalisé)."""
        # Sécurise la présence de name/state/payload
        name = evt.get("name")
        state = evt.get("state")
        payload = evt.get("payload", {})
        if name is None or state is None:
            # fallback si ancien format {"name": "x.y"} → tente d'inférer
            raw = evt.get("name", "")
            if isinstance(raw, str) and "." in raw:
                parts = raw.split(".", 1)
                name, state = parts[0], parts[1]
            else:
                raise ValueError("Événement invalide: nécessite 'name' et 'state'")
        self.events.publish({"name": name, "state": state, "payload": payload})

    def emit(self, evt: dict):
        """Alias public pour émettre (modules internes)."""
        self._emit_event(evt)

    # ------------------------------- Config --------------------------------
    def init(self, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        applied: list[str] = []
        ignored: list[str] = []
        if cfg is None:
            return {"ok": True, "applied": applied, "ignored": ignored}
        if not isinstance(cfg, dict):
            return {"ok": False, "error": "invalid_config_type"}

        new_cfg = Config.from_dict(cfg)
        if "log_full_paths" in cfg:
            new_cfg.log_full_paths = bool(cfg["log_full_paths"])

        prev = self.config.to_dict()
        self.config = new_cfg
       
        global LOG_FULL_PATHS
        LOG_FULL_PATHS = bool(self.config.log_full_paths)

        for key in cfg.keys():
            if key not in ACCEPTED_CONFIG_KEYS:
                ignored.append(key)
        for k, v in self.config.to_dict().items():
            if prev.get(k) != v:
                applied.append(k)
        self._emit_event({
            "name": "config",
            "state": "updated",
            "payload": {"applied": applied, "ignored": ignored, **self.config.to_dict()},
        })
        return {"ok": True, "applied": applied, "ignored": ignored}

    def get_config(self) -> Dict[str, Any]:
        return {"ok": True, **self.config.to_dict()}

    # ------------------------------- Volumes -------------------------------
    def set_master_volume(self, value: float, *, fade_ms: Optional[int] = None) -> Dict[str, Any]:
        self.config.master_volume = _clamp(value, 0.0, 1.0)
        self._emit_event({"name": "volume", "state": "master_changed", "payload": {"value": self.config.master_volume}})
        return {"ok": True, "master_volume": self.config.master_volume}

    def get_master_volume(self) -> Dict[str, Any]:
        return {"ok": True, "master_volume": self.config.master_volume}

    def set_volume(self, role: Role, value: float, *, fade_ms: Optional[int] = None) -> Dict[str, Any]:
        v = _clamp(value, 0.0, 1.0)
        if role == "music":
            self.config.music_volume = v
        elif role == "journal":
            self.config.journal_volume = v
        elif role == "info":
            self.config.info_volume = v
        else:
            return {"ok": False, "error": "unknown_role", "role": role}
        self._emit_event({"name": "volume", "state": f"{role}_changed", "payload": {"role": role, "value": v}})
        return {"ok": True, "role": role, "volume": v}

    # ------------------------------- État ----------------------------------
    def get_state(self) -> Dict[str, Any]:
        music_state = self.music.get_state()
        journal_state = self.journal.get_state()
        return {
            "ok": True,
            "master": self.config.master_volume,
            "volumes": {
                "music": self.config.music_volume,
                "journal": self.config.journal_volume,
                "info": self.config.info_volume,
            },
            "music": music_state if music_state.get("ok") else music_state,
            "journal": journal_state if journal_state.get("ok") else journal_state,
            "info": self.info.get_state(),
            "duck": {"fade_ms": self.config.duck_fade_ms, "level_percent": DUCK_LEVEL_PERCENT},
        }
