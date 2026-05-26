from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QListWidget, QHBoxLayout, QMessageBox, QWidget)
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtCore import Qt, QSize
from src.core.utils import ASSETS_DIR
from src.core.utils import get_lang_from_registry, load_locale
import os
import logging
try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')


# ---- GLOBAL STYLES ----
GAMING_STYLESHEET = """
    QDialog {
        background-color: #0d0e10;
        border: 2px solid #1b1f23;
        border-radius: 14px;
    }

    QLabel {
        font-size: 14px;
        font-family: "Segoe UI";
        color: #e0e0e0;
        padding-bottom: 4px;
    }
    
    QLabel#title_label {
        font-size: 18px;
        font-weight: bold;
        color: #ffffff;
        padding-bottom: 8px;
    }

    QLineEdit, QSpinBox {
        padding: 8px;
        font-size: 14px;
        border: 1px solid #2c2f33;
        border-radius: 6px;
        background: #1a1b1d;
        color: #ffffff;
        font-family: "Segoe UI";
        font-weight: bold;
    }

    QLineEdit:focus, QSpinBox:focus {
        border: 2px solid #454C55;
    }

    QPushButton {
        background-color: #045D0E;
        color: #FFFFFF;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-family: "Segoe UI";
        font-weight: bold;
    }

    QPushButton:hover {
        background-color: #12881F;
    }
    
    QPushButton:pressed {
        background-color: #03420a;
    }

    QPushButton#secondary {
        background-color: #2c2f33;
        color: #e6e6e6;
    }

    QPushButton#secondary:hover {
        background-color: #3c3f43;
    }

    /* LIST WIDGET & SCROLLBARS */
    QListWidget {
        background: #131416;
        border: 1px solid #1f2428;
        border-radius: 8px;
        padding: 6px;
        font-size: 13px;
        font-family: Consolas, monospace;
        color: #cfcfcf;
    }

    QListWidget::item {
        padding: 8px;
        border-radius: 4px;
        color: #dfdfdf;
    }

    QListWidget::item:selected {
        background-color: #00e676;
        color: #0e0f11;
        font-weight: bold;
    }

    QScrollBar:vertical {
        background: transparent;
        width: 8px;
        margin: 4px 0;
    }
    QScrollBar::handle:vertical {
        background: #383a3d;
        border-radius: 4px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #4a4d50;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0; 
        background: none; 
    }
"""

class GamingMessageBox(QDialog):
    def __init__(self, title, text, icon_type="info", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 20)
        layout.setSpacing(20)
        
        # Icon & Text Row (Optional: add an icon label if desired, skipping for simplicity to match style)
        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.lbl_text)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        
        if icon_type == "question":
            self.ok_btn.setText(TEXTS.get("yes", "Yes"))
            self.cancel_btn.setText(TEXTS.get("no", "No"))
            btn_layout.addWidget(self.ok_btn)
            btn_layout.addWidget(self.cancel_btn)
        else:
            # Info / Warning
            btn_layout.addStretch()
            btn_layout.addWidget(self.ok_btn)
            btn_layout.addStretch()
            
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # Auto size
        self.adjustSize()

    @staticmethod
    def show_info(parent, title, text):
        dlg = GamingMessageBox(title, text, "info", parent)
        dlg.exec_()
        
    @staticmethod
    def show_warning(parent, title, text):
        dlg = GamingMessageBox(title, text, "warning", parent)
        dlg.exec_()

    @staticmethod
    def show_question(parent, title, text):
        dlg = GamingMessageBox(title, text, "question", parent)
        return dlg.exec_() == QDialog.Accepted

