"""The branded banner: shows the whole image at every width, sized from its own aspect ratio."""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel

from ui.branding import APP_AUTHOR, APP_NAME, APP_SUBTITLE, banner_path

BANNER_MIN_HEIGHT = 90
BANNER_MAX_HEIGHT = 260


def banner_height_for(width: int, source: QSize) -> int:
    """Label height that shows the whole banner at ``width``, clamped to a sensible band."""
    natural = round(width * source.height() / max(1, source.width()))
    return max(BANNER_MIN_HEIGHT, min(BANNER_MAX_HEIGHT, natural))


class BrandBanner(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.source = QPixmap(str(banner_path()))
        self.setObjectName("brandBanner")
        self.setFixedHeight(banner_height_for(900, self.source.size()))
        self.setAlignment(Qt.AlignCenter)
        self.setAccessibleName(f"{APP_NAME} banner")
        self.setAccessibleDescription(f"{APP_NAME}, {APP_SUBTITLE}, by {APP_AUTHOR}.")
        self.setStyleSheet("QLabel#brandBanner { background-color: #07151c; border-radius: 8px; }")
        # Parented single-shot timer: if the banner is deleted before it fires, Qt stops it with the widget.
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(0)
        self._settle.timeout.connect(self.refresh)
        self.refresh()

    def refresh(self):
        if self.source.isNull():
            self.setText(f"{APP_NAME}\n{APP_SUBTITLE}\nby {APP_AUTHOR}")
            return
        width = self.width()
        if width <= 0:
            return
        height = banner_height_for(width, self.source.size())
        self.setFixedHeight(height)
        ratio = self.devicePixelRatioF()
        scaled = self.source.scaled(
            QSize(int(width * ratio), int(height * ratio)), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        scaled.setDevicePixelRatio(ratio)
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()
        self._settle.start()  # again once the layout has settled
