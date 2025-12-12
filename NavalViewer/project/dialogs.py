"""dialogs.py
Contains PyQt dialogs used by the application:
- SettingsDialog: configure listener host/port and view raw messages
- AISDialog: list known AIS targets, change per-ship color, center on selection

Each dialog exposes a small API (e.g. `append_message`, `add_ship`) used
by the main window controller.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QColorDialog,
)
from PyQt5.QtGui import QColor, QPixmap, QIcon


class SettingsDialog(QDialog):
    """Dialog to start/stop the UDP listener and show raw messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Listener Settings")
        self.setMinimumSize(360, 300)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        # default host/port preconfigured
        self.host_input = QLineEdit("0.0.0.0")
        self.port_input = QLineEdit("10110")
        form.addRow("Host:", self.host_input)
        form.addRow("Port:", self.port_input)
        layout.addLayout(form)

        self.start_btn = QPushButton("Start Listener")
        self.start_btn.clicked.connect(self._on_start_stop)
        layout.addWidget(self.start_btn)

        self.msgs = QTextEdit()
        self.msgs.setReadOnly(True)
        layout.addWidget(self.msgs)

    def _on_start_stop(self):
        """Handler for start/stop button: calls parent start/stop methods."""
        host = self.host_input.text().strip() or '0.0.0.0'
        try:
            port = int(self.port_input.text().strip())
        except Exception:
            self.append_message('Invalid port value')
            return
        if self.parent is None:
            return
        if self.parent.listener is None:
            self.parent.start_listener(host, port)
            self.start_btn.setText('Stop Listener')
        else:
            self.parent.stop_listener()
            self.start_btn.setText('Start Listener')

    def append_message(self, msg: str):
        """Append a raw UDP/NMEA message to the text area."""
        self.msgs.append(msg)


class AISDialog(QDialog):
    """Dialog that lists known AIS targets and allows color editing.

    Items in the list store the MMSI in `Qt.UserRole`. When the user
    chooses a color the dialog calls `parent.set_ship_color(mmsi, color)`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle('AIS Targets')
        self.setMinimumSize(320, 400)

        layout = QVBoxLayout(self)
        self.list = QListWidget()
        layout.addWidget(self.list)

        btn_row = QHBoxLayout()
        self.color_btn = QPushButton('Change color')
        self.color_btn.clicked.connect(self.change_color)
        btn_row.addWidget(self.color_btn)

        self.center_btn = QPushButton('Center on selected')
        self.center_btn.clicked.connect(self.center_selected)
        btn_row.addWidget(self.center_btn)

        layout.addLayout(btn_row)

    def add_ship(self, mmsi: str, name: str = None, color: str = None):
        """Add a ship to the list if missing. The MMSI is saved in UserRole."""
        if mmsi is None:
            return
        # avoid duplicates
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.UserRole) == mmsi:
                return
        text = f"{mmsi} ({name})" if name and name != '-' else mmsi
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, mmsi)
        col = QColor(color) if color else QColor('#0077be')
        pix = QPixmap(16,16)
        pix.fill(col)
        item.setIcon(QIcon(pix))
        self.list.addItem(item)

    def change_color(self):
        """Open a color picker and inform the parent of the chosen color."""
        item = self.list.currentItem()
        if not item:
            return
        mmsi = item.data(Qt.UserRole)
        init = QColor('#0077be')
        col = QColorDialog.getColor(init, self, 'Select color')
        if not col.isValid():
            return
        hexc = col.name()
        pix = QPixmap(16,16)
        pix.fill(col)
        item.setIcon(QIcon(pix))
        if self.parent:
            try:
                self.parent.set_ship_color(mmsi, hexc)
            except Exception:
                pass

    def center_selected(self):
        """Center map on selected item by calling parent.center_on_mmsi."""
        item = self.list.currentItem()
        if not item:
            return
        mmsi = item.data(Qt.UserRole)
        if self.parent:
            self.parent.center_on_mmsi(mmsi)
