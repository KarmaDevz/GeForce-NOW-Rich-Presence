from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QListWidget, QHBoxLayout, QWidget, QPlainTextEdit, QFileDialog)
from PyQt5.QtGui import QIcon, QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor
from PyQt5.QtCore import Qt, QSize, QRegExp
from src.core.utils import ASSETS_DIR, LOG_FILE
from src.core.utils import get_lang_from_registry, load_locale
from src.version import VERSION
import os
import logging

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

logger = logging.getLogger('geforce_presence')


# ---- ESTILOS GLOBALES ----
GAMING_STYLESHEET = """
    * {
        outline: none;
    }

    QDialog {
        background-color: #0d0e10;
        border: 2px solid #1b1f23;
        border-radius: 14px;
    }

    QLabel {
        font-size: 14px;
        font-family: "TT Octosquares Trl Cnd";
        color: #e0e0e0;
        padding-bottom: 4px;
    }

    QCheckBox, QRadioButton {
        color: #e0e0e0;
        font-size: 13px;
        font-family: "TT Octosquares Trl Cnd";
    }
    
    QCheckBox:disabled, QRadioButton:disabled {
        color: #707070;
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
        font-family: "TT Octosquares Trl Cnd";
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
        font-family: "TT Octosquares Trl Cnd";
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

    QPlainTextEdit {
        background-color: #131416;
        border: 1px solid #1f2428;
        border-radius: 8px;
        color: #cfcfcf;
        font-family: Consolas, "Courier New", monospace;
        font-size: 13px;
        padding: 8px;
    }
"""


class GamingMessageBox(QDialog):
    def __init__(self, title, text, icon_type="info", checkbox_text=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 20)
        layout.setSpacing(20)
        
        # Icon & Text Row
        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.lbl_text)
        
        # Checkbox
        self.checkbox = None
        if checkbox_text:
            from PyQt5.QtWidgets import QCheckBox
            self.checkbox = QCheckBox(checkbox_text)
            self.checkbox.setStyleSheet("""
                QCheckBox {
                    color: #cfcfcf;
                    font-size: 13px;
                    font-family: "TT Octosquares Trl Cnd";
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    background-color: #1a1b1d;
                    border: 1px solid #2c2f33;
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    background-color: #045D0E;
                    border: 1px solid #12881F;
                }
            """)
            layout.addWidget(self.checkbox, 0, Qt.AlignCenter)
        
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
        dlg = GamingMessageBox(title, text, "info", None, parent)
        dlg.exec_()
        
    @staticmethod
    def show_warning(parent, title, text):
        dlg = GamingMessageBox(title, text, "warning", None, parent)
        dlg.exec_()
        
    @staticmethod
    def show_question(parent, title, text, checkbox_text=None):
        dlg = GamingMessageBox(title, text, "question", checkbox_text, parent)
        res = dlg.exec_() == QDialog.Accepted
        if checkbox_text:
            return res, dlg.checkbox.isChecked()
        return res


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


class GamingTextInputDialog(QDialog):
    def __init__(self, title, label_text, default_value="", parent=None):
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
        
        self.entry = QLineEdit()
        self.entry.setText(default_value)
        layout.addWidget(self.entry)
        
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
        self.setFixedSize(350, 180)

    @staticmethod
    def get_text(parent, title, label, default_value=""):
        dlg = GamingTextInputDialog(title, label, default_value, parent)
        if dlg.exec_() == QDialog.Accepted:
            return dlg.entry.text().strip(), True
        return default_value, False


# ---- SYNTAX HIGHLIGHTER & LOG VIEWER ----
class LogHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)
        self.rules = []
        
        # Color definitions matching dark theme
        info_format = QTextCharFormat()
        info_format.setForeground(QColor("#00e676")) # bright green/cyan
        info_format.setFontWeight(QFont.Bold)
        
        warn_format = QTextCharFormat()
        warn_format.setForeground(QColor("#ffab00")) # orange/yellow
        warn_format.setFontWeight(QFont.Bold)
        
        error_format = QTextCharFormat()
        error_format.setForeground(QColor("#ff1744")) # red
        error_format.setFontWeight(QFont.Bold)
        
        debug_format = QTextCharFormat()
        debug_format.setForeground(QColor("#808080")) # gray
        
        # Rules: match [LEVEL] tags
        self.rules.append((QRegExp(r"\[DEBUG\]"), debug_format))
        self.rules.append((QRegExp(r"\[INFO\]"), info_format))
        self.rules.append((QRegExp(r"\[WARNING\]"), warn_format))
        self.rules.append((QRegExp(r"\[ERROR\]"), error_format))
        self.rules.append((QRegExp(r"\[CRITICAL\]"), error_format))

    def highlightBlock(self, text):
        for pattern, format in self.rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)