class GamingInputDialog(QDialog):
    def __init__(self, title, label_text, value=0, min_val=0, max_val=100, step=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 20)
        layout.setSpacing(15)
        
        lbl = QLabel(label_text)
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        
        from PyQt5.QtWidgets import QSpinBox
        self.spin = QSpinBox()
        self.spin.setRange(min_val, max_val)
        self.spin.setValue(value)
        self.spin.setSingleStep(step)
        self.spin.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.spin)
        
        btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.setFixedSize(300, 180)

    @staticmethod
    def get_int(parent, title, label, value=0, min_val=0, max_val=100, step=1):
        dlg = GamingInputDialog(title, label, value, min_val, max_val, step, parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.spin.value(), True
        return value, False


from PyQt5.QtCore import pyqtSignal

class AskGameDialog(QDialog):
    quest_mode_requested = pyqtSignal()
    update_list_requested = pyqtSignal()

    def __init__(self, parent=None, title=TEXTS.get("force_game", "Force Game"),
                 message=TEXTS.get("game_name", "GAME NAME:")):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setFixedSize(460, 280) # Increased size for better layout
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        # ---- 🎮 DARK GAMING STYLE ----
        self.setStyleSheet(GAMING_STYLESHEET)

        # ---- LAYOUT ----
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 15)
        layout.setSpacing(15)

        # Centrado del label
        self.label = QLabel(message)
        self.label.setObjectName("title_label")
        self.label.setAlignment(Qt.AlignCenter)  
        layout.addWidget(self.label)

        self.entry = QLineEdit()
        self.entry.returnPressed.connect(self.accept)
        layout.addWidget(self.entry)

        sec_btns_layout = QVBoxLayout()
        sec_btns_layout.setSpacing(10)

        self.quest_mode_btn = QPushButton(TEXTS.get("quest_mode", "Discord Quest Mode (Multiple Games)"))
        self.quest_mode_btn.setObjectName("secondary")
        self.quest_mode_btn.setAutoDefault(False)
        self.quest_mode_btn.clicked.connect(self.on_quest_mode_clicked)
        self.quest_mode_btn.setStyleSheet("padding: 10px; font-size: 13px;") # Make button slightly taller
        sec_btns_layout.addWidget(self.quest_mode_btn)

        self.update_list_btn = QPushButton(TEXTS.get("update_list", "Update games database"))
        self.update_list_btn.setObjectName("secondary")
        self.update_list_btn.setAutoDefault(False)
        self.update_list_btn.clicked.connect(self.on_update_list_clicked)
        self.update_list_btn.setStyleSheet("padding: 8px; font-size: 13px;")
        sec_btns_layout.addWidget(self.update_list_btn)

        layout.addLayout(sec_btns_layout)

        # More compact buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.ok_btn = QPushButton(TEXTS.get("ok", "OK"))
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton(TEXTS.get("cancel", "Cancel"))
        self.cancel_btn.setObjectName("secondary")

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        # ---- 🎞️ ANIMATED BACKGROUND ----
        self.bg_label = QLabel(self)
        self.gif = QMovie(str(ASSETS_DIR / "gfn2.mp4"))
        self.bg_label.setMovie(self.gif)
        self.bg_label.setScaledContents(True)
        self.gif.start()
        
        self.bg_label.lower()

    def resizeEvent(self, event):
        if hasattr(self, 'bg_label'):
            self.bg_label.resize(self.size())
        super().resizeEvent(event)

    def get_game_name(self):
        return self.entry.text()

    def is_quest_mode(self):
        return False  # Deprecated logic from checkbox, handled directly via button now

    def on_quest_mode_clicked(self):
        self.quest_mode_requested.emit()

    def on_update_list_clicked(self):
        self.update_list_requested.emit()


