from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTabWidget
from PyQt5.QtGui import QIcon  # <--- RICCARDO

# import the subpanels directly
from subpanels.PortiPanel import PortiPanel
from subpanels.VascelliPanel import VascelliPanel
from subpanels.TrattePanel import TrattePanel
from subpanels.CorsePanel import CorsePanel
from subpanels.PianiOperativiPanel import PianiOperativiPanel
from subpanels.SimulazioniPanel import SimulazioniPanel
from subpanels.ComponentiPanel import ComponentiPanel


class ManagerDialog(QDialog):
    """Manager window with two tabs: Parametri and Servizi."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon("static/icon/icon_manager.ico"))  # RICCARDO

        self.setWindowTitle('Manager')
        # make dialog a top-level window with minimize and maximize buttons
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setMinimumSize(1100, 700)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # add subpanels directly as tabs
        self.porti = PortiPanel(self)
        self.vascelli = VascelliPanel(self)
        self.tratte = TrattePanel(self)
        self.corse = CorsePanel(self)
        self.piani = PianiOperativiPanel(self)
        self.simulazioni = SimulazioniPanel(self)
        self.componenti = ComponentiPanel(self)

        self.tabs.addTab(self.porti, 'Porti')
        self.tabs.addTab(self.vascelli, 'Vascelli')
        self.tabs.addTab(self.componenti, 'Componenti')
        self.tabs.addTab(self.tratte, 'Tratte')
        self.tabs.addTab(self.corse, 'Corse')
        self.tabs.addTab(self.piani, 'Piani Operativi')
        self.tabs.addTab(self.simulazioni, 'Simulazioni')

        layout.addWidget(self.tabs)