class GamingLogViewerDialog(QDialog):
    def __init__(self, texts=None, parent=None):
        super().__init__(parent)
        self.texts = texts if texts is not None else TEXTS
        self.setWindowTitle(self.texts.get("log_viewer_title", "Visor de Registros (Logs)"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        self.setMinimumSize(750, 500)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 15)
        layout.setSpacing(12)
        
        # Header
        title = QLabel(self.texts.get("log_viewer_title", "Visor de Registros (Logs)"))
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        desc = QLabel(self.texts.get("log_viewer_desc", "Historial de eventos de la aplicación. Si experimentas problemas, puedes exportar este archivo y enviarlo."))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 13px; color: #cfcfcf; padding-bottom: 5px;")
        layout.addWidget(desc)
        
        # Log Text Box
        self.log_text_edit = QPlainTextEdit()
        self.log_text_edit.setReadOnly(True)
        
        # Set up Syntax Highlighter
        self.highlighter = LogHighlighter(self.log_text_edit.document())
        
        layout.addWidget(self.log_text_edit)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.refresh_btn = QPushButton(self.texts.get("refresh", "Refresh"))
        self.refresh_btn.clicked.connect(self.load_logs)
        
        self.export_btn = QPushButton(self.texts.get("export", "Export Logs"))
        self.export_btn.setObjectName("secondary")
        self.export_btn.clicked.connect(self.on_export)
        
        self.close_btn = QPushButton(self.texts.get("close", "Close"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Initial load
        self.load_logs()

    def load_logs(self):
        log_content = ""
        try:
            if LOG_FILE.exists():
                # Read log file safely (ignoring encoding errors, avoiding locks)
                log_content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
            else:
                log_content = "No log file found."
        except Exception as e:
            log_content = f"Error reading log file: {e}"
            
        self.log_text_edit.setPlainText(log_content)
        
        # Auto scroll to bottom
        self.log_text_edit.moveCursor(QTextCursor.End)

    def on_export(self):
        default_name = "geforce_presence_logs.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.texts.get("export", "Export Logs"),
            default_name,
            "Log Files (*.log *.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                log_content = ""
                if LOG_FILE.exists():
                    log_content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                
                GamingMessageBox.show_info(
                    self,
                    "Success",
                    self.texts.get("logs_exported", "Logs successfully exported to {path}").replace("{path}", file_path)
                )
            except Exception as e:
                GamingMessageBox.show_warning(
                    self,
                    "Error",
                    self.texts.get("export_error", "Error exporting logs: {error}").replace("{error}", str(e))
                )


class CrashReporterDialog(QDialog):
    def __init__(self, traceback_text, texts=None, parent=None):
        super().__init__(parent)
        self.texts = texts if texts is not None else TEXTS
        self.setWindowTitle(self.texts.get("crash_title", "⚠️ Unexpected Error"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(GAMING_STYLESHEET)
        self.setMinimumSize(600, 450)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 25, 25, 20)
        layout.setSpacing(15)
        
        # Title Header
        title = QLabel(self.texts.get("crash_title", "⚠️ Unexpected Error"))
        title.setObjectName("title_label")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Message description
        desc = QLabel(self.texts.get("crash_msg", "The application has suffered an unhandled critical error. Details have been saved to logs. You can copy the error below to report it."))
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("font-size: 14px; color: #cfcfcf; padding-bottom: 8px;")
        layout.addWidget(desc)
        
        # Tech details heading
        tech_title = QLabel("System Details & Traceback:")
        tech_title.setStyleSheet("font-weight: bold; color: #ffffff;")
        layout.addWidget(tech_title)
        
        # Gather technical details
        import platform
        import sys
        from PyQt5.QtCore import QT_VERSION_STR
        import datetime
        
        tech_details = (
            f"App Version: {VERSION}\n"
            f"Python Version: {platform.python_version()}\n"
            f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]})\n"
            f"Qt Version: {QT_VERSION_STR}\n"
            f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"--------------------------------------------------\n"
        )
        
        self.full_error_text = tech_details + traceback_text
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(self.full_error_text)
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        self.copy_btn = QPushButton(self.texts.get("copy_error", "Copy Error"))
        self.copy_btn.clicked.connect(self.on_copy)

        self.hotfix_btn = QPushButton(self.texts.get("check_hotfix", "Check for Fix / Update"))
        self.hotfix_btn.clicked.connect(self.on_check_hotfix)
        
        self.export_btn = QPushButton(self.texts.get("export", "Export Logs"))
        self.export_btn.setObjectName("secondary")
        self.export_btn.clicked.connect(self.on_export)
        
        self.close_btn = QPushButton(self.texts.get("close", "Close"))
        self.close_btn.setObjectName("secondary")
        self.close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(self.hotfix_btn)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

    def on_check_hotfix(self):
        try:
            from src.core.updater import Updater
            updater = Updater(parent_widget=self)
            updater.check_for_updates(silent=False)
        except Exception as e:
            logger.error(f"Error al comprobar hotfix desde crash reporter: {e}")

    def on_copy(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.full_error_text)
        
        # Show a visual feedback
        copied_text = self.texts.get("error_copied", "Copied!")
        self.copy_btn.setText(f"✓ {copied_text}")
        self.copy_btn.setEnabled(False)
        
        from PyQt5.QtCore import QTimer
        # Reset button text after 2 seconds
        QTimer.singleShot(2000, lambda: [
            self.copy_btn.setText(self.texts.get("copy_error", "Copy Error")),
            self.copy_btn.setEnabled(True)
        ])

    def on_export(self):
        default_name = "geforce_presence_crash_logs.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.texts.get("export", "Export Logs"),
            default_name,
            "Log Files (*.log *.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                log_content = ""
                if LOG_FILE.exists():
                    log_content = LOG_FILE.read_text(encoding="utf-8", errors="ignore")
                
                # Prepend the crash details to the exported log
                full_export_content = (
                    "=== CRASH DETAILS ===\n" + 
                    self.full_error_text + 
                    "\n======================\n\n" + 
                    log_content
                )
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(full_export_content)
                
                GamingMessageBox.show_info(
                    self,
                    "Success",
                    self.texts.get("logs_exported", "Logs successfully exported to {path}").replace("{path}", file_path)
                )
            except Exception as e:
                GamingMessageBox.show_warning(
                    self,
                    "Error",
                    self.texts.get("export_error", "Error exporting logs: {error}").replace("{error}", str(e))
                )
