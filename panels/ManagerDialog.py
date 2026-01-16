from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget
from PyQt5.QtGui import QIcon  # <--- RICCARDO

from panels.ParametriPanel import ParametriPanel
from panels.ServiziPanel import ServiziPanel


class ManagerDialog(QDialog):
    """Manager window with two tabs: Parametri and Servizi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon("static/icon/icon_manager.ico"))  # RICCARDO

        self.setWindowTitle('Manager')
        # make dialog a top-level window with minimize and maximize buttons
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.parametri = ParametriPanel(self)
        self.servizi = ServiziPanel(self)

        self.tabs.addTab(self.parametri, 'Parametri')
        self.tabs.addTab(self.servizi, 'Servizi')

        layout.addWidget(self.tabs)
