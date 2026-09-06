import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QIcon

from ..constants import ASSETS_DIR
from src.ui.dialogs import GAMING_STYLESHEET, GamingMessageBox
from src.core.utils import get_lang_from_registry, load_locale

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

class AskGameDialog(QDialog):
    quest_mode_requested = pyqtSignal()
    update_list_requested = pyqtSignal()

    def __init__(self, parent=None, title=TEXTS.get("force_game", "Force Game"),
                 message=TEXTS.get("game_name", "GAME NAME:")):
        super().__init__(parent)
        self.texts = TEXTS

        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setFixedSize(460, 280)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)

        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 15)
        layout.setSpacing(15)

        self.label = QLabel(message)
        self.label.setObjectName("title_label")
        self.label.setAlignment(Qt.AlignCenter)  
        layout.addWidget(self.label)

        self.entry = QLineEdit()
        self.entry.returnPressed.connect(self.accept)
        layout.addWidget(self.entry)

        sec_btns_layout = QVBoxLayout()
        sec_btns_layout.setSpacing(10)

        self.quest_mode_btn = QPushButton(self.texts.get("quest_mode", "Misiones de Discord (Múltiples Juegos)"))
        self.quest_mode_btn.setObjectName("secondary")
        self.quest_mode_btn.setAutoDefault(False)
        self.quest_mode_btn.clicked.connect(self.on_quest_mode_clicked)
        self.quest_mode_btn.setStyleSheet("padding: 10px; font-size: 13px;")
        sec_btns_layout.addWidget(self.quest_mode_btn)

        self.orig_update_text = self.texts.get("update_list", "Actualizar base de datos de juegos")
        self.update_list_btn = QPushButton(self.orig_update_text)
        self.update_list_btn.setObjectName("secondary")
        self.update_list_btn.setAutoDefault(False)
        self.update_list_btn.clicked.connect(self.on_update_list_clicked)
        self.update_list_btn.setStyleSheet("padding: 8px; font-size: 13px;")
        sec_btns_layout.addWidget(self.update_list_btn)

        layout.addLayout(sec_btns_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.ok_btn = QPushButton(self.texts.get("ok", "OK"))
        self.ok_btn.setDefault(True)
        self.cancel_btn = QPushButton(self.texts.get("cancel", "Cancel"))
        self.cancel_btn.setObjectName("secondary")

        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_game_name(self):
        return self.entry.text()

    def is_quest_mode(self):
        return False

    def on_quest_mode_clicked(self):
        self.quest_mode_requested.emit()

    def on_update_list_clicked(self):
        self.update_list_requested.emit()

    def set_updating(self, is_updating: bool):
        if is_updating:
            self.update_list_btn.setEnabled(False)
            downloading_str = self.texts.get("downloading", "Descargando...")
            self.update_list_btn.setText(f" {downloading_str}")
        else:
            self.update_list_btn.setEnabled(True)
            self.update_list_btn.setText(self.orig_update_text)

    def update_download_progress(self, current: int, total: int):
        downloading_str = self.texts.get("downloading", "Descargando...")
        if total > 0 and current > 0:
            def fmt(sz):
                if sz < 1024 * 1024:
                    return f"{sz / 1024:.1f} KB"
                return f"{sz / 1024 / 1024:.1f} MB"
            self.update_list_btn.setText(f" {downloading_str} ({fmt(current)} / {fmt(total)})")
        else:
            self.update_list_btn.setText(f" {downloading_str}")

    def set_update_result(self, success: bool, count: int = 0):
        self.update_list_btn.setEnabled(True)
        if success:
            success_text = self.texts.get("updated_success", "¡Base de datos actualizada!")
            msg = f"✅ {success_text} ({count} apps)" if count else f"✅ {success_text}"
            self.update_list_btn.setText(msg)
        else:
            err_text = self.texts.get("update_error", "Error al actualizar")
            self.update_list_btn.setText(f"❌ {err_text}")

        QTimer.singleShot(4000, lambda: self.update_list_btn.setText(self.orig_update_text))


class MatchSelectionDialog(QDialog):
    def __init__(self, game_key, candidates, parent=None):
        super().__init__(parent)

        title_text = TEXTS.get("match_title", "Coincidencias para: {busqueda}").replace("{busqueda}", game_key)
        self.setWindowTitle(title_text)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setMinimumWidth(540)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.candidates = candidates
        self.selected_match = None
        self.setStyleSheet(GAMING_STYLESHEET)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(15)

        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
        
        self.table_widget = QTableWidget(len(candidates), 3)
        self.table_widget.setHorizontalHeaderLabels([
            TEXTS.get("match_col_name", "Nombre"),
            TEXTS.get("match_col_score", "Coincidencia"),
            TEXTS.get("match_col_quests", "Misiones de discord")
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

        btn_layout = QHBoxLayout()

        self.confirm_btn = QPushButton(TEXTS.get("confirm", "Confirmar"))
        self.confirm_btn.clicked.connect(self.on_confirm)

        self.ignore_btn = QPushButton(TEXTS.get("ignore", "Ignorar"))
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
            GamingMessageBox.show_warning(
                self,
                TEXTS.get("selection_required", "Selección requerida"),
                TEXTS.get("selection_required_msg", "Por favor selecciona una opción de la lista.")
            )