class QuestListDialog(QDialog):
    def __init__(self, presence_manager, parent=None):
        super().__init__(parent)
        self.pm = presence_manager
        self.setWindowTitle("Discord Quest Mode - Active Games")
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        lbl = QLabel(TEXTS.get("active_games", "Active Games (15 minutes max.)"))
        lbl.setObjectName("title_label")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(GAMING_STYLESHEET + """
            QListWidget::item { 
                border-bottom: 1px solid #2c2f33; 
                margin-bottom: 4px;
            }
        """)
        layout.addWidget(self.list_widget)
        
        # Add new game button
        add_btn = QPushButton(TEXTS.get("force_new_game", "Force New Game"))
        add_btn.clicked.connect(self.on_add_game)
        layout.addWidget(add_btn)
        
        self.close_btn = QPushButton(TEXTS.get("close_window", "Close Window (Games will continue)"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        
        # Timer for UI updates
        from PyQt5.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_list)
        self.timer.start(1000) # Update every second
        
        self.refresh_list()
        
    def on_add_game(self):
        # Trigger the same logic as the tray icon
        # We can signal or call a callback provided in init, but for now let's assume parent/pm handling?
        # Ideally, we should invoke the main add game dialog.
        # But we are in a dialog.
        
        # Let's import AskGameDialog locally to avoid circulars if any, though we are in same file
        dlg = AskGameDialog(parent=self, message="Game name for Quest:")
        dlg.quest_mode_btn.hide() # Force quest mode if adding from here
        
        if dlg.exec_() == QDialog.Accepted:
            game_name = dlg.get_game_name()
            if game_name:
                # We need to trigger the process_force_game logic.
                # Since we have `pm`, we can perhaps call a new method on it or use the tray icon logic?
                # The tray icon logic handles the searching/downloading.
                # We should probably expose that logic or signal it.
                # For simplicity, let's signal the PM to request a new quest game login.
                # But PM is core. Tray is UI.
                # Let's emit a custom signal if possible, or direct call if we move logic to PM.
                # For now, let's assume PM has a method `start_quest_game_flow(game_name, parent_ui)`
                # Or we can reuse the callback passed from tray?
                # Actually, the proper way is probably to emit a signal from this dialog that the Tray listens to?
                # But Tray creates this dialog.
                # We can call `self.parent().process_force_game(game_name, quest_mode=True)` if parent is tray.
                pass
                # To be handled in the connection logic in TrayIcon.
                # Actually, let's allow the user to type it here, but the heavy lifting is done by the caller.
                # We will define a callback.
                if hasattr(self, 'add_game_callback'):
                    self.add_game_callback(game_name)

    def set_add_game_callback(self, callback):
        self.add_game_callback = callback
        
    def refresh_list(self):
        # Save scroll position
        # current_row = self.list_widget.currentRow()
        
        self.list_widget.clear()
        
        quests = getattr(self.pm, "active_quests", {})
        if not quests:
            self.list_widget.addItem("No active games in Quest mode.")
            return

        from PyQt5.QtWidgets import QWidget, QProgressBar, QHBoxLayout, QLabel, QPushButton
        
        sorted_quests = sorted(quests.items(), key=lambda x: x[1]['start_time'])
        
        for game_id, data in sorted_quests:
            item_widget = QWidget()
            layout = QVBoxLayout()
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)
            
            # Header
            header_layout = QHBoxLayout()
            name_lbl = QLabel(f"{data.get('name', 'Unknown')}")
            # Add padding and min-height to prevent clipping of descenders/ascenders
            name_lbl.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; padding: 2px 0px 4px 0px;")
            name_lbl.setWordWrap(True)
            # Ensure label tries to expand reasonably
            name_lbl.setMinimumHeight(24)
            header_layout.addWidget(name_lbl, 1) 
            
            # Close/Remove button
            btn_stop = QPushButton("❌")
            btn_stop.setFixedSize(28, 28)
            btn_stop.setCursor(Qt.PointingHandCursor)
            btn_stop.setStyleSheet("""
                QPushButton { background: #d32f2f; color: white; border: none; border-radius: 4px; font-size: 14px; }
                QPushButton:hover { background: #b71c1c; }
            """)
            btn_stop.clicked.connect(lambda checked, gid=game_id: self.stop_quest(gid))
            header_layout.addWidget(btn_stop)
            
            layout.addLayout(header_layout)
            
            # Spacer
            layout.addSpacing(4)

            # Progress status
            import time
            elapsed = time.time() - data['start_time']
            duration = (16 * 60) + 30 # 16 mins 30 secs
            remaining = max(0, duration - elapsed)
            
            progress = QProgressBar()
            progress.setRange(0, duration)
            progress.setValue(int(remaining))
            progress.setTextVisible(False)
            
            # Color based on state or time
            progress.setStyleSheet("""
                QProgressBar {
                    background-color: #2c2f33;
                    border: none;
                    border-radius: 4px;
                    height: 10px;
                }
                QProgressBar::chunk {
                    background-color: #5865F2; /* Discord Blurple brighter */
                    border-radius: 4px;
                }
            """)
            
            if data.get('finished', False):
                status_text = "Status: Stopped"
                progress.setValue(0)
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                status_text = f"⏱️ Time remaining: {mins:02d}:{secs:02d}"
                
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet("color: #dcddde; font-size: 13px; font-weight: 500; padding-top: 2px;")
            
            layout.addWidget(status_lbl)
            layout.addWidget(progress)
            
            item_widget.setLayout(layout)
            
            # Force layout calculation
            item_widget.adjustSize()
            
            # Add to list
            from PyQt5.QtWidgets import QListWidgetItem
            list_item = QListWidgetItem(self.list_widget)
            # Add a little extra height buffer to be safe
            sz = item_widget.sizeHint()
            sz.setHeight(sz.height() + 10) 
            list_item.setSizeHint(sz)
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)
            
    def stop_quest(self, game_id):
        self.pm.stop_quest_game(game_id)
        self.refresh_list()



