import os
import time
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QPushButton, QListWidget, 
                             QHBoxLayout, QWidget, QProgressBar, QListWidgetItem, QApplication)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon

from ..constants import ASSETS_DIR
from src.ui.dialogs import GAMING_STYLESHEET
from src.core.utils import get_lang_from_registry, load_locale
from .force_game_dialog import AskGameDialog

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

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
        
        lbl = QLabel(TEXTS.get("active_games", "Juegos activos (15 minutos máx.)"))
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
        add_btn = QPushButton(TEXTS.get("force_new_game", "Forzar Nuevo Juego"))
        add_btn.clicked.connect(self.on_add_game)
        layout.addWidget(add_btn)
        
        self.close_btn = QPushButton(TEXTS.get("close_window", "Cerrar Ventana (Juegos continuarán)"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
        
        # Timer for UI updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_list)
        self.timer.start(1000) # Update every second
        
        self.refresh_list()
        
    def on_add_game(self):
        dlg = AskGameDialog(parent=self, message="Nombre del juego para Quest:")
        dlg.quest_mode_btn.hide() # Force quest mode if adding from here
        
        def on_update_list():
            dlg.set_updating(True)
            QApplication.processEvents()

            def on_progress(cur, tot):
                dlg.update_download_progress(cur, tot)
                QApplication.processEvents()

            self.pm.download_progress.connect(on_progress)
            try:
                apps = self.pm._fetch_discord_apps_cached(force_download=True)
            finally:
                try:
                    self.pm.download_progress.disconnect(on_progress)
                except Exception:
                    pass

            if apps:
                dlg.set_update_result(True, len(apps))
            else:
                dlg.set_update_result(False)

        dlg.update_list_requested.connect(on_update_list)
        
        if dlg.exec_() == QDialog.Accepted:
            game_name = dlg.get_game_name()
            if game_name:
                if hasattr(self, 'add_game_callback'):
                    self.add_game_callback(game_name)

    def set_add_game_callback(self, callback):
        self.add_game_callback = callback
        
    def refresh_list(self):
        self.list_widget.clear()
        
        quests = getattr(self.pm, "active_quests", {})
        if not quests:
            self.list_widget.addItem("No hay juegos activos en modo Quest.")
            return
        
        sorted_quests = sorted(quests.items(), key=lambda x: x[1]['start_time'])
        
        for game_id, data in sorted_quests:
            item_widget = QWidget()
            layout = QVBoxLayout()
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)
            
            # Header
            header_layout = QHBoxLayout()
            name_lbl = QLabel(f"{data.get('name', 'Unknown')}")
            name_lbl.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: bold; padding: 2px 0px 4px 0px;")
            name_lbl.setWordWrap(True)
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
            layout.addSpacing(4)

            # Progress status
            elapsed = time.time() - data['start_time']
            duration = (16 * 60) + 30 # 16 mins 30 secs
            remaining = max(0, duration - elapsed)
            
            progress = QProgressBar()
            progress.setRange(0, duration)
            progress.setValue(int(remaining))
            progress.setTextVisible(False)
            
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
                status_text = "Estado: Detenido"
                progress.setValue(0)
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                status_text = f"⏱️ Tiempo restante: {mins:02d}:{secs:02d}"
                
            status_lbl = QLabel(status_text)
            status_lbl.setStyleSheet("color: #dcddde; font-size: 13px; font-weight: 500; padding-top: 2px;")
            
            layout.addWidget(status_lbl)
            layout.addWidget(progress)
            
            item_widget.setLayout(layout)
            item_widget.adjustSize()
            
            list_item = QListWidgetItem(self.list_widget)
            sz = item_widget.sizeHint()
            sz.setHeight(sz.height() + 10) 
            list_item.setSizeHint(sz)
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, item_widget)
            
    def stop_quest(self, game_id):
        self.pm.stop_quest_game(game_id)
        self.refresh_list()
