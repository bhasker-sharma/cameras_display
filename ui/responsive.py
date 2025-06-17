# camera_app/ui/responsive.py

from PyQt5.QtGui import QGuiApplication

# Reference resolution for scaling
BASE_WIDTH = 1920
BASE_HEIGHT = 1080

class ScreenScaler:
    def __init__(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.width = screen.width()
        self.height = screen.height()
        self.scale_factor_w = self.width / BASE_WIDTH
        self.scale_factor_h = self.height / BASE_HEIGHT
        self.scale_factor = min(self.scale_factor_w, self.scale_factor_h)

    def scale(self, value):
        """Scale based on average (uniform) factor"""
        return int(value * self.scale_factor)

    def scale_w(self, value):
        """Scale based on screen width"""
        return int(value * self.scale_factor_w)

    def scale_h(self, value):
        """Scale based on screen height"""
        return int(value * self.scale_factor_h)