class MatchSelectionDialog(QDialog):
    def __init__(self, game_key, candidates, parent=None):
        super().__init__(parent)

        title_text = TEXTS.get("match_title", "Matches for: {busqueda}").replace("{busqueda}", game_key)
        self.setWindowTitle(title_text)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setMinimumWidth(540)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.candidates = candidates
        self.selected_match = None

        # ---- 🎮 DARK GAMING STYLE ----
        self.setStyleSheet(GAMING_STYLESHEET)

        # ---- LAYOUT ----
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)

        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
        
        self.table_widget = QTableWidget(len(candidates), 3)
        self.table_widget.setHorizontalHeaderLabels([
            TEXTS.get("match_col_name", "Name"),
            TEXTS.get("match_col_score", "Match"),
            TEXTS.get("match_col_quests", "Discord Quests")
        ])
        
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setStretchLastSection(False)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table_widget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.table_widget.setStyleSheet(GAMING_STYLESHEET + """
            QTableWidget {
                background: #131416;
                border: 1px solid #1f2428;
                border-radius: 8px;
                color: #cfcfcf;
                gridline-color: #2c2f33;
            }
            QHeaderView::section {
                background-color: #1a1b1d;
                color: #ffffff;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #2c2f33;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #00e676;
                color: #0e0f11;
                font-weight: bold;
            }
        """)

        for row, c in enumerate(candidates):
            name_item = QTableWidgetItem(c['name'])
            score_item = QTableWidgetItem(f"{c['score'] * 100:.1f}%")
            score_item.setTextAlignment(Qt.AlignCenter)
            
            has_id = bool(c.get('id'))
            has_exe = bool(c.get('exe'))
            eligible = has_id and has_exe
            quests_str = "✅" if eligible else "❌"
            quests_item = QTableWidgetItem(quests_str)
            quests_item.setTextAlignment(Qt.AlignCenter)
            
            self.table_widget.setItem(row, 0, name_item)
            self.table_widget.setItem(row, 1, score_item)
            self.table_widget.setItem(row, 2, quests_item)

        layout.addWidget(self.table_widget)

        # ---- BOTONES ----
        btn_layout = QHBoxLayout()

        self.confirm_btn = QPushButton(TEXTS.get("confirm", "Confirm"))
        self.confirm_btn.clicked.connect(self.on_confirm)

        self.ignore_btn = QPushButton(TEXTS.get("ignore", "Ignore"))
        self.ignore_btn.setObjectName("secondary")
        self.ignore_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.confirm_btn)
        btn_layout.addWidget(self.ignore_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def on_confirm(self):
        row = self.table_widget.currentRow()
        if row >= 0:
            self.selected_match = self.candidates[row]
            self.accept()
        else:
            QMessageBox.warning(
                self,
                TEXTS.get("selection_required", "Selection required"),
                TEXTS.get("selection_required_msg", "Please select an option from the list.")
            )


class CustomPresenceDialog(QDialog):
    def __init__(self, game_name, current_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Custom Presence: {game_name}")
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        self.game_name = game_name
        self.result_data = None
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Helper to create rows
        def add_row(label_txt, widget):
            r = QVBoxLayout()
            r.setSpacing(5)
            l = QLabel(label_txt)
            r.addWidget(l)
            r.addWidget(widget)
            layout.addLayout(r)
            return widget

        self.details_edit = add_row("Details (Line 1):", QLineEdit())
        self.details_edit.setPlaceholderText("e.g. Playing Competitive")
        self.details_edit.setText(current_data.get("custom_details", ""))

        self.state_edit = add_row("State (Line 2):", QLineEdit())
        self.state_edit.setPlaceholderText("e.g. In a party of 5")
        self.state_edit.setText(current_data.get("custom_state", ""))

        # Party Size Row
        party_layout = QHBoxLayout()
        
        from PyQt5.QtWidgets import QSpinBox
        self.party_current = QSpinBox()
        self.party_current.setRange(0, 100)
        self.party_current.setValue(current_data.get("custom_party_size_current", 0))
        
        self.party_max = QSpinBox()
        self.party_max.setRange(0, 100)
        self.party_max.setValue(current_data.get("custom_party_size_max", 0))
        
        p_sub = QVBoxLayout()
        p_sub.addWidget(QLabel("Party Size (Current):"))
        p_sub.addWidget(self.party_current)
        party_layout.addLayout(p_sub)
        
        p_sub2 = QVBoxLayout()
        p_sub2.addWidget(QLabel("Party Size (Max):"))
        p_sub2.addWidget(self.party_max)
        party_layout.addLayout(p_sub2)
        
        layout.addLayout(party_layout)
        
        layout.addWidget(QLabel("Note: If 'Max' is 0, no party information will be displayed."))

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.on_save)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondary")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        self.adjustSize()

    def on_save(self):
        self.result_data = {
            "custom_details": self.details_edit.text(),
            "custom_state": self.state_edit.text(),
            "custom_party_size_current": self.party_current.value(),
            "custom_party_size_max": self.party_max.value()
        }
        self.accept()

class ClickableIconLabel(QLabel):
    def __init__(self, icon_path, url, parent=None):
        super().__init__(parent)
        self.url = url
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(str(ASSETS_DIR / icon_path))
        if not pixmap.isNull():
            # Apply some smoothing if it's scaled down
            self.setPixmap(pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(url)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            import webbrowser
            webbrowser.open(self.url)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TEXTS.get("about", "About"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setFixedSize(400, 250)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("GeForce NOW Rich Presence")
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Description
        desc = QLabel(TEXTS.get("about_desc", "This program was made by KarmaDevz, consider support the program"))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 14px; color: #cfcfcf;")
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Icons Layout
        icons_layout = QHBoxLayout()
        icons_layout.setSpacing(30)
        icons_layout.setAlignment(Qt.AlignCenter)
        
        github_icon = ClickableIconLabel("github.png", "https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence", self)
        discord_icon = ClickableIconLabel("discord.png", "https://discord.com/users/karmadevz", self)
        paypal_icon = ClickableIconLabel("paypal.png", "https://www.paypal.com/paypalme/KarmaDevz", self)
        
        icons_layout.addWidget(github_icon)
        icons_layout.addWidget(discord_icon)
        icons_layout.addWidget(paypal_icon)
        
        layout.addLayout(icons_layout)
        # Close Button
        self.close_btn = QPushButton(TEXTS.get("close", "Close"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        
        # Add a stretch before the close button to push it to the bottom
        layout.addStretch()
        
        # We can center the close button by placing it in its own layout
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(self.close_btn)
        close_layout.addStretch()
        
        layout.addLayout(close_layout)
        
        self.setLayout(layout)

    def open_url(self, url):
        import webbrowser
        webbrowser.open(url)

class GFNRepairDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TEXTS.get("repair_title", "Repairing GeForce NOW"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedSize(450, 180)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # Title
        title_lbl = QLabel(TEXTS.get("repair_title", "Repairing GeForce NOW"))
        title_lbl.setObjectName("title_label")
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Status text
        self.status_lbl = QLabel(TEXTS.get("repair_status_init", "Starting repair..."))
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #cfcfcf;")
        layout.addWidget(self.status_lbl)
        
        # Progress Bar
        from PyQt5.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setAlignment(Qt.AlignCenter)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #1a1b1d;
                border: 1px solid #2c2f33;
                border-radius: 6px;
                color: #ffffff;
                font-weight: bold;
                text-align: center;
                height: 22px;
            }
            QProgressBar::chunk {
                background-color: #045D0E;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)
        
        # Button layout (Hidden until error or done)
        self.btn_layout = QHBoxLayout()
        self.ok_btn = QPushButton(TEXTS.get("close", "Close"))
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setVisible(False)
        self.btn_layout.addStretch()
        self.btn_layout.addWidget(self.ok_btn)
        self.btn_layout.addStretch()
        
        layout.addLayout(self.btn_layout)
        self.setLayout(layout)

    def on_progress(self, percent):
        self.progress.setValue(percent)

    def on_status(self, lang_key):
        self.status_lbl.setText(TEXTS.get(lang_key, lang_key))

    def on_error(self, err_msg):
        self.progress.setStyleSheet("""
            QProgressBar { background-color: #1a1b1d; border: 1px solid #d32f2f; border-radius: 6px; color: #ffffff; text-align: center; height: 22px; }
            QProgressBar::chunk { background-color: #d32f2f; border-radius: 4px; }
        """)
        msg = TEXTS.get("repair_status_error", "Error: {error}").replace("{error}", err_msg)
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet("color: #ff5252; font-weight: bold;")
        self.ok_btn.setVisible(True)

    def on_finished(self):
        self.status_lbl.setText(TEXTS.get("repair_status_done", "Repair completed."))
        self.status_lbl.setStyleSheet("color: #00e676; font-weight: bold;")
        self.progress.setValue(100)
        self.ok_btn.setVisible(True)

