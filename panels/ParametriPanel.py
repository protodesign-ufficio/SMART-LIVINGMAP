
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PyQt5.QtGui import QIcon # RICCARDO

from subpanels.PortiPanel import PortiPanel
from subpanels.VascelliPanel import VascelliPanel
from subpanels.TrattePanel import TrattePanel
from subpanels.CorsePanel import CorsePanel


class ParametriPanel(QWidget):
    """Panel containing sub-tabs: Porti, Vascelli, Tratte, Corse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon("static/icon/settings_icon.ico")) # RICCARDO
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.porti = PortiPanel(self)
        self.vascelli = VascelliPanel(self)
        self.tratte = TrattePanel(self)
        self.corse = CorsePanel(self)

        self.tabs.addTab(self.porti, 'Porti')
        self.tabs.addTab(self.vascelli, 'Vascelli')
        self.tabs.addTab(self.tratte, 'Tratte')
        self.tabs.addTab(self.corse, 'Corse')

        layout.addWidget(self.tabs)
