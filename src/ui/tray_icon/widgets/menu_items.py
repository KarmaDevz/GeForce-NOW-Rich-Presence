from PyQt5.QtWidgets import QWidgetAction, QFrame, QHBoxLayout, QLabel, QMenu
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor

from ..constants import ASSETS_DIR
from ..styles import MENU_ITEM_FRAME_STYLESHEET, MENU_ITEM_TEXT_DANGER, MENU_ITEM_TEXT_NORMAL

class CustomMenuItemWidget(QFrame):
    clicked = pyqtSignal()

    def __init__(self, text, icon_name, right_icon_name=None, is_danger=False, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setObjectName("menu_item_widget")
        self.is_danger = is_danger
        self.setStyleSheet(MENU_ITEM_FRAME_STYLESHEET)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)

        # Left Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.set_left_icon(icon_name)
        
        # Text label
        self.text_label = QLabel(text)
        if self.is_danger:
            self.text_label.setStyleSheet(MENU_ITEM_TEXT_DANGER)
        else:
            self.text_label.setStyleSheet(MENU_ITEM_TEXT_NORMAL)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()

        # Right Icon/Arrow (if provided)
        if right_icon_name:
            self.right_label = QLabel()
            self.right_label.setFixedSize(14, 14)
            self.right_label.setAlignment(Qt.AlignCenter)
            self.set_right_icon(right_icon_name)
            layout.addWidget(self.right_label)

    def tint_pixmap(self, pixmap, color):
        tinted = QPixmap(pixmap.size())
        tinted.fill(Qt.transparent)
        painter = QPainter(tinted)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), color)
        painter.end()
        return tinted

    def update_icon_colors(self, is_hover=False):
        is_colored = hasattr(self, "left_icon_name") and "color" in self.left_icon_name
        
        if is_hover:
            color = QColor("#ffffff")
        elif self.is_danger:
            color = QColor("#ff4d4d")
        elif is_colored:
            # Show original brand colors when not hovered
            if hasattr(self, "original_left_pixmap"):
                self.icon_label.setPixmap(self.original_left_pixmap)
            if hasattr(self, "original_right_pixmap"):
                self.right_label.setPixmap(self.original_right_pixmap)
            return
        else:
            color = QColor("#b0b3b8")
            
        if hasattr(self, "original_left_pixmap"):
            tinted = self.tint_pixmap(self.original_left_pixmap, color)
            self.icon_label.setPixmap(tinted)
            
        if hasattr(self, "original_right_pixmap"):
            tinted = self.tint_pixmap(self.original_right_pixmap, color)
            self.right_label.setPixmap(tinted)

    def set_left_icon(self, icon_name):
        self.left_icon_name = icon_name
        # Helper map of fallbacks
        fallbacks = {
            "crosshair.svg": "🎯",
            "sync.svg": "🔄",
            "discord.svg": "💬",
            "target.svg": "✨",
            "gear.svg": "⚙️",
            "gamepad.svg": "🎮",
            "palette.svg": "🎨",
            "activity.svg": "🛠️",
            "file-text.svg": "📄",
            "refresh.svg": "⭐",
            "info.svg": "ℹ️",
            "log-out.svg": "❌",
            "gfn.svg": "G",
            "network.svg": "🌐",
            "diagnostics.svg": "🔍",
            "integrity.svg": "🛠️",
            "nvidia-color.svg": "🟢",
            "discord-color.svg": "💬",
            "steam-color.svg": "🎮"
        }
        
        path = ASSETS_DIR / "iconos" / icon_name
        if path.exists():
            self.original_left_pixmap = QPixmap(str(path)).scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.update_icon_colors(is_hover=False)
        else:
            fb = fallbacks.get(icon_name, "")
            self.icon_label.setText(fb)
            self.icon_label.setStyleSheet("color: #b0b3b8; font-size: 12px; font-weight: bold;")

    def set_right_icon(self, icon_name):
        fallbacks = {
            "chevron-right.svg": ">",
            "external-link.svg": "↗"
        }
        
        path = ASSETS_DIR / "iconos" / icon_name
        if path.exists():
            self.original_right_pixmap = QPixmap(str(path)).scaled(14, 14, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.update_icon_colors(is_hover=False)
        else:
            fb = fallbacks.get(icon_name, "")
            self.right_label.setText(fb)
            self.right_label.setStyleSheet("color: #5f6368; font-size: 11px; font-weight: bold;")

    def enterEvent(self, event):
        bg_color = "#8c1d1d" if self.is_danger else "#045D0E"
        self.setStyleSheet(f"""
            QFrame#menu_item_widget {{
                background-color: {bg_color};
                border-radius: 4px;
            }}
        """)
        self.text_label.setStyleSheet("color: #ffffff; font-size: 13px; font-family: 'TT Octosquares Trl Cnd'; font-weight: bold;")
        if hasattr(self, "right_label") and self.right_label.text():
            self.right_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        self.update_icon_colors(is_hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet("""
            QFrame#menu_item_widget {
                background-color: transparent;
                border-radius: 4px;
            }
        """)
        if self.is_danger:
            self.text_label.setStyleSheet(MENU_ITEM_TEXT_DANGER)
        else:
            self.text_label.setStyleSheet(MENU_ITEM_TEXT_NORMAL)
        if hasattr(self, "right_label") and self.right_label.text():
            self.right_label.setStyleSheet("color: #5f6368; font-size: 11px; font-weight: bold;")
        self.update_icon_colors(is_hover=False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Retrieve and close the parent menu first while the widget is still valid
            p = self.parent()
            parent_menu = None
            while p:
                if isinstance(p, QMenu):
                    parent_menu = p
                    break
                p = p.parent()
            
            if parent_menu:
                parent_menu.close()
            
            # Call super mouseReleaseEvent to propagate the event safely
            super().mouseReleaseEvent(event)
            
            # Emit clicked signal. Note that slot handlers may delete this widget,
            # so do not access self or call methods after this point.
            self.clicked.emit()
        else:
            super().mouseReleaseEvent(event)

class CustomMenuItemAction(QWidgetAction):
    def __init__(self, text, icon_name, right_icon_name=None, is_danger=False, parent=None):
        super().__init__(parent)
        self.widget = CustomMenuItemWidget(text, icon_name, right_icon_name, is_danger, parent)
        self.setDefaultWidget(self.widget)
        self.triggered = self.widget.clicked

class SectionHeaderAction(QWidgetAction):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.widget = QFrame()
        self.widget.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(12, 10, 12, 4)
        layout.setSpacing(0)
        
        self.label = QLabel(text.upper())
        self.label.setStyleSheet("""
            color: #6a6f73;
            font-size: 10px;
            font-family: 'TT Octosquares Trl Cnd';
            font-weight: bold;
            letter-spacing: 0.5px;
            background-color: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        """)
        layout.addWidget(self.label)
        self.setDefaultWidget(self.widget)

class VersionLabelAction(QWidgetAction):
    def __init__(self, version_text, parent=None):
        super().__init__(parent)
        self.widget = QFrame()
        self.widget.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(self.widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)
        
        self.label = QLabel(version_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("""
            color: #5f6368;
            font-size: 10px;
            font-family: 'TT Octosquares Trl Cnd';
            background-color: transparent;
            border: none;
            padding: 0px;
            margin: 0px;
        """)
        layout.addWidget(self.label)
        self.setDefaultWidget(self.widget)
