"""
Mini LCARS‑style Qt demo for Windows (PySide6)
------------------------------------------------
This tiny app loads three fields from your YAML config (listen section):
  - language (combo box)
  - hotword (line edit)
  - debug_listen (toggle)

It updates only these three keys and writes a new file next to the original
(e.g. config-exemple.updated.yaml) so your full config stays safe.

Run:
  pip install PySide6 pyyaml
  python lcars_demo.py  # (save this file as lcars_demo.py)

Optional:
  python lcars_demo.py --config "C:/path/to/config-exemple.yaml"
"""
from __future__ import annotations
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict

import yaml  # pip install pyyaml
from PySide6 import QtCore, QtGui, QtWidgets

# ---------------------------
# Config model
# ---------------------------
@dataclass
class ListenConfig:
    language: str = "fr-FR"
    hotword: str = "Swan"
    debug_listen: bool = False

    @classmethod
    def from_yaml(cls, data: Dict[str, Any]) -> "ListenConfig":
        listen = (data or {}).get("listen", {}) or {}
        return cls(
            language=str(listen.get("language", cls.language)).strip("'\" "),
            hotword=str(listen.get("hotword", cls.hotword)).strip("'\" "),
            debug_listen=bool(listen.get("debug_listen", cls.debug_listen)),
        )

    def apply_to_yaml(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data = data.copy() if data else {}
        listen = dict(data.get("listen", {}) or {})
        listen.update({
            "language": self.language,
            "hotword": self.hotword,
            "debug_listen": bool(self.debug_listen),
        })
        data["listen"] = listen
        return data

# ---------------------------
# LCARS-ish styling helpers
# ---------------------------
LCARS_BG = "#0b0f17"      # deep space
LCARS_ACCENT = "#ff9f1c"  # amber panel
LCARS_ACCENT2 = "#00d1ff" # cyan glow
LCARS_TEXT = "#e6e6e6"

STYLE = f"""
* {{
  font-family: Segoe UI, Roboto, Arial, sans-serif;
  color: {LCARS_TEXT};
}}
QWidget {{
  background: {LCARS_BG};
}}
QGroupBox {{
  border: 0px solid transparent;
  margin-top: 16px;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: 8px;
  padding: 2px 6px;
  background: {LCARS_ACCENT};
  border-radius: 10px;
  color: black;
  font-weight: 700;
}}
QLabel {{
  font-size: 14px;
  letter-spacing: 0.5px;
}}
QLineEdit, QComboBox {{
  background: rgba(255,255,255,0.05);
  border: 2px solid {LCARS_ACCENT2};
  padding: 8px 10px;
  border-radius: 12px;
}}
QCheckBox::indicator {{
  width: 26px; height: 26px;
}}
QCheckBox::indicator:unchecked {{
  border: 2px solid {LCARS_ACCENT2};
  background: rgba(0,0,0,0.2);
  border-radius: 6px;
}}
QCheckBox::indicator:checked {{
  border: 2px solid {LCARS_ACCENT2};
  background: {LCARS_ACCENT2};
  border-radius: 6px;
}}
QPushButton {{
  background: {LCARS_ACCENT};
  color: black;
  border: none;
  padding: 10px 16px;
  border-radius: 14px;
  font-weight: 700;
}}
QPushButton:hover {{ filter: brightness(1.05); }}
QPushButton:disabled {{ background: #3a3a3a; color: #999; }}
"""

# ---------------------------
# Main window
# ---------------------------
class LcarsWindow(QtWidgets.QWidget):
    def __init__(self, cfg_path: Path):
        super().__init__()
        self.cfg_path = cfg_path
        self.setWindowTitle("LCARS Demo – Listen Config")
        self.setMinimumSize(560, 360)
        self.setWindowIcon(QtGui.QIcon())

        self.data: Dict[str, Any] = self._load_yaml(cfg_path)
        self.model = ListenConfig.from_yaml(self.data)

        # Header strip (LCARS vibe)
        header = QtWidgets.QFrame()
        header.setFixedHeight(64)
        header.setStyleSheet(f"background: {LCARS_ACCENT}; border-bottom-left-radius: 24px; border-bottom-right-radius: 24px;")
        title = QtWidgets.QLabel("STAR • INTERFACE • LISTEN")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: black; font-weight: 900; letter-spacing: 2px; font-size: 18px;")
        hbox = QtWidgets.QHBoxLayout(header)
        hbox.setContentsMargins(16, 8, 16, 8)
        hbox.addWidget(title)

        # Form group
        group = QtWidgets.QGroupBox("listen")
        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft|QtCore.Qt.AlignmentFlag.AlignVCenter)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(14)

        # language
        self.cmb_language = QtWidgets.QComboBox()
        # A few sensible defaults; you can add more later
        self.cmb_language.addItems(["fr-FR", "en-US", "en-GB", "de-DE", "es-ES"]) 
        try:
            idx = self.cmb_language.findText(self.model.language)
            if idx >= 0:
                self.cmb_language.setCurrentIndex(idx)
        except Exception:
            pass
        form.addRow(self._lab("language"), self.cmb_language)

        # hotword
        self.ed_hotword = QtWidgets.QLineEdit(self.model.hotword)
        self.ed_hotword.setPlaceholderText("Ex: Swan")
        form.addRow(self._lab("hotword"), self.ed_hotword)

        # debug_listen
        self.chk_debug = QtWidgets.QCheckBox("enabled")
        self.chk_debug.setChecked(self.model.debug_listen)
        form.addRow(self._lab("debug_listen"), self.chk_debug)

        group.setLayout(form)

        # Buttons
        btn_load = QtWidgets.QPushButton("Open config…")
        btn_save = QtWidgets.QPushButton("Save as new file")
        btn_save.setDefault(True)
        btn_load.clicked.connect(self.on_open)
        btn_save.clicked.connect(self.on_save)

        # Layout
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)
        root.addWidget(header)
        root.addWidget(group)

        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn_load)
        row.addWidget(btn_save)
        root.addLayout(row)

        self.setStyleSheet(STYLE)

    def _lab(self, text: str) -> QtWidgets.QLabel:
        lab = QtWidgets.QLabel(text)
        lab.setToolTip(text)
        return lab

    def on_open(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select YAML config", str(self.cfg_path.parent), "YAML files (*.yaml *.yml);;All files (*)")
        if not path:
            return
        self.cfg_path = Path(path)
        self.data = self._load_yaml(self.cfg_path)
        self.model = ListenConfig.from_yaml(self.data)
        # refresh fields
        idx = self.cmb_language.findText(self.model.language)
        if idx >= 0:
            self.cmb_language.setCurrentIndex(idx)
        self.ed_hotword.setText(self.model.hotword)
        self.chk_debug.setChecked(self.model.debug_listen)

    def on_save(self):
        # collect from UI -> model
        self.model.language = self.cmb_language.currentText().strip()
        self.model.hotword = self.ed_hotword.text().strip()
        self.model.debug_listen = self.chk_debug.isChecked()

        # apply into the full YAML and write new file
        new_data = self.model.apply_to_yaml(self.data)
        out_path = self.cfg_path.with_suffix("")
        out_path = out_path.parent / (out_path.name + ".updated.yaml")
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(new_data, f, sort_keys=False, allow_unicode=True)

        QtWidgets.QMessageBox.information(self, "Saved", f"Updated file written to:\n{out_path}")

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Error", f"Cannot read file:\n{e}")
            return {}
        try:
            return yaml.safe_load(text) or {}
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Error", f"YAML parse error:\n{e}")
            return {}

# ---------------------------
# Entry point
# ---------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("./config-exemple.yaml"), help="Path to YAML config")
    args = ap.parse_args()

    app = QtWidgets.QApplication([])
    app.setApplicationName("LCARS Demo")

    win = LcarsWindow(args.config)
    # center on screen
    geo = win.frameGeometry()
    scr = QtGui.QGuiApplication.primaryScreen().availableGeometry().center()
    geo.moveCenter(scr)
    win.move(geo.topLeft())
    win.show()

    app.exec()

if __name__ == "__main__":
    main()
