# /core/interface/tabs/logs_tab.py
"""
Onglet Logs - Affichage des logs avec lecture de fichier
"""

from __future__ import annotations
import os
from PySide6 import QtCore, QtGui, QtWidgets
from core.bus import EventBus

from core.pol import create_pol
pol = create_pol(source_id=22)


class LogsTab(QtWidgets.QWidget):
    """Onglet pour l'affichage des logs"""
    
    def __init__(self, event_bus: EventBus, config_manager=None):
        super().__init__()
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # ✅ Chemin simple : logs.txt à la racine du projet
        # Si on lance depuis la racine du projet, logs.txt sera trouvé
        self.logs_file_path = "./logs/orion.log"
        
        # ✅ NOUVEAU : Variables de filtrage
        self.current_module_filter = 0   # 0 = ALL
        self.current_level_filter = 0    # 0 = ALL
        self.all_logs = []               # Cache de tous les logs
        
        # ✅ NOUVEAU : Gestion auto-scroll hybride v2
        self.auto_scroll_enabled = True  # État auto-scroll
        self.refresh_enabled = True      # État refresh (peut être suspendu)
        self.user_is_reading = False     # L'utilisateur lit l'historique
        self.scroll_threshold = 50       # Pixels depuis le bas pour considérer qu'on lit l'historique
        
        # ✅ NOUVEAU : Timer pour réactivation automatique après 5s en bas
        self.time_at_bottom = 0          # Timestamp quand on arrive en bas
        self.auto_reactivate_delay = 5   # Secondes avant réactivation auto
        self.mouse_over_logs = False     # Souris sur la zone de logs
        self.timer_blocked_by_mouse = False  # Timer bloqué par présence souris
        
        self._setup_ui()
        self._setup_timer()
    
    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header avec info
        header = QtWidgets.QLabel("📋 LOGS SYSTÈME (500 dernières lignes)")
        header.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                background: rgba(255, 159, 28, 0.1);
                border: 1px solid #ff9f1c;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                font-weight: bold;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(header)
        
        # ✅ NOUVEAU : Container pour les filtres et contrôles
        filters_container = QtWidgets.QWidget()
        filters_layout = QtWidgets.QHBoxLayout(filters_container)
        filters_layout.setContentsMargins(0, 0, 0, 10)
        
        # ✅ Filtre Module
        module_label = QtWidgets.QLabel("📁 Module:")
        module_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.module_combo = QtWidgets.QComboBox()
        self.module_combo.addItem("ALL", 0)  # Valeur 0 pour ALL
        self.module_combo.addItem("Main", 1)  # Valeur 1 pour Main
        self.module_combo.addItem("Interface", 2)  # Valeur 2 pour Interface
        self.module_combo.addItem("Interface Log", 22)  # Valeur 22 pour INT_LOG
        self.module_combo.addItem("Grammar", 3)  # Valeur 3 pour Grammar
        self.module_combo.addItem("Vocalizer", 4)  # Valeur 4 pour Vocalizer
        for i in range(5, 11):
            self.module_combo.addItem(f"Inconnu{i}", i)
        self.module_combo.setStyleSheet("""
            QComboBox {
                background: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAFCAYAAAB8ZH1oAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAABGSURBVAiZY/z//z8DAwMDJgDxP1wAq0JcCrAqxKkQXQGuQnQFuAqxKsRVgKsQq0JcBbgKsSrEVYCrEKtCXAW4CrEqxFUAAG1kDTJ9K7baAAAAAElFTkSuQmCC);
            }
        """)
        self.module_combo.currentIndexChanged.connect(self._on_module_filter_changed)
        
        # ✅ Filtre Niveau
        level_label = QtWidgets.QLabel("📊 Niveau:")
        level_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.level_combo = QtWidgets.QComboBox()
        self.level_combo.addItem("ALL", 0)       # 0 = Tous
        self.level_combo.addItem("LEGER", 1)     # 1 = LEGER
        self.level_combo.addItem("WARNING", 2)   # 2 = WARNING
        self.level_combo.addItem("ERROR", 3)     # 3 = ERROR
        self.level_combo.addItem("PARANO", 4)    # 4 = PARANO
        self.level_combo.addItem("HABILLAGE", 5) # 5 = HABILLAGE
        self.level_combo.setStyleSheet("""
            QComboBox {
                background: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.level_combo.currentIndexChanged.connect(self._on_level_filter_changed)
        
        # ✅ NOUVEAU : Indicateur Auto-Scroll (principalement visuel)
        self.auto_scroll_indicator = QtWidgets.QPushButton("� Auto-Scroll")
        self.auto_scroll_indicator.setCheckable(True)
        self.auto_scroll_indicator.setChecked(True)
        self.auto_scroll_indicator.setStyleSheet("""
            QPushButton {
                background: #4caf50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #45a049;
            }
            QPushButton:checked {
                background: #4caf50;
            }
            QPushButton:!checked {
                background: #f44336;
            }
        """)
        self.auto_scroll_indicator.clicked.connect(self._toggle_auto_scroll)
        
        # ✅ NOUVEAU : Bouton Copier vers presse-papier
        copy_btn = QtWidgets.QPushButton("📋 Copier")
        copy_btn.setStyleSheet("""
            QPushButton {
                background: #2196f3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background: #1976d2;
            }
        """)
        copy_btn.clicked.connect(self._copy_logs_to_clipboard)
        
        # ✅ Assemblage filtres et contrôles
        filters_layout.addWidget(module_label)
        filters_layout.addWidget(self.module_combo)
        filters_layout.addSpacing(20)
        filters_layout.addWidget(level_label)
        filters_layout.addWidget(self.level_combo)
        filters_layout.addSpacing(20)
        filters_layout.addWidget(self.auto_scroll_indicator)
        filters_layout.addSpacing(10)
        filters_layout.addWidget(copy_btn)
        filters_layout.addStretch()  # Pousser vers la gauche
        
        layout.addWidget(filters_container)
        
        # Zone de texte scrollable pour les logs
        self.logs_display = QtWidgets.QTextEdit()
        self.logs_display.setReadOnly(True)
        self.logs_display.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 8px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        
        # ✅ NOUVEAU : Connecter les événements de scroll pour détecter l'interaction utilisateur
        scrollbar = self.logs_display.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)
        
        # ✅ NOUVEAU : Activer le tracking de souris pour détecter enter/leave
        self.logs_display.setMouseTracking(True)
        self.logs_display.enterEvent = self._on_mouse_enter_logs
        self.logs_display.leaveEvent = self._on_mouse_leave_logs
        
        layout.addWidget(self.logs_display)
        
        # Bouton de rechargement manuel
        refresh_btn = QtWidgets.QPushButton("🔄 Recharger")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #ff9f1c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e8890f;
            }
        """)
        refresh_btn.clicked.connect(self._load_logs)
        layout.addWidget(refresh_btn)
    
    def _setup_timer(self):
        """Configure le timer pour recharger les logs toutes les 500ms"""
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._on_timer_tick)
        self.timer.start(500)  # 500ms
        
        # Charger une première fois
        self._load_logs()
    
    # ✅ NOUVEAU : Méthodes de gestion de l'auto-scroll hybride v2
    def _on_timer_tick(self):
        """Tick du timer - gère refresh et réactivation automatique"""
        import time
        
        # 1. Vérifier si on peut faire un refresh
        if self.refresh_enabled:
            self._load_logs()
        
        # 2. Vérifier réactivation automatique après 5s en bas
        if not self.auto_scroll_enabled and not self.user_is_reading:
            # On est en bas mais auto-scroll désactivé
            current_time = time.time()
            
            # ✅ NOUVEAU : Vérifier si le timer n'est pas bloqué par la souris
            if self.mouse_over_logs and not self.timer_blocked_by_mouse:
                # Première fois qu'on détecte la souris → bloquer le timer
                self.timer_blocked_by_mouse = True
                pol.write(4, "Timer 5s bloqué par présence souris", "log")
            elif not self.mouse_over_logs and self.timer_blocked_by_mouse:
                # La souris a quitté → débloquer et redémarrer timer
                self.timer_blocked_by_mouse = False
                self.time_at_bottom = current_time  # Redémarrer timer
                pol.write(4, "Timer 5s redémarré (souris sortie)", "log")
            
            # Vérifier expiration du timer (seulement si pas bloqué par souris)
            if (not self.timer_blocked_by_mouse and 
                self.time_at_bottom > 0 and 
                (current_time - self.time_at_bottom) >= self.auto_reactivate_delay):
                # 5 secondes en bas sans souris → réactivation automatique
                pol.write(1, "Réactivation auto après 5s en bas (sans souris)", "log")
                self._reactivate_auto_scroll()
    
    def _reactivate_auto_scroll(self):
        """Réactive complètement l'auto-scroll et le refresh"""
        self.auto_scroll_enabled = True
        self.refresh_enabled = True
        self.user_is_reading = False
        self.time_at_bottom = 0
        self.timer_blocked_by_mouse = False  # Reset aussi l'état souris
        
        # Mise à jour visuelle du bouton
        self.auto_scroll_indicator.setText("� Auto-Scroll")
        self.auto_scroll_indicator.setChecked(True)
        self.auto_scroll_indicator.setStyleSheet("""
            QPushButton {
                background: #4caf50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background: #45a049;
            }
        """)
        
        # Forcer un refresh et scroll vers le bas
        self._load_logs()
        scrollbar = self.logs_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _toggle_auto_scroll(self):
        """Toggle manuel de l'auto-scroll (principalement pour override)"""
        if self.auto_scroll_indicator.isChecked():
            # Réactivation manuelle
            pol.write(1, "Auto-scroll réactivé manuellement", "log")
            self._reactivate_auto_scroll()
        else:
            # Désactivation manuelle
            self.auto_scroll_enabled = False
            self.refresh_enabled = False
            self.user_is_reading = True  # Forcer mode lecture
            self.time_at_bottom = 0
            
            self.auto_scroll_indicator.setText("� Lecture")
            self.auto_scroll_indicator.setStyleSheet("""
                QPushButton {
                    background: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                    min-width: 100px;
                }
                QPushButton:hover {
                    background: #d32f2f;
                }
            """)
            pol.write(1, "Auto-scroll et refresh désactivés manuellement", "log")
    
    def _on_scroll_changed(self, value):
        """Détecte quand l'utilisateur scrolle manuellement - Logique v2"""
        import time
        scrollbar = self.logs_display.verticalScrollBar()
        max_value = scrollbar.maximum()
        
        # Distance depuis le bas
        distance_from_bottom = max_value - value
        
        if distance_from_bottom > self.scroll_threshold:
            # 🔴 SCROLL VERS LE HAUT → L'utilisateur veut parcourir l'historique
            if not self.user_is_reading:
                self.user_is_reading = True
                self.auto_scroll_enabled = False  # STOP auto-scroll
                self.refresh_enabled = False      # STOP refresh
                self.time_at_bottom = 0           # Reset timer
                
                # Mise à jour visuelle
                self.auto_scroll_indicator.setText("� Lecture")
                self.auto_scroll_indicator.setChecked(False)
                self.auto_scroll_indicator.setStyleSheet("""
                    QPushButton {
                        background: #f44336;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                        font-weight: bold;
                        min-width: 100px;
                    }
                    QPushButton:hover {
                        background: #d32f2f;
                    }
                """)
                
                pol.write(1, f"Scroll vers le haut détecté → STOP auto-scroll et refresh (pos: {value}/{max_value})", "log")
        
        else:
            # 🟡 RETOUR VERS LE BAS → Ne rien faire, juste noter qu'on est en bas
            if self.user_is_reading:
                self.user_is_reading = False
                self.time_at_bottom = time.time()  # Commencer le timer de 5s
                pol.write(4, f"Retour en bas, timer 5s démarré (pos: {value}/{max_value})", "log")
            elif not self.user_is_reading and self.time_at_bottom == 0:
                # Première fois qu'on détecte qu'on est en bas
                self.time_at_bottom = time.time()
    
    def _should_auto_scroll(self):
        """Détermine si l'auto-scroll doit s'appliquer selon la logique v2"""
        return self.auto_scroll_enabled  # Simple : juste vérifier l'état
    
    # ✅ NOUVEAU : Gestion des événements souris pour le timer intelligent
    def _on_mouse_enter_logs(self, event):
        """Callback quand la souris entre dans la zone de logs"""
        self.mouse_over_logs = True
        if not self.auto_scroll_enabled and not self.user_is_reading:
            pol.write(4, "Souris sur logs → timer bloqué", "log")
    
    def _on_mouse_leave_logs(self, event):
        """Callback quand la souris quitte la zone de logs"""
        import time
        self.mouse_over_logs = False
        
        # Si on était en mode lecture et en bas, redémarrer le timer
        if not self.auto_scroll_enabled and not self.user_is_reading:
            self.time_at_bottom = time.time()  # Redémarrer timer
            self.timer_blocked_by_mouse = False
            pol.write(4, "Souris sortie → timer 5s redémarré", "log")
    
    def _copy_logs_to_clipboard(self):
        """Copie les logs actuellement affichés vers le presse-papier"""
        try:
            # Récupérer le texte brut des logs filtrés
            if not self.all_logs:
                pol.write(2, "Aucun log à copier", "log")
                return
            
            # Filtrer selon les critères actuels
            filtered_logs = []
            for log_entry in self.all_logs:
                # Filtre module (0 = ALL)
                if self.current_module_filter != 0 and log_entry['module'] != self.current_module_filter:
                    continue
                # Filtre niveau (0 = ALL)
                if self.current_level_filter != 0 and log_entry['level'] != self.current_level_filter:
                    continue
                filtered_logs.append(log_entry)
            
            if not filtered_logs:
                pol.write(2, "Aucun log correspondant aux filtres", "log")
                return
            
            # Construire le texte à copier
            clipboard_text = "\n".join([log['raw'] for log in filtered_logs])
            
            # Copier vers le presse-papier
            clipboard = QtWidgets.QApplication.clipboard()
            clipboard.setText(clipboard_text)
            
            # Feedback utilisateur
            count = len(filtered_logs)
            pol.write(1, f"{count} logs copiés vers le presse-papier", "log")
            print(f"📋 {count} logs copiés vers le presse-papier")
            
            # Effet visuel temporaire sur le bouton
            copy_btn = self.sender()
            original_text = copy_btn.text()
            copy_btn.setText("✅ Copié!")
            copy_btn.setStyleSheet("""
                QPushButton {
                    background: #4caf50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-weight: bold;
                    min-width: 80px;
                }
            """)
            
            # Restaurer après 2 secondes
            QtCore.QTimer.singleShot(2000, lambda: [
                copy_btn.setText(original_text),
                copy_btn.setStyleSheet("""
                    QPushButton {
                        background: #2196f3;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 10px;
                        font-weight: bold;
                        min-width: 80px;
                    }
                    QPushButton:hover {
                        background: #1976d2;
                    }
                """)
            ])
            
        except Exception as e:
            pol.write(3, f"Erreur copie presse-papier: {e}", "log")
            print(f"❌ Erreur copie: {e}")
    
    # ✅ NOUVEAU : Méthodes de gestion des filtres
    def _on_module_filter_changed(self, index):
        """Callback quand le filtre module change"""
        self.current_module_filter = self.module_combo.currentData()
        pol.write(4, f"Filtre module changé: {self.current_module_filter}", "log")
        print(f"🔍 Filtre module changé: {self.current_module_filter}")
        self._apply_filters()
        # Afficher le résultat du filtrage
        filtered_count = len([log for log in self.all_logs 
                            if (self.current_module_filter == 0 or log['module'] == self.current_module_filter)
                            and (self.current_level_filter == 0 or log['level'] == self.current_level_filter)])
        pol.write(4, f"Résultat: {filtered_count}/{len(self.all_logs)} logs affichés", "log")
        print(f"📊 Résultat: {filtered_count}/{len(self.all_logs)} logs affichés")
    
    def _on_level_filter_changed(self, index):
        """Callback quand le filtre niveau change"""
        self.current_level_filter = self.level_combo.currentData()
        print(f"🔍 Filtre niveau changé: {self.current_level_filter}")
        self._apply_filters()
        # Afficher le résultat du filtrage
        filtered_count = len([log for log in self.all_logs 
                            if (self.current_module_filter == 0 or log['module'] == self.current_module_filter)
                            and (self.current_level_filter == 0 or log['level'] == self.current_level_filter)])

        pol.write(4, f"Résultat: {filtered_count}/{len(self.all_logs)} logs affichés", "log")
        print(f"📊 Résultat: {filtered_count}/{len(self.all_logs)} logs affichés")
    
    def _parse_log_line(self, line):
        """
        Parse une ligne de log au format POL [niveau][source][timestamp]message
        
        Returns:
            dict avec 'level', 'module', 'timestamp', 'message', 'raw'
            ou None si parsing échoue
        """
        line = line.strip()
        if not line:
            return None
            
        try:
            # Format attendu: [niveau][source][timestamp]message
            if line.startswith('[') and ']' in line:
                # Extraire niveau
                end_level = line.find(']')
                if end_level == -1:
                    return None
                level_str = line[1:end_level]
                
                # Extraire source/module
                remaining = line[end_level + 1:]
                if remaining.startswith('[') and ']' in remaining:
                    end_module = remaining.find(']')
                    if end_module == -1:
                        return None
                    module_str = remaining[1:end_module]
                    
                    # Le reste après [timestamp] est le message
                    remaining2 = remaining[end_module + 1:]
                    if remaining2.startswith('[') and ']' in remaining2:
                        end_timestamp = remaining2.find(']')
                        if end_timestamp == -1:
                            return None
                        timestamp_str = remaining2[1:end_timestamp]
                        message = remaining2[end_timestamp + 1:]
                        
                        return {
                            'level': int(level_str) if level_str.isdigit() else 0,
                            'module': int(module_str) if module_str.isdigit() else 0,
                            'timestamp': timestamp_str,
                            'message': message,
                            'raw': line
                        }
            
            # Si parsing échoue, retourner comme message simple
            return {
                'level': 0,
                'module': 0,
                'timestamp': '',
                'message': line,
                'raw': line
            }
            
        except Exception as e:
            print(f"❌ Erreur parsing log: {e}")
            return None
    
    def _apply_filters(self):
        """Applique les filtres actuels sur tous les logs chargés"""
        if not self.all_logs:
            return
            
        filtered_logs = []
        
        for log_entry in self.all_logs:
            # Filtre module (0 = ALL)
            if self.current_module_filter != 0 and log_entry['module'] != self.current_module_filter:
                continue
                
            # Filtre niveau (0 = ALL)
            if self.current_level_filter != 0 and log_entry['level'] != self.current_level_filter:
                continue
                
            filtered_logs.append(log_entry)
        
        # Afficher les logs filtrés
        self._display_logs(filtered_logs)
    
    def _display_logs(self, log_entries):
        """Affiche une liste de logs dans l'interface avec auto-scroll intelligent"""
        content = ""
        
        for log_entry in log_entries:
            line = log_entry['raw']
            level = log_entry['level']
            
            # Coloration selon le niveau POL
            if level == 3:  # ERROR
                content += f'<span style="color: #ff6b6b;">{line}</span><br>'
            elif level == 2:  # WARNING
                content += f'<span style="color: #ffa726;">{line}</span><br>'
            elif level == 1:  # LEGER
                content += f'<span style="color: #66bb6a;">{line}</span><br>'
            elif level == 4:  # PARANO
                content += f'<span style="color: #90a4ae;">{line}</span><br>'
            elif level == 5:  # HABILLAGE
                content += f'<span style="color: #e1bee7;">{line}</span><br>'
            else:
                content += f'<span style="color: #ffffff;">{line}</span><br>'
        
        self.logs_display.setHtml(content)
        
        # ✅ NOUVEAU : Auto-scroll intelligent hybride
        if self._should_auto_scroll():
            scrollbar = self.logs_display.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
    
    def _load_logs(self):
        """Charge les 500 dernières lignes du fichier de logs et les parse"""
        try:
            if not os.path.exists(self.logs_file_path):
                self.logs_display.setText("📄 Fichier orion.log introuvable...")
                return
            
            with open(self.logs_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Prendre les 500 dernières lignes maximum
            if len(lines) > 500:
                lines = lines[-500:]
            
            # ✅ NOUVEAU : Parser chaque ligne et stocker
            self.all_logs = []
            for line in lines:
                parsed = self._parse_log_line(line)
                if parsed:
                    self.all_logs.append(parsed)
            
            # Appliquer les filtres actuels
            self._apply_filters()
            
        except Exception as e:
            self.logs_display.setText(f"❌ Erreur lecture logs: {e}")