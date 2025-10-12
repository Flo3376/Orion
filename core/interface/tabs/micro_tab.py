# /core/interface/tabs/micro_tab.py
"""
Onglet Micro - VU-mètre et sélection micro (basé sur audio_input_tester.py)
"""

from __future__ import annotations
import math
import queue
from typing import List, Tuple, Optional

import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus

DBFS_FLOOR = -60.0  # lower bound for the meter scale
UPDATE_INTERVAL_MS = 50  # UI refresh rate
BLOCKSIZE = 1024
DTYPE = 'float32'


def list_input_devices() -> List[Tuple[int, str]]:
    """Return WASAPI devices only (modern Windows audio API)."""
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    items = []
    
    for idx, dev in enumerate(devices):
        if dev.get('max_input_channels', 0) > 0:
            host_name = hostapis[dev['hostapi']]['name']
            
            # WASAPI seulement - API moderne recommandée
            if host_name == 'Windows WASAPI':
                device_name = dev['name']
                label = f"{device_name} (in:{dev['max_input_channels']})"  # Plus simple sans [API]
                items.append((idx, label))
                print(f"🎤 WASAPI device {idx}: {device_name}")
    
    items.sort(key=lambda x: x[1])
    print(f"📋 {len(items)} micros WASAPI trouvés")
    return items


def build_device_key(dev_info: dict) -> str:
    """Construit une clé unique pour le périphérique"""
    host = sd.query_hostapis()[dev_info['hostapi']]['name']
    name = dev_info['name']
    return f"{host}:{name}"


