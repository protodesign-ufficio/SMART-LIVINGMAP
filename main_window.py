import json
import time
from pathlib import Path
from PyQt5.QtCore import QUrl, QTimer
# logging removed per user request
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)
from PyQt5.QtGui import QIcon  # <--- RICCARDO

# Manager dialog will live in panels/ManagerDialog.py
try:
    from panels.ManagerDialog import ManagerDialog
except Exception:
    ManagerDialog = None

try:
    from ApiClient import get_json
except Exception:
    get_json = None

# Classe _webbridge: helper QObject exposed to the web page via QWebChannel
class _WebBridge(QObject):
    def __init__(self, main_window):
        super().__init__()
        self._mw = main_window

    @pyqtSlot(str, str, str, int, int)
    def openDashboard(self, page_relative, query_json, title, width, height):
        try:
            q = None
            if query_json:
                import json as _json
                try:
                    q = _json.loads(query_json)
                except Exception:
                    q = None
            # call the MainWindow helper to open the dashboard
            self._mw.open_dashboard_embedded(page_relative, query=q, title=title or None, size=(width or 1500, height or 900))
        except Exception:
            pass


class MainWindow(QMainWindow):
    """Main application window + controller logic.

    Responsibilities:
    - maintain and display the embedded Leaflet map (in `map.html`)
    - open/manage various dialogs (Manager, Settings, etc)
    """

    def __init__(self, queue=None):
        # Accept an optional `queue.Queue` with AIS messages produced by
        # `consumer_ais.ConsumerAIS` running in a background thread.
        super().__init__()
        self.setWindowIcon(QIcon("static/icon/settings_icon.ico")) # RICCARDO
        self._ais_queue = queue
        self.setWindowTitle("NavalViewer - Chart Viewer")
        self.resize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # top + content
        content = QHBoxLayout()

        # Web map (left)
        # use a custom QWebEnginePage to handle window.open/popups so
        # dashboard links opened from JS popups create an embedded dialog
        class PopupPage(QWebEnginePage):
            def __init__(self, parent_window, profile=None):
                # allow passing profile to share cookies etc
                if profile is None:
                    super().__init__(parent_window)
                else:
                    super().__init__(profile, parent_window)
                self._parent_window = parent_window

            def createWindow(self, _type):
                try:
                    from PyQt5.QtWidgets import QDialog, QVBoxLayout
                    dlg = QDialog(self._parent_window)
                    dlg.setWindowTitle('Dashboard')
                    dlg.resize(1000, 700)
                    layout = QVBoxLayout(dlg)
                    new_view = QWebEngineView(dlg)
                    # create a new page for the new view sharing the same profile
                    new_page = QWebEnginePage(self.profile(), new_view)
                    new_view.setPage(new_page)
                    layout.addWidget(new_view)
                    dlg.setModal(False)
                    try:
                        from PyQt5.QtCore import Qt
                        dlg.setWindowModality(Qt.NonModal)
                    except Exception:
                        pass
                    dlg.show()
                    # keep reference on parent to avoid GC
                    try:
                        lst = getattr(self._parent_window, '_popup_dialogs', None)
                        if lst is None:
                            self._parent_window._popup_dialogs = [dlg]
                        else:
                            lst.append(dlg)
                    except Exception:
                        pass
                    return new_page
                except Exception:
                    return super().createWindow(_type)

        # create the main view and set our PopupPage so window.open works
        self.view = QWebEngineView()
        try:
            # replace the page with our PopupPage using the same profile
            popup_page = PopupPage(self, self.view.page().profile())
            self.view.setPage(popup_page)
        except Exception:
            # fallback: leave default page
            pass
        # expose a small webchannel bridge object to the page so JS can
        # request the application to open embedded dashboards
        try:
            self._webbridge = _WebBridge(self)
            channel = QWebChannel(self.view.page())
            channel.registerObject('pyMain', self._webbridge)
            try:
                self.view.page().setWebChannel(channel)
            except Exception:
                # older/newer PyQt variants may not need this call
                pass
        except Exception:
            pass
        map_path = Path(__file__).parent / 'static/map.html'
        self.view.load(QUrl.fromLocalFile(str(map_path.resolve())))
        # when the embedded map has finished loading, request initial ports
        try:
            self.view.loadFinished.connect(self._on_map_loaded)
        except Exception:
            pass
        content.addWidget(self.view, 10)
        
        # setup AIS queue polling timer
        # start a timer that will poll the AIS queue and forward updates to JS
        self._queue_timer = QTimer(self)
        self._queue_timer.setInterval(200)
        self._queue_timer.timeout.connect(self._drain_queue)
        try:
            if self._ais_queue is not None:
                self._queue_timer.start()
        except Exception:
            pass


        # simple right column with buttons
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(8, 8, 8, 8)

        self.open_manager_btn = QPushButton("Manager")
        self.open_manager_btn.clicked.connect(self.open_manager_dialog)
        right_layout.addWidget(self.open_manager_btn)

        # button to open the advanced settings dashboard
        self.open_advanced_btn = QPushButton("Impostazioni Avanzate")
        self.open_advanced_btn.clicked.connect(
            lambda: self.open_dashboard_embedded(
                'static/dashboard/impostazioni_avanzate.html',
                title='Impostazioni Avanzate',
                size=(1500, 900),
            )
        )
        right_layout.addWidget(self.open_advanced_btn)

        right_layout.addStretch()
        
        content.addWidget(right_col, 0)

        layout.addLayout(content)

        # timer already created above

    def open_manager_dialog(self):
        """Open or create the Manager dialog."""
        if getattr(self, 'manager_dialog', None) is None:
            self.manager_dialog = ManagerDialog(self)
        self.manager_dialog.show()

    def _on_map_loaded(self, ok: bool):
        if not ok:
            return
        # load ports from API if available
        try:
            self._load_ports_to_map()
        except Exception:
            pass

    def _load_ports_to_map(self):
        if get_json is None:
            return
        try:
            items = get_json('porto/lista')
            import json as _json
            # ensure serializable
            js = f"loadPorts({_json.dumps(items)})"
            self.view.page().runJavaScript(js)
        except Exception:
            pass

    def _drain_queue(self):
        """Drain AIS queue and forward updates to the embedded map JS.

        Each item put on the queue is expected to be a dict (the deserialized
        Kafka message value). We call the global JS `updateShip(obj)` function
        in the page context with the object.
        """
        q = self._ais_queue
        if q is None:
            return
        try:
            import json as _json
            while not q.empty():
                try:
                    item = q.get_nowait()
                except Exception:
                    break
                try:
                    # log the item for debug
                    try:
                        js = f"window.updateShip({_json.dumps(item)})"
                        try:
                            self.view.page().runJavaScript(js)
                        except Exception:
                            # ignore JS errors silently
                            pass
                    except Exception:
                        pass
                except Exception:
                    logger.exception("Error while draining AIS queue")
        except Exception:
            pass

    def refresh_ports_on_map(self, items):
        """Public helper to push a list of port dicts to the web map.

        `items` should be a list of objects with at least `nome`, `lat`, `lon`, and optional `id`.
        This is used by the PortiPanel after adds/edits.
        """
        try:
            import json as _json
            js = f"loadPorts({_json.dumps(items)})"
            self.view.page().runJavaScript(js)
        except Exception:
            pass

    def open_dashboard_embedded(self, page_relative: str, query: dict = None, title: str = None, size=(1500,900)):
        """Open or reuse an embedded dashboard dialog inside the application.

        This uses the same profile as the main view so cookies and session are shared.
        """
        try:
            from PyQt5.QtWidgets import QDialog, QVBoxLayout
            from PyQt5.QtCore import QUrl

            # support fragment/hash in page_relative
            frag = None
            if '#' in page_relative:
                page_path, frag = page_relative.split('#', 1)
            else:
                page_path = page_relative

            base = Path(__file__).parent / page_path
            base = str(base.resolve())

            qstr = None
            if query:
                from urllib.parse import urlencode
                qstr = urlencode({k: str(v) for k, v in query.items()})

            url = QUrl.fromLocalFile(base)
            if frag:
                frag_to_set = frag
                if qstr:
                    if '?' in frag_to_set:
                        frag_to_set = f"{frag_to_set}&{qstr}"
                    else:
                        frag_to_set = f"{frag_to_set}?{qstr}"
                url.setFragment(frag_to_set)
            else:
                if qstr:
                    url.setQuery(qstr)

            # always create a new dialog (do not reuse) so multiple dashboards stack
            dlg = QDialog(self)
            dlg.setWindowTitle(title or 'Dashboard')
            dlg.resize(size[0], size[1])
            layout = QVBoxLayout(dlg)
            view = QWebEngineView(dlg)
            # share profile with main view
            try:
                page = QWebEnginePage(self.view.page().profile(), view)
                view.setPage(page)
            except Exception:
                pass
            layout.addWidget(view)
            dlg.setModal(False)
            try:
                from PyQt5.QtCore import Qt
                dlg.setWindowModality(Qt.NonModal)
            except Exception:
                pass
            dlg.show()

            # retain reference to avoid GC and to allow multiple dialogs
            try:
                lst = getattr(self, '_dashboard_dialogs', None)
                if lst is None:
                    self._dashboard_dialogs = [dlg]
                else:
                    lst.append(dlg)
            except Exception:
                pass

            # keep ref to view for potential future use
            try:
                lstv = getattr(self, '_dashboard_views', None)
                if lstv is None:
                    self._dashboard_views = [view]
                else:
                    lstv.append(view)
            except Exception:
                pass

            view.load(url)
        except Exception:
            pass
