from typing import TYPE_CHECKING
from ..dialogs import AboutDialog

if TYPE_CHECKING:
    from ..tray_icon import SystemTrayIcon
    Base = SystemTrayIcon
else:
    Base = object

class UpdaterHandlerMixin(Base):
    def open_about(self):
        dlg = AboutDialog(texts=getattr(self, "texts", None), parent=self.parent() if hasattr(self, "parent") else None)
        dlg.exec_()

    def manual_check_updates(self):
        if self.updater:
            self.updater.check_for_updates(silent=False)