class AudioMeterWidget(QtWidgets.QWidget):
    """Un vu-mètre horizontal dBFS de DBFS_FLOOR à 0 dBFS."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(35)
        self.setMaximumHeight(35)
        self.setMinimumWidth(300)
        self._dbfs = -math.inf

    def set_dbfs(self, db: float):
        self._dbfs = db
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):
        p = QtGui.QPainter(self)
        rect = self.rect()
        
        # Background LCARS style
        p.fillRect(rect, QtGui.QColor(11, 15, 23))  # LCARS_BG
        
        # Border
        pen = QtGui.QPen(QtGui.QColor(0, 209, 255))  # LCARS_ACCENT2
        pen.setWidth(2)
        p.setPen(pen)
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)

        # Meter fill
        if np.isfinite(self._dbfs):
            frac = (self._dbfs - DBFS_FLOOR) / (0.0 - DBFS_FLOOR)
            frac = float(np.clip(frac, 0.0, 1.0))
        else:
            frac = 0.0

        if frac > 0:
            fill_width = int(frac * (rect.width() - 8))
            fill_rect = QtCore.QRect(rect.left() + 4, rect.top() + 4, fill_width, rect.height() - 8)
            
            # Color gradient from green to yellow to red (style LCARS)
            if self._dbfs < -30:
                color = QtGui.QColor(0, 255, 0)  # Vert
            elif self._dbfs < -12:
                # Transition vert -> jaune
                ratio = (self._dbfs + 30) / 18  # -30 to -12
                color = QtGui.QColor(int(255 * ratio), 255, 0)
            else:
                # Transition jaune -> rouge
                ratio = (self._dbfs + 12) / 12  # -12 to 0
                color = QtGui.QColor(255, int(255 * (1 - ratio)), 0)
            
            p.fillRect(fill_rect, color)

        # Current value text (style LCARS)
        p.setPen(QtGui.QPen(QtGui.QColor(230, 230, 235)))
        font = p.font()
        font.setPointSize(10)
        font.setWeight(QtGui.QFont.Weight.Bold)
        p.setFont(font)
        
        label = "RMS: -∞ dBFS" if not np.isfinite(self._dbfs) else f"RMS: {self._dbfs:0.1f} dBFS"
        p.drawText(rect.adjusted(8, 4, -8, -4), QtCore.Qt.AlignmentFlag.AlignCenter, label)


class AudioWorker(QtCore.QObject):
    """Manages the audio stream and produces RMS values."""
    level = QtCore.Signal(float)

    def __init__(self, device_index: Optional[int] = None, samplerate: Optional[float] = None, channels: int = 1):
        super().__init__()
        self.device_index = device_index
        self.samplerate = samplerate
        self.channels = channels
        self._stream: Optional[sd.InputStream] = None
        self._q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=8)
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._process_queue)
        self._timer.start(UPDATE_INTERVAL_MS)

    def _audio_callback(self, indata, frames, time, status):
        if status:
            pass  # Non-fatal; could log status
        # Collapse to mono by averaging channels
        data = np.mean(indata.astype(np.float32), axis=1)
        try:
            self._q.put_nowait(data.copy())
        except queue.Full:
            pass  # Drop if UI is lagging

    def _process_queue(self):
        if self._q.empty():
            return
        buf = []
        while not self._q.empty():
            try:
                buf.append(self._q.get_nowait())
            except queue.Empty:
                break
        if not buf:
            return
        x = np.concatenate(buf)
        rms = float(np.sqrt(np.mean(np.square(x), dtype=np.float64)))
        if rms <= 1e-9 or not np.isfinite(rms):
            dbfs = -math.inf
        else:
            dbfs = 20.0 * math.log10(rms)
            dbfs = max(DBFS_FLOOR, min(0.0, dbfs))
        self.level.emit(dbfs)

    def is_running(self) -> bool:
        return self._stream is not None

    def start(self):
        self.stop()
        if self.device_index is None:
            raise RuntimeError("No input device selected.")
        dev_info = sd.query_devices(self.device_index)
        sr = self.samplerate or dev_info.get('default_samplerate', 48000) or 48000
        ch = min(self.channels, max(1, dev_info.get('max_input_channels', 1)))
        self._stream = sd.InputStream(
            device=self.device_index,
            channels=ch,
            samplerate=sr,
            blocksize=BLOCKSIZE,
            dtype=DTYPE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None


class MicroTab(QtWidgets.QWidget):
    """Onglet pour la gestion du micro avec VU-mètre"""
    
    def __init__(self, event_bus: EventBus):
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = None  # Sera défini via set_config_manager
        self._is_tab_visible = False  # Pour savoir si on est sur cet onglet
        self._setup_ui()
        self._setup_audio()
        self._populate_devices()

    def set_config_manager(self, config_manager):
        """Définit le gestionnaire de configuration"""
        self.config_manager = config_manager
        self._select_config_microphone()

    def _setup_ui(self):
        """Configure l'interface de l'onglet"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        
        # === Section sélection micro ===
        device_group = QtWidgets.QGroupBox("SÉLECTION MICROPHONE")
        device_layout = QtWidgets.QVBoxLayout(device_group)
        device_layout.setSpacing(8)
        
        # Ligne sélection + refresh
        select_layout = QtWidgets.QHBoxLayout()
        
        label = QtWidgets.QLabel("Périphérique:")
        label.setMaximumWidth(80)
        label.setStyleSheet("""
                QLabel {
                    font-weight: 700;
                    color: #ff9f1c;  /* Couleur LCARS orange */
                    letter-spacing: 1px;
                }
            """)
        select_layout.addWidget(label)
        
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setMinimumHeight(32)
        self.device_combo.setToolTip("Sélectionnez votre microphone d'entrée")  # Aide visuelle
        select_layout.addWidget(self.device_combo, 1)
        
        self.refresh_btn = QtWidgets.QPushButton("REFRESH")
        self.refresh_btn.setMaximumWidth(100)
        self.refresh_btn.setToolTip("Actualiser la liste des microphones")
        select_layout.addWidget(self.refresh_btn)
        
        device_layout.addLayout(select_layout)
        
        # Ligne infos device
        """info_layout = QtWidgets.QHBoxLayout()
        
        clef_label = QtWidgets.QLabel("Clé:")
        clef_label.setMaximumWidth(30)
        info_layout.addWidget(clef_label)
        
        self.key_edit = QtWidgets.QLineEdit()
        self.key_edit.setReadOnly(True)
        self.key_edit.setPlaceholderText("hostapi:nom")
        info_layout.addWidget(self.key_edit, 1)
        
        self.index_label = QtWidgets.QLabel("Index: -")
        self.index_label.setMinimumWidth(70)
        info_layout.addWidget(self.index_label)
        
        device_layout.addLayout(info_layout)"""
        
        layout.addWidget(device_group)
        
        # === Section VU-mètre ===
        meter_group = QtWidgets.QGroupBox("VU-MÈTRE RMS dBFS")
        meter_layout = QtWidgets.QVBoxLayout(meter_group)
        meter_layout.setSpacing(8)
        
        # Le vu-mètre
        self.meter = AudioMeterWidget()
        meter_layout.addWidget(self.meter)
        
        # Status uniquement (plus de boutons start/stop)
        self.status_label = QtWidgets.QLabel("En attente de sélection d'onglet...")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        meter_layout.addWidget(self.status_label)
        
        layout.addWidget(meter_group)
        
        # === Section configuration ===
        config_group = QtWidgets.QGroupBox("CONFIG")
        config_layout = QtWidgets.QVBoxLayout(config_group)
        config_layout.setSpacing(6)
        
        # Ligne bouton sauvegarder plus compacte
        save_layout = QtWidgets.QHBoxLayout()
        save_layout.addWidget(QtWidgets.QLabel("Micro sélectionné:"))
        
        self.save_btn = QtWidgets.QPushButton("SAUVEGARDER")
        self.save_btn.setEnabled(False)  # Pas encore câblé
        save_layout.addWidget(self.save_btn)
        
        config_layout.addLayout(save_layout)
        
        # Note d'info plus courte
        info_label = QtWidgets.QLabel("💾 Mettra à jour config.yaml (listen.Microphone)")
        info_label.setStyleSheet("color: #00d1ff; font-style: italic; font-size: 12px;")
        config_layout.addWidget(info_label)
        
        layout.addWidget(config_group)

    def _setup_audio(self):
        """Configure le worker audio"""
        self.worker = AudioWorker()
        self.worker.level.connect(self.meter.set_dbfs)
        
        # Connecter les signaux
        self.refresh_btn.clicked.connect(self._populate_devices)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.save_btn.clicked.connect(self._on_save_config)  # ← DÉCOMMENTER cette ligne

    def _populate_devices(self):
        """Remplit la liste des périphériques audio"""
        prev_index = self.device_combo.currentData() if self.device_combo.count() else None
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        
        try:
            inputs = list_input_devices()
            if not inputs:
                self.device_combo.addItem("Aucun périphérique d'entrée trouvé", None)
                self.device_combo.setEnabled(False)
            else:
                for idx, label in inputs:
                    self.device_combo.addItem(label, idx)
                self.device_combo.setEnabled(True)
                
                # Restaurer la sélection précédente si possible
                if prev_index is not None:
                    for i in range(self.device_combo.count()):
                        if self.device_combo.itemData(i) == prev_index:
                            self.device_combo.setCurrentIndex(i)
                            break
        except Exception as e:
            self.device_combo.addItem(f"Erreur: {e}", None)
            self.device_combo.setEnabled(False)
        
        self.device_combo.blockSignals(False)
        self._update_device_info()
        
        # Sélectionner le micro de la config après le rafraîchissement
        if self.config_manager:
            self._select_config_microphone()

    def _select_config_microphone(self):
        """Sélectionne le microphone configuré dans config.listen.Microphone"""
        if not self.config_manager:
            return
        
        try:
            # Récupérer l'ID du micro depuis la config
            config_mic_id = self.config_manager.get("listen.Microphone")
            if config_mic_id is None:
                return
            
            # Chercher et sélectionner ce micro dans la combo
            for i in range(self.device_combo.count()):
                device_index = self.device_combo.itemData(i)
                if device_index == config_mic_id:
                    self.device_combo.setCurrentIndex(i)
                    print(f"🎤 Micro sélectionné depuis config: Index {config_mic_id}")
                    return
            
            print(f"⚠️ Micro configuré (Index {config_mic_id}) non trouvé dans la liste")
            
        except Exception as e:
            print(f"❌ Erreur lors de la sélection du micro configuré: {e}")

    def _update_device_info(self):
        """Met à jour les infos du périphérique sélectionné"""
        dev_index = self.device_combo.currentData()
        if dev_index is None:
            #self.key_edit.setText("")
            #self.index_label.setText("Index: -")
            return
        
        try:
            dev_info = sd.query_devices(dev_index)
            #key = build_device_key(dev_info)
            #self.key_edit.setText(key)
            #self.index_label.setText(f"Index: {dev_index}")
            print(f"🎤 Micro sélectionné: {dev_info['name']} (Index: {dev_index})")
        except Exception as e:
            # self.key_edit.setText(f"Erreur: {e}")
            # self.index_label.setText("Index: -")
            print(f"❌ Erreur info micro: {e}")

    def _auto_start_if_visible(self):
        """Démarre automatiquement si l'onglet est visible et un micro sélectionné"""
        if not self._is_tab_visible:
            return
            
        dev_index = self.device_combo.currentData()
        if dev_index is None:
            self.status_label.setText("Aucun périphérique sélectionné.")
            return
        
        if self.worker.is_running():
            return  # Déjà en cours
        
        self.worker.device_index = dev_index
        self.worker.samplerate = None
        self.worker.channels = 1
        
        try:
            self.worker.start()
            self.status_label.setText("🎤 VU-mètre actif")
        except Exception as e:
            self.status_label.setText(f"Erreur: {e}")

    def _on_device_changed(self, idx: int):
        """Appelé quand le périphérique change"""
        self._update_device_info()
        
        # Activer le bouton sauvegarder s'il y a une sélection
        if self.device_combo.currentData() is not None:
            self.save_btn.setEnabled(True)
        else:
            self.save_btn.setEnabled(False)
        
        # Redémarrage automatique si l'onglet est visible
        if self._is_tab_visible:
            self.worker.stop()
            self._auto_start_if_visible()

    def on_tab_show(self):
        """Appelé quand cet onglet devient visible"""
        self._is_tab_visible = True
        print("🎤 Onglet Micro visible - démarrage du VU-mètre")
        self._auto_start_if_visible()

    def on_tab_hide(self):
        """Appelé quand on quitte cet onglet"""
        self._is_tab_visible = False
        print("🎤 Onglet Micro masqué - arrêt du VU-mètre")
        self.worker.stop()
        self.status_label.setText("VU-mètre arrêté (onglet masqué)")

    def _on_save_config(self):
        """Sauvegarde le micro sélectionné dans la config"""
        dev_index = self.device_combo.currentData()
        if dev_index is not None and self.config_manager:
            try:
                # Sauvegarder dans la config
                self.config_manager.set("listen.Microphone", dev_index)
                
                # Obtenir le nom du device pour l'affichage
                dev_info = sd.query_devices(dev_index)
                device_name = dev_info['name']
                
                self.status_label.setText(f"💾 Micro sauvegardé: {device_name}")
                self.save_btn.setEnabled(False)  # Désactiver après sauvegarde
                
                print(f"✅ Config sauvegardée: listen.Microphone = {dev_index} ({device_name})")
                
            except Exception as e:
                self.status_label.setText(f"❌ Erreur sauvegarde: {e}")
                print(f"❌ Erreur lors de la sauvegarde: {e}")
        else:
            self.status_label.setText("Aucun micro sélectionné à sauvegarder")

    def closeEvent(self, event):
        """Nettoyage lors de la fermeture"""
        try:
            self.worker.stop()
        except Exception:
            pass
        super().closeEvent(event)