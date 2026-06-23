import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QWidget
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QFont, QFontDatabase, QLinearGradient, QPen

from ..constants import ASSETS_DIR
from src.core.utils import get_lang_from_registry, load_locale
from src.version import VERSION

try:
    LANG = get_lang_from_registry()
    TEXTS = load_locale(LANG)
except Exception:
    LANG = os.getenv('GEFORCE_LANG', 'en')
    TEXTS = load_locale(LANG)

# Load custom fonts lazily after QApplication is created
_fonts_loaded = False

def load_about_fonts():
    global _fonts_loaded
    if _fonts_loaded:
        return
    gfn_font_path = ASSETS_DIR / "GEFORCENOW.otf"
    rp_over_font_path = ASSETS_DIR / "RICHPRESENCEOver.ttf"
    rp_under_font_path = ASSETS_DIR / "RICHPRESENCEUnder.ttf"

    if gfn_font_path.exists():
        QFontDatabase.addApplicationFont(str(gfn_font_path))
    if rp_over_font_path.exists():
        QFontDatabase.addApplicationFont(str(rp_over_font_path))
    if rp_under_font_path.exists():
        QFontDatabase.addApplicationFont(str(rp_under_font_path))
    _fonts_loaded = True


class RichPresenceTitle(QWidget):
    def __init__(self, text="RICH PRESENCE", parent=None):
        load_about_fonts()
        super().__init__(parent)
        self.text = text
        self.under_font = QFont('Platinum Sign Under', 34)
        self.over_font = QFont('Platinum Sign Over', 34)
        self.setFixedHeight(65)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        under_color = QColor("#0B5900")
        over_color = QColor("#ffffff")
        
        # Shadow/Under Layer
        painter.setFont(self.under_font)
        painter.setPen(under_color)
        shadow_rect = self.rect().translated(4, 4)
        painter.drawText(shadow_rect, Qt.AlignCenter, self.text)
        
        # Overlay/Outline Layer
        painter.setFont(self.over_font)
        painter.setPen(over_color)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text)


class ShinyTextLabel(QLabel):
    def __init__(self, text, base_color="#b5b5b5", shine_color="#ffffff", parent=None):
        super().__init__(text, parent)
        self.base_color = QColor(base_color)
        self.shine_color = QColor(shine_color)
        self.offset = -1.0 # From -1.0 to 2.0
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(33) # ~30fps
        
    def animate(self):
        self.offset += 0.035
        if self.offset > 2.0:
            self.offset = -1.0
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        w = self.width()
        
        x1 = w * self.offset
        x2 = x1 + (w * 0.45) # spread width
        
        gradient = QLinearGradient(x1, 0, x2, 0)
        gradient.setSpread(QLinearGradient.PadSpread)
        gradient.setColorAt(0.0, self.base_color)
        gradient.setColorAt(0.5, self.shine_color)
        gradient.setColorAt(1.0, self.base_color)
        
        pen = QPen()
        pen.setBrush(QBrush(gradient))
        painter.setPen(pen)
        painter.setFont(self.font())
        
        painter.drawText(self.rect(), self.alignment(), self.text())


class HeartBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 44)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw solid white circle background
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.width(), self.height())
        
        # Draw heart.svg in the center
        path = ASSETS_DIR / "iconos" / "heart.svg"
        if path.exists():
            pixmap = QPixmap(str(path)).scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Tint heart to dark background color #0c0d0e
            tinted = QPixmap(pixmap.size())
            tinted.fill(Qt.transparent)
            p = QPainter(tinted)
            p.setRenderHint(QPainter.Antialiasing)
            p.drawPixmap(0, 0, pixmap)
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(tinted.rect(), QColor("#0c0d0e"))
            p.end()
            
            x = (self.width() - tinted.width()) // 2
            y = (self.height() - tinted.height()) // 2
            painter.drawPixmap(x, y, tinted)


