"""main_window.py
Contains `MainWindow` which coordinates the GUI, listener and map.

This module keeps an in-memory registry of ships (`self.ships`), handles
incoming lines from the UDP listener, decodes NMEA/AIS (when libraries
are present) and updates the embedded web map via `runJavaScript`.
"""
import json
import time
from pathlib import Path
from PyQt5.QtCore import QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)

from listener import UDPListener
# Manager dialog will live in panels/ManagerDialog.py
from dialogs import SettingsDialog, AISDialog
try:
    from panels.ManagerDialog import ManagerDialog
except Exception:
    ManagerDialog = None
from utils import color_from_string_py

try:
    from pyais import decode as ais_decode
    HAS_PYAIS = True
except Exception:
    HAS_PYAIS = False

try:
    import pynmea2
    HAS_PY_NMEA = True
except Exception:
    HAS_PY_NMEA = False


class MainWindow(QMainWindow):
    """Main application window + controller logic.

    Responsibilities:
    - maintain and display the embedded Leaflet map (in `map.html`)
    - start/stop UDP listener
    - parse incoming messages and forward map updates
    - expose methods used by dialogs (start_listener, stop_listener, set_ship_color)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("NavalViewer - AIS & Chart Viewer")
        self.resize(1000, 700)

        self.queue = None
        self.listener = None
        self.settings_dialog = None
        self.ais_dialog = None
        self.ship_colors = {}
        self.ships = {}

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # top + content
        content = QHBoxLayout()

        # Web map (left)
        self.view = QWebEngineView()
        map_path = Path(__file__).parent / "map.html"
        self.view.load(QUrl.fromLocalFile(str(map_path.resolve())))
        content.addWidget(self.view, 10)

        # simple right column with buttons
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(8, 8, 8, 8)
        self.status_label = QLabel("Stopped\nListener")
        right_layout.addWidget(self.status_label)
        self.open_dialog_btn = QPushButton("Listener Settings")
        self.open_dialog_btn.clicked.connect(self.open_listener_dialog)
        right_layout.addWidget(self.open_dialog_btn)
        self.open_ais_btn = QPushButton("AIS Targets")
        self.open_ais_btn.clicked.connect(self.open_ais_dialog)
        right_layout.addWidget(self.open_ais_btn)
        self.open_manager_btn = QPushButton("Manager")
        self.open_manager_btn.clicked.connect(self.open_manager_dialog)
        right_layout.addWidget(self.open_manager_btn)
        right_layout.addStretch()
        content.addWidget(right_col, 0)

        layout.addLayout(content)

        # queue and timer for polling listener messages
        import queue as _q
        self.queue = _q.Queue()
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self._poll)
        self.timer.start()

    def open_listener_dialog(self):
        """Open or create the Settings dialog."""
        if self.settings_dialog is None:
            self.settings_dialog = SettingsDialog(self)
        # ensure correct button state
        if self.listener is None:
            self.settings_dialog.start_btn.setText('Start Listener')
        else:
            self.settings_dialog.start_btn.setText('Stop Listener')
        self.settings_dialog.show()

    def open_ais_dialog(self):
        """Open or create the AIS dialog and populate known ships."""
        if self.ais_dialog is None:
            self.ais_dialog = AISDialog(self)
        # populate with known ships, compute default color if needed
        for mmsi, info in self.ships.items():
            col = self.ship_colors.get(mmsi) or color_from_string_py(mmsi)
            self.ais_dialog.add_ship(mmsi, info.get('name'), col)
        self.ais_dialog.show()

    def open_manager_dialog(self):
        """Open or create the Manager dialog."""
        if getattr(self, 'manager_dialog', None) is None:
            self.manager_dialog = ManagerDialog(self)
        self.manager_dialog.show()

    def start_listener(self, host, port):
        """Start the UDP listener thread pointing to `self.queue`."""
        if self.listener is not None:
            return
        self.listener = UDPListener(host, port, self.queue)
        self.listener.start()
        self.status_label.setText(f"Listening\n{host}:{port}")
        if self.settings_dialog:
            self.settings_dialog.start_btn.setText('Stop Listener')

    def stop_listener(self):
        """Stop the UDP listener thread if running."""
        if self.listener is None:
            return
        self.listener.stop()
        self.listener = None
        self.status_label.setText('Stopped\nListener')
        if self.settings_dialog:
            self.settings_dialog.start_btn.setText('Start Listener')

    def _poll(self):
        """Poll the queue for incoming UDP lines and process them."""
        try:
            while True:
                msg, addr = self.queue.get_nowait()
                if msg == "__ERROR__":
                    if self.settings_dialog:
                        self.settings_dialog.append_message(f"Error: {addr}")
                    continue
                if self.settings_dialog:
                    self.settings_dialog.append_message(msg)
                self.process_nmea(msg)
        except Exception:
            # no items or other parsing issue; simply return
            return

    def process_nmea(self, line: str):
        """Parse an incoming line and update map accordingly.

        Supports basic NMEA via `pynmea2` and AIS via `pyais` when available.
        This method performs best-effort parsing and will silently ignore
        unsupported lines or parse errors.
        """
        if line.startswith("$") and HAS_PY_NMEA:
            try:
                n = pynmea2.parse(line)
                if hasattr(n, 'latitude') and hasattr(n, 'longitude'):
                    lat = n.latitude
                    lon = n.longitude
                    sog = getattr(n, 'spd_over_grnd', 0)
                    cog = getattr(n, 'true_course', 0)
                    info = {'source': 'nmea'}
                    self.update_map(lat, lon, sog or 0, cog or 0, info)
            except Exception:
                pass
        elif (line.startswith('!AIVDM') or line.startswith('!AIVDO')) and HAS_PYAIS:
            try:
                decoded = ais_decode(line)
                if hasattr(decoded, '__iter__') and not isinstance(decoded, dict):
                    for msg in decoded:
                        lat = getattr(msg, 'lat', None) or (msg.get('lat') if isinstance(msg, dict) else None)
                        lon = getattr(msg, 'lon', None) or (msg.get('lon') if isinstance(msg, dict) else None)
                        sog = getattr(msg, 'sog', 0) or (msg.get('sog', 0) if isinstance(msg, dict) else 0)
                        cog = getattr(msg, 'cog', 0) or (msg.get('cog', 0) if isinstance(msg, dict) else 0)
                        info = {}
                        if isinstance(msg, dict):
                            info['mmsi'] = msg.get('mmsi') or msg.get('MMSI')
                            info['name'] = msg.get('name')
                            info['type'] = msg.get('ship_type') or msg.get('type')
                        else:
                            info['mmsi'] = getattr(msg, 'mmsi', None)
                            info['name'] = getattr(msg, 'name', None)
                            info['type'] = getattr(msg, 'ship_type', None) or getattr(msg, 'type', None)
                        if lat and lon:
                            self.update_map(float(lat), float(lon), float(sog), float(cog), info)
                else:
                    msg = decoded
                    lat = getattr(msg, 'lat', None) or (msg.get('lat') if isinstance(msg, dict) else None)
                    lon = getattr(msg, 'lon', None) or (msg.get('lon') if isinstance(msg, dict) else None)
                    sog = getattr(msg, 'sog', 0) or (msg.get('sog', 0) if isinstance(msg, dict) else 0)
                    cog = getattr(msg, 'cog', 0) or (msg.get('cog', 0) if isinstance(msg, dict) else 0)
                    info = {}
                    if isinstance(msg, dict):
                        info['mmsi'] = msg.get('mmsi') or msg.get('MMSI')
                        info['name'] = msg.get('name')
                        info['type'] = msg.get('ship_type') or msg.get('type')
                    else:
                        info['mmsi'] = getattr(msg, 'mmsi', None)
                        info['name'] = getattr(msg, 'name', None)
                        info['type'] = getattr(msg, 'ship_type', None) or getattr(msg, 'type', None)
                    if lat and lon:
                        self.update_map(float(lat), float(lon), float(sog), float(cog), info)
            except Exception:
                pass

    def update_map(self, lat, lon, sog=0, cog=0, info=None):
        """Send an update to the JavaScript map.

        This method prepares a safe JSON-escaped JS call to `updateShip`.
        It also stores the last known ship state in `self.ships` and informs
        the AIS dialog when new ships appear.
        """
        if info is None:
            info = {}
        mmsi = str(info.get('mmsi') or '-')
        name = str(info.get('name') or '-')
        typ = str(info.get('type') or '-')
        # determine color override if present, otherwise derive same color JS uses
        color = None
        if hasattr(self, 'ship_colors'):
            color = self.ship_colors.get(mmsi)
        if not color and mmsi and mmsi != '-':
            color = color_from_string_py(mmsi)
        mmsi_js = json.dumps(mmsi)
        name_js = json.dumps(name)
        type_js = json.dumps(typ)
        color_js = json.dumps(color) if color else 'null'
        js = f"updateShip({lat}, {lon}, {sog}, {cog}, {mmsi_js}, {name_js}, {type_js}, {color_js});"
        self.view.page().runJavaScript(js)
        # store last known info
        if mmsi and mmsi != '-':
            self.ships[mmsi] = {
                'mmsi': mmsi,
                'name': name,
                'type': typ,
                'lat': lat,
                'lon': lon,
                'sog': sog,
                'cog': cog,
                'last': time.time(),
            }
            if self.ais_dialog:
                try:
                    self.ais_dialog.add_ship(mmsi, name, self.ship_colors.get(mmsi))
                except Exception:
                    pass

    def center_on_mmsi(self, mmsi: str):
        """Center the web map on the marker for the specified MMSI."""
        try:
            mmsi_js = json.dumps(str(mmsi))
            js = f"centerOnShip({mmsi_js});"
            self.view.page().runJavaScript(js)
        except Exception:
            pass

    def set_ship_color(self, mmsi: str, color: str):
        """Set a color override for a ship and inform JavaScript to update visuals."""
        self.ship_colors[str(mmsi)] = color
        try:
            mmsi_js = json.dumps(str(mmsi))
            color_js = json.dumps(color)
            js = f"setShipColor({mmsi_js}, {color_js});"
            self.view.page().runJavaScript(js)
        except Exception:
            pass
