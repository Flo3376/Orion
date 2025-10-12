from __future__ import annotations
from typing import Optional, Dict, Any, Callable, List
import threading
import time
import os
import subprocess

try:
    import psutil  # facultatif (Windows) pour détecter le process Spotify
except Exception:  # pragma: no cover
    psutil = None  # type: ignore

from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# Ton bus minimal (assert: msg contient 'name' et 'state')
#   msg = { 'name': <str>, 'state': <str>, 'payload': <dict (opt.)> }
from core.bus import EventBus


class SpotifyController:
    """
    Contrôleur Spotify, compatible avec ton EventBus (name/state/payload).

    - Émet des messages sur le bus :
        { 'name': <event_prefix>, 'state': <etat>, 'payload': {...} }
      with `event_prefix` par défaut "spotify".

    États émis typiques :
      • ready            → payload: { device: {id,name,type} }
      • playback         → payload (minimal si demandé):
            {
              'playing': bool, 'title': str|None, 'artists': [str], 'album': str|None,
              'pos': int|None, 'dur': int|None, 'thumb': str|None,
              'volume': int|None, 'device': str|None
            }
      • track_changed    → payload: { track_id, title, artists }
      • paused / playing → payload réduit (progress/duration)
      • idle             → aucune lecture en cours
      • error            → payload: { code, message, ... }

    Commandes publiques : play(), pause(), next(), previous(), set_volume(), volume_up(), volume_down()
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str = "user-modify-playback-state user-read-playback-state user-read-currently-playing",
        event_bus: Optional[EventBus] = None,
        poll_interval: float = 3.0,
        open_app_if_needed: bool = True,
        device_name_preference: Optional[str] = None,
        cache_path: str = ".cache_spotify_controller",
        # Adaptation bus
        event_prefix: str = "spotify",
        event_map: Optional[Dict[str, str]] = None,
        payload_minimal: bool = False,
    ) -> None:
        self.bus = event_bus or EventBus()
        self.name = (event_prefix or "spotify").strip()
        self.event_map = event_map or {}
        self.payload_minimal = bool(payload_minimal)

        self.poll_interval = max(0.5, float(poll_interval))
        self.device_name_preference = device_name_preference
        self._stop_evt = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None

        # 1) Option : lancer Spotify localement si possible (Windows)
        if open_app_if_needed:
            self._ensure_spotify_running()

        # 2) Auth Spotify (Spotipy)
        self.sp = Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                cache_path=cache_path,
                open_browser=True,
                requests_timeout=10,
            )
        )

        # 3) Sélection du device actif
        self.device = self._select_or_activate_device()
        if self.device:
            self._emit("ready", {"device": self._slim_device(self.device)})
        else:
            self._emit_error("no_device", "Aucun device Spotify Connect actif. Ouvre l'app Spotify et reconnecte-toi.")

        # 4) Polling d'état
        self._start_polling()

    # ----------------- Emission bus -----------------
    def _map_state(self, state: str) -> str:
        return self.event_map.get(state, state)

    def _emit(self, state: str, payload: Optional[Dict[str, Any]] = None) -> None:
        msg = {
            "name": self.name,
            "state": self._map_state(state),
            "payload": payload or {},
        }
        try:
            self.bus.publish(msg)
        except Exception as e:  # protège contre erreurs des abonnés
            print(f"[SpotifyController] bus.publish error: {e}")

    def _emit_error(self, code: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        p = {"code": code, "message": message}
        if extra:
            p.update(extra)
        self._emit("error", p)

    # ----------------- Spotify locaux -----------------
    def _ensure_spotify_running(self) -> None:
        """Essaye d'ouvrir Spotify si pas lancé (Windows). Optionnel."""
        try:
            if psutil is None:
                self._emit("app_check", {"status": "psutil_unavailable", "message": "psutil non disponible, impossible de vérifier si Spotify est lancé"})
                return
            
            # Vérifier si Spotify est déjà lancé
            for p in psutil.process_iter(attrs=["name"]):
                if (p.info.get("name") or "").lower() == "spotify.exe":
                    self._emit("app_check", {"status": "already_running", "message": "Spotify est déjà en cours d'exécution"})
                    return
            # Tentatives de lancement
            self._emit("app_launch", {"status": "attempting", "message": "Tentative de lancement de Spotify"})
            candidates = [
                os.path.expandvars(r"%APPDATA%\\Spotify\\Spotify.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\\Microsoft\\WindowsApps\\Spotify.exe"),
            ]
            for path in candidates:
                if os.path.isfile(path):
                    self._emit("app_launch", {"status": "launching", "method": "executable", "path": path})
                    subprocess.Popen([path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(1.5)
                    self._emit("app_launch", {"status": "launched", "method": "executable"})
                    return
            try:
                self._emit("app_launch", {"status": "launching", "method": "protocol", "uri": "spotify:"})
                os.startfile("spotify:")  # type: ignore[attr-defined]
                time.sleep(1.5)
                self._emit("app_launch", {"status": "launched", "method": "protocol"})
            except Exception as e:
                self._emit("app_launch", {"status": "protocol_failed", "error": str(e)})
        except Exception as e:
            self._emit_error("launch_failed", str(e))

    def _select_or_activate_device(self) -> Optional[Dict[str, Any]]:
        try:
            self._emit("device_scan", {"status": "scanning", "message": "Recherche des périphériques Spotify Connect"})
            devices = (self.sp.devices() or {}).get("devices", [])
            
            if not devices:
                self._emit("device_scan", {"status": "no_devices", "message": "Aucun périphérique Spotify Connect trouvé"})
                return None
            
            self._emit("device_scan", {"status": "found", "count": len(devices), "devices": [d.get("name") for d in devices]})
            
            chosen = None
            if self.device_name_preference:
                for d in devices:
                    if self.device_name_preference.lower() in (d.get("name") or "").lower():
                        chosen = d
                        self._emit("device_select", {"status": "preferred_found", "device": d.get("name"), "id": d.get("id")})
                        break
                        
            if not chosen:
                active_device = next((d for d in devices if d.get("is_active")), None)
                chosen = active_device or devices[0]
                selection_reason = "active" if active_device else "first_available"
                self._emit("device_select", {"status": "auto_selected", "reason": selection_reason, "device": chosen.get("name"), "id": chosen.get("id")})
            
            # Transférer la lecture vers ce device sans auto-play
            try:
                self._emit("device_transfer", {"status": "transferring", "to_device": chosen.get("name"), "id": chosen.get("id")})
                self.sp.transfer_playback(chosen["id"], force_play=False)
                self._emit("device_transfer", {"status": "transferred", "to_device": chosen.get("name")})
            except Exception as e:
                self._emit("device_transfer", {"status": "failed", "error": str(e)})
            return chosen
        except Exception as e:
            self._emit_error("device_query_failed", str(e))
            return None

    def _slim_device(self, d: Dict[str, Any]) -> Dict[str, Any]:
        if not d:
            return {}
        if self.payload_minimal:
            return {"id": d.get("id"), "name": d.get("name"), "type": d.get("type")}
        return d

    # ----------------- Polling -----------------
    def _start_polling(self) -> None:
        if self._poll_thread and self._poll_thread.is_alive():
            self._emit("polling", {"status": "already_running", "message": "Le polling est déjà actif"})
            return
        self._emit("polling", {"status": "starting", "interval": self.poll_interval, "message": "Démarrage du polling de l'état Spotify"})
        self._stop_evt.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, name="SpotifyPoll", daemon=True)
        self._poll_thread.start()
        self._emit("polling", {"status": "started", "message": "Polling démarré avec succès"})

    def stop(self) -> None:
        self._emit("polling", {"status": "stopping", "message": "Arrêt du polling en cours"})
        self._stop_evt.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2)
        self._emit("polling", {"status": "stopped", "message": "Polling arrêté"})

    def _poll_loop(self) -> None:
        last_track_id: Optional[str] = None
        while not self._stop_evt.is_set():
            try:
                pb = self.sp.current_playback()
                if pb:
                    payload = self._playback_payload(pb)
                    self._emit("playback", payload)

                    item = pb.get("item") or {}
                    track_id = item.get("id")
                    if track_id and track_id != last_track_id:
                        last_track_id = track_id
                        self._emit("track_changed", {
                            "track_id": track_id,
                            "title": item.get("name"),
                            "artists": [a.get("name") for a in (item.get("artists") or [])],
                        })

                    self._emit("playing" if payload.get("playing") else "paused", {
                        "progress_ms": payload.get("pos"),
                        "duration_ms": payload.get("dur"),
                    })
                else:
                    self._emit("idle", {})
            except Exception as e:
                self._emit_error("poll_failure", str(e))
            finally:
                time.sleep(self.poll_interval)

    def _playback_payload(self, pb: Dict[str, Any]) -> Dict[str, Any]:
        item = pb.get("item") or {}
        album = item.get("album") or {}
        images: List[Dict[str, Any]] = album.get("images") or []
        thumb = images[0]["url"] if images else None
        artists = [a.get("name") for a in (item.get("artists") or [])]
        device = pb.get("device") or {}

        base = {
            "playing": bool(pb.get("is_playing", False)),
            "title": item.get("name"),
            "artists": artists,
            "album": album.get("name"),
            "pos": pb.get("progress_ms"),
            "dur": item.get("duration_ms"),
            "thumb": thumb,
            "volume": device.get("volume_percent"),
            "device": device.get("name"),
        }
        if self.payload_minimal:
            return base
        # payload complet (si besoin futur)
        base.update({
            "device_info": {
                "id": device.get("id"),
                "type": device.get("type"),
            }
        })
        return base

    # ----------------- API publique -----------------
    def play(self, uri: Optional[str] = None, *, context_uri: Optional[str] = None, position_ms: Optional[int] = None) -> None:
        try:
            if uri:
                self._emit("command", {"action": "play_track", "uri": uri, "position_ms": position_ms})
                self.sp.start_playback(device_id=self._device_id(), uris=[uri], position_ms=position_ms)
            elif context_uri:
                self._emit("command", {"action": "play_context", "context_uri": context_uri, "position_ms": position_ms})
                self.sp.start_playback(device_id=self._device_id(), context_uri=context_uri, position_ms=position_ms)
            else:
                self._emit("command", {"action": "resume", "message": "Reprise de la lecture"})
                self.sp.start_playback(device_id=self._device_id())
            
            self._emit("command_success", {"action": "play", "message": "Commande de lecture envoyée avec succès"})
        except Exception as e:
            self._emit_error("play_failed", str(e))

    def pause(self) -> None:
        try:
            self._emit("command", {"action": "pause", "message": "Mise en pause de la lecture"})
            self.sp.pause_playback(device_id=self._device_id())
            self._emit("command_success", {"action": "pause", "message": "Lecture mise en pause"})
        except Exception as e:
            self._emit_error("pause_failed", str(e))

    def next(self) -> None:
        try:
            self._emit("command", {"action": "next", "message": "Passage à la piste suivante"})
            self.sp.next_track(device_id=self._device_id())
            self._emit("command_success", {"action": "next", "message": "Piste suivante activée"})
        except Exception as e:
            self._emit_error("next_failed", str(e))

    def previous(self) -> None:
        try:
            self._emit("command", {"action": "previous", "message": "Retour à la piste précédente"})
            self.sp.previous_track(device_id=self._device_id())
            self._emit("command_success", {"action": "previous", "message": "Piste précédente activée"})
        except Exception as e:
            self._emit_error("previous_failed", str(e))

    def set_volume(self, percent: int) -> None:
        p = max(0, min(100, int(percent)))
        try:
            self._emit("volume_command", {"action": "set_volume", "from_volume": None, "to_volume": p})
            self.sp.volume(p, device_id=self._device_id())
            self._emit("volume_success", {"action": "set_volume", "volume": p, "message": f"Volume réglé à {p}%"})
        except Exception as e:
            self._emit_error("volume_failed", str(e), {"requested": p})

    def volume_up(self, step: int = 5) -> None:
        try:
            state = self.sp.current_playback() or {}
            device = state.get("device") or {}
            cur = int(device.get("volume_percent") or 0)
            new_vol = cur + abs(step)
            self._emit("volume_command", {"action": "volume_up", "from_volume": cur, "to_volume": new_vol, "step": abs(step)})
            self.set_volume(new_vol)
        except Exception as e:
            self._emit_error("volume_up_failed", str(e))

    def volume_down(self, step: int = 5) -> None:
        try:
            state = self.sp.current_playback() or {}
            device = state.get("device") or {}
            cur = int(device.get("volume_percent") or 0)
            new_vol = cur - abs(step)
            self._emit("volume_command", {"action": "volume_down", "from_volume": cur, "to_volume": new_vol, "step": abs(step)})
            self.set_volume(new_vol)
        except Exception as e:
            self._emit_error("volume_down_failed", str(e))

    # ----------------- Utils -----------------
    def _device_id(self) -> Optional[str]:
        return (self.device or {}).get("id")