class SocialButton(QWidget):
    def __init__(self, text, icon_name, url, is_circular=True, bg_color=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.is_circular = is_circular
        self.bg_color = bg_color
        self.icon_name = icon_name
        self.is_hovered = False
        
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)
        
        # Icon Label
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(36, 36)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.render_icon()
        
        # Text Label
        self.text_label = QLabel(text)
        self.text_label.setStyleSheet("""
            color: #dcddde;
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            font-weight: bold;
        """)
        
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.setLayout(layout)
        
    def render_icon(self):
        pix = QPixmap(36, 36)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if self.is_circular and self.bg_color:
            painter.setBrush(QBrush(QColor(self.bg_color)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 36, 36)
            
            icon_path = ASSETS_DIR / "iconos" / self.icon_name
            if not icon_path.exists():
                icon_path = ASSETS_DIR / self.icon_name
                
            if icon_path.exists():
                icon_pix = QPixmap(str(icon_path)).scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                tinted = QPixmap(icon_pix.size())
                tinted.fill(Qt.transparent)
                p = QPainter(tinted)
                p.setRenderHint(QPainter.Antialiasing)
                p.drawPixmap(0, 0, icon_pix)
                p.setCompositionMode(QPainter.CompositionMode_SourceIn)
                p.fillRect(tinted.rect(), QColor("#ffffff"))
                p.end()
                
                x = (36 - tinted.width()) // 2
                y = (36 - tinted.height()) // 2
                painter.drawPixmap(x, y, tinted)
        else:
            icon_path = ASSETS_DIR / "iconos" / self.icon_name
            if not icon_path.exists():
                icon_path = ASSETS_DIR / self.icon_name
                
            if icon_path.exists():
                icon_pix = QPixmap(str(icon_path)).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                tinted = QPixmap(icon_pix.size())
                tinted.fill(Qt.transparent)
                p = QPainter(tinted)
                p.setRenderHint(QPainter.Antialiasing)
                p.drawPixmap(0, 0, icon_pix)
                p.setCompositionMode(QPainter.CompositionMode_SourceIn)
                
                color_hex = "#ffffff" if self.is_hovered else "#e0e0e0"
                p.fillRect(tinted.rect(), QColor(color_hex))
                p.end()
                
                x = (36 - tinted.width()) // 2
                y = (36 - tinted.height()) // 2
                painter.drawPixmap(x, y, tinted)
                
        painter.end()
        self.icon_label.setPixmap(pix)
        
    def enterEvent(self, event):
        self.is_hovered = True
        self.text_label.setStyleSheet("""
            color: #00e676;
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            font-weight: bold;
        """)
        self.render_icon()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self.is_hovered = False
        self.text_label.setStyleSheet("""
            color: #dcddde;
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            font-weight: bold;
        """)
        self.render_icon()
        super().leaveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            import webbrowser
            webbrowser.open(self.url)
        super().mouseReleaseEvent(event)


class AboutDialog(QDialog):
    def __init__(self, texts=None, parent=None):
        load_about_fonts()
        super().__init__(parent)
        
        # Load local translations dynamically on init
        if texts is None:
            try:
                lang = get_lang_from_registry()
                self.texts = load_locale(lang)
            except Exception:
                lang = os.getenv('GEFORCE_LANG', 'en')
                self.texts = load_locale(lang)
        else:
            self.texts = texts
            
        self.setWindowTitle(self.texts.get("about", "About"))
        self.setWindowIcon(QIcon(str(ASSETS_DIR / "geforce.ico")))
        self.setFixedSize(680, 505)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                border: 1px solid #1b1f23;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(35, 20, 35, 20)
        layout.setSpacing(10)
        
        # 1. GEFORCE NOW Header
        self.gfn_label = QLabel("GEFORCE NOW")
        self.gfn_label.setAlignment(Qt.AlignCenter)
        self.gfn_label.setStyleSheet("""
            color: #ffffff;
            font-size: 50px;
            font-family: "Akira Expanded";
            font-weight: bold;
            background: transparent;
            padding: 0px;
            margin: 0px;
        """)
        layout.addWidget(self.gfn_label)
        
        # 2. RICH PRESENCE custom layered widget
        self.rp_title = RichPresenceTitle("RICH PRESENCE")
        layout.addWidget(self.rp_title)
        
        # 3. Logo Row (GFN & Discord side by side)
        logo_layout = QHBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        logo_layout.setSpacing(15)
        
        gfn_logo_path = ASSETS_DIR / "GFNblackbg.jpg"
        discord_logo_path = ASSETS_DIR / "discordblackbg.jpg"
        
        if gfn_logo_path.exists():
            gfn_logo_lbl = QLabel()
            gfn_logo_lbl.setPixmap(QPixmap(str(gfn_logo_path)))
            logo_layout.addWidget(gfn_logo_lbl)
            
        if discord_logo_path.exists():
            discord_logo_lbl = QLabel()
            discord_logo_lbl.setPixmap(QPixmap(str(discord_logo_path)))
            logo_layout.addWidget(discord_logo_lbl)
            
        layout.addLayout(logo_layout)
        
        # 4. Description Label
        self.desc_label = QLabel(self.texts.get("about_desc_1", "GeForce NOW Rich Presence mejora tu experiencia en Discord\nmostrando lo que juegas en tiempo real"))
        self.desc_label.setAlignment(Qt.AlignCenter)
        self.desc_label.setStyleSheet("""
            color: #ffffff;
            font-size: 18px;
            font-family: "TT Octosquares Trl Cnd";
            background: transparent;
        """)
        layout.addWidget(self.desc_label)

        self.desc_label2 = QLabel(self.texts.get("about_desc_2", "Hecho para la comunidad de GeForce NOW y Discord."))
        self.desc_label2.setAlignment(Qt.AlignCenter)
        self.desc_label2.setStyleSheet("""
            color: #7A7A7A;
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            background: transparent;
        """)
        layout.addWidget(self.desc_label2)
        
        # 5. Dedication Card (QFrame)
        self.dedication_card = QFrame()
        self.dedication_card.setFixedSize(470, 72)
        self.dedication_card.setStyleSheet("""
            QFrame {
                background-color: #0c0d0e;
                border: 1px solid #2d3139;
                border-radius: 10px;
            }
        """)
        
        card_layout = QHBoxLayout(self.dedication_card)
        card_layout.setContentsMargins(15, 12, 15, 12)
        card_layout.setSpacing(15)
        card_layout.setAlignment(Qt.AlignVCenter)
        
        self.badge = HeartBadge()
        card_layout.addWidget(self.badge)
        
        text_vbox = QVBoxLayout()
        text_vbox.setContentsMargins(0, 0, 0, 0)
        text_vbox.setSpacing(4)
        
        # Developed by line with ShinyText name
        dev_layout = QHBoxLayout()
        dev_layout.setContentsMargins(0, 0, 0, 0)
        dev_layout.setSpacing(4)
        dev_layout.setAlignment(Qt.AlignLeft)
        
        dev_lbl = QLabel(self.texts.get("about_dev_by", "Este proyecto fue desarrollado con cariño por"))
        dev_lbl.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            border: none;
            background: transparent;
        """)
        dev_layout.addWidget(dev_lbl)
        
        # Shiny text label for KarmaDevz
        self.shiny_name = ShinyTextLabel("KarmaDevz", base_color="#57A851", shine_color="#0B5900")
        self.shiny_name.setStyleSheet("""
            font-size: 13px;
            font-family: "TT Octosquares Trl Cnd";
            font-weight: bold;
            border: none;
            background: transparent;
        """)
        self.shiny_name.setFixedWidth(85) # Ensure enough space for text + shine
        dev_layout.addWidget(self.shiny_name)
        
        text_vbox.addLayout(dev_layout)
        
        support_lbl = QLabel(self.texts.get("about_support", "Si te gusta este proyecto, considera apoyar su desarrollo."))
        support_lbl.setStyleSheet("""
            color: #8a8d90;
            font-size: 12px;
            font-family: "TT Octosquares Trl Cnd";
            border: none;
            background: transparent;
        """)
        text_vbox.addWidget(support_lbl)
        
        card_layout.addLayout(text_vbox, 1)
        layout.addWidget(self.dedication_card, 0, Qt.AlignCenter)
        
        # 6. Social Buttons Row
        social_layout = QHBoxLayout()
        social_layout.setAlignment(Qt.AlignCenter)
        social_layout.setSpacing(35)
        
        btn_github = SocialButton(self.texts.get("about_btn_repo", "Ver repositorio"), "github.svg", "https://github.com/KarmaDevz/GeForce-NOW-Rich-Presence", is_circular=False)
        btn_discord = SocialButton(self.texts.get("about_btn_server", "Entrar al servidor"), "discord.svg", "https://discord.gg/kHUvndZnw7", is_circular=True, bg_color="#5865F2")
        btn_paypal = SocialButton(self.texts.get("about_btn_support", "Apóyame"), "paypal.png", "https://www.paypal.com/paypalme/KarmaDevz", is_circular=True, bg_color="#0079C1")
        
        social_layout.addWidget(btn_github)
        social_layout.addWidget(btn_discord)
        social_layout.addWidget(btn_paypal)
        
        layout.addLayout(social_layout)
        
        # Spacing before footer
        layout.addStretch()
        
        # 7. Version Footer
        footer_text = f"{VERSION} • Open Source • MIT License"
        self.footer_lbl = QLabel(footer_text)
        self.footer_lbl.setAlignment(Qt.AlignCenter)
        self.footer_lbl.setStyleSheet("""
            color: #5f6368;
            font-size: 11px;
            font-family: "TT Octosquares Trl Cnd";
            background: transparent;
        """)
        layout.addWidget(self.footer_lbl)
        
        self.setLayout(layout)
