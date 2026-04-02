import json
import time
from pathlib import Path

from PyQt5.QtCore import QUrl, QTimer, QVariant, QObject, pyqtSlot
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings
from PyQt5.QtWebEngineCore import QWebEngineUrlRequestInterceptor
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QDialog,
)
from PyQt5.QtGui import QIcon

# ──────────────────────────────────────────────────────────────────────────────
# Optional dependencies (graceful fallback when not available)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from panels.ManagerDialog import ManagerDialog
except Exception:
    print("[main_window] panels.ManagerDialog not available", flush=True)
    ManagerDialog = None

try:
    from ApiClient import get_json
except Exception:
    print("[main_window] ApiClient.get_json not available", flush=True)
    get_json = None


# ──────────────────────────────────────────────────────────────────────────────
# TileRefererInterceptor
# ──────────────────────────────────────────────────────────────────────────────
class TileRefererInterceptor(QWebEngineUrlRequestInterceptor):
    """Inject Referer and User-Agent headers on every OSM / OpenSeaMap tile
    request so the tile servers don't return 403r ("Referer is required").

    QtWebEngine strips the Referer header when the page is loaded from a
    file:// URL (which is always the case here).  The interceptor runs at the
    network layer and patches the headers before they leave the process.
    """

    # Domains that require a Referer header
    TILE_DOMAINS = (
        b"tile.openstreetmap.org",
        b"tiles.openseamap.org",
    )

    # A stable, identifying User-Agent string as required by the OSM policy
    USER_AGENT = b"NavalViewer/1.0 (+https://navalviewer.local; contact: admin@navalviewer.local)"

    # A synthetic Referer that satisfies the policy (must be a valid https URL)
    REFERER = b"https://navalviewer.local/"

    def interceptRequest(self, info):
        url_bytes = info.requestUrl().toString().encode("utf-8", errors="replace")
        if any(domain in url_bytes for domain in self.TILE_DOMAINS):
            info.setHttpHeader(b"Referer", self.REFERER)
            info.setHttpHeader(b"User-Agent", self.USER_AGENT)


# ──────────────────────────────────────────────────────────────────────────────
# _WebBridge  –  QObject exposed to the web page via QWebChannel
# ──────────────────────────────────────────────────────────────────────────────
class _WebBridge(QObject):
    """Small helper that lets JavaScript call back into the Python application.

    Registered as ``window.pyMain`` inside the embedded map page.
    """

    def __init__(self, main_window: "MainWindow"):
        super().__init__()
        self._mw = main_window

    # ── route visibility ──────────────────────────────────────────────────────

    @pyqtSlot(result=bool)
    def cleanRoutes(self):
        """Clear all visible route IDs from the global state."""
        try:
            self._mw.visible_routes.clear()
            return True
        except Exception:
            return False

    @pyqtSlot(str, result=bool)
    def addRoute(self, route_id: str):
        """Add a route ID to the visible set."""
        try:
            if route_id:
                self._mw.visible_routes.add(str(route_id))
            return True
        except Exception:
            return False

    @pyqtSlot(str, result=bool)
    def removeRoute(self, route_id: str):
        """Remove a route ID from the visible set."""
        try:
            if route_id:
                self._mw.visible_routes.discard(str(route_id))
            return True
        except Exception:
            return False

    # ── dashboard ─────────────────────────────────────────────────────────────

    @pyqtSlot(str, str, str, int, int)
    def openDashboard(self, page_relative: str, query_json: str, title: str, width: int, height: int):
        """Open an embedded dashboard dialog from JavaScript."""
        try:
            query = None
            if query_json:
                try:
                    query = json.loads(query_json)
                except Exception:
                    query = None
            self._mw.open_dashboard_embedded(
                page_relative,
                query=query,
                title=title or None,
                size=(width or 1500, height or 900),
            )
        except Exception as exc:
            print(f"[WebBridge.openDashboard] {exc}", flush=True)

    # ── route details ─────────────────────────────────────────────────────────

    @pyqtSlot(str, result=QVariant)
    def getRouteDetails(self, route_id: str):
        """Fetch full route details for the given ID from the backend API."""
        try:
            if get_json is None:
                return {}
            data = get_json(f"percorso/{route_id}?include=corsa,tratta,vascello")
            if isinstance(data, dict):
                if "id" not in data and "percorso_id" in data:
                    data["id"] = data["percorso_id"]
                return data
            return {}
        except Exception as exc:
            print(f"[WebBridge.getRouteDetails] route={route_id} – {exc}", flush=True)
            return {}


# ──────────────────────────────────────────────────────────────────────────────
# PopupPage  –  handles window.open() calls from JS
# ──────────────────────────────────────────────────────────────────────────────
class _PopupPage(QWebEnginePage):
    """Custom page that turns JS ``window.open()`` calls into embedded dialogs."""

    def __init__(self, parent_window: "MainWindow", profile=None):
        if profile is not None:
            super().__init__(profile, parent_window)
        else:
            super().__init__(parent_window)
        self._parent_window = parent_window

    def createWindow(self, _type):
        try:
            dlg = QDialog(self._parent_window)
            dlg.setWindowTitle("Dashboard")
            dlg.resize(1000, 700)
            layout = QVBoxLayout(dlg)
            new_view = QWebEngineView(dlg)
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
            # keep reference alive to avoid garbage collection
            lst = getattr(self._parent_window, "_popup_dialogs", None)
            if lst is None:
                self._parent_window._popup_dialogs = [dlg]
            else:
                lst.append(dlg)
            return new_page
        except Exception:
            return super().createWindow(_type)


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Main application window.

    Responsibilities
    ----------------
    * Embed and display the Leaflet map (``static/map.html``) inside a
      ``QWebEngineView``.
    * Inject the ``TileRefererInterceptor`` so OSM tile servers receive a
      valid ``Referer`` header and do not return 403r.
    * Expose ``_WebBridge`` to JavaScript via ``QWebChannel`` as
      ``window.pyMain``.
    * Poll the AIS queue and forward ship updates to the map page.
    * Open/manage auxiliary dialogs (Manager, Impostazioni Avanzate, Gantt).
    """

    def __init__(self, queue=None):
        super().__init__()
        self.setWindowIcon(QIcon("static/icon/settings_icon.ico"))
        self.setWindowTitle("PROJECT SMART - Living Map")
        self.resize(1000, 700)

        self._ais_queue = queue

        # Public set of currently visible route IDs (string)
        self.visible_routes: set = set()

        # Reference holders to prevent garbage collection
        self._popup_dialogs: list = []
        self._dashboard_dialogs: list = []
        self._dashboard_views: list = []

        self._build_ui()
        self._setup_web_view()
        self._setup_ais_timer()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        content = QHBoxLayout()

        # ── right column ──────────────────────────────────────────────────────
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(8, 8, 8, 8)

        self.open_manager_btn = QPushButton("Manager")
        self.open_manager_btn.clicked.connect(self.open_manager_dialog)
        right_layout.addWidget(self.open_manager_btn)

        self.open_advanced_btn = QPushButton("Impostazioni Avanzate")
        self.open_advanced_btn.clicked.connect(
            lambda: self.open_dashboard_embedded(
                "static/dashboard/impostazioni_avanzate.html",
                title="Impostazioni Avanzate",
                size=(1500, 900),
            )
        )
        right_layout.addWidget(self.open_advanced_btn)

        self.open_gantt_btn = QPushButton("Gantt")
        self.open_gantt_btn.clicked.connect(
            lambda: self.open_dashboard_embedded(
                "static/gantt/gantt.html",
                query={"giorno": time.strftime("%Y-%m-%d")},
                title="Gantt",
                size=(1600, 900),
            )
        )
        right_layout.addWidget(self.open_gantt_btn)
        right_layout.addStretch()

        # The web view placeholder is filled by _setup_web_view()
        self._content_layout = content
        content.addWidget(right_col, 0)
        root.addLayout(content)

    # ── web view + interceptor ────────────────────────────────────────────────

    def _setup_web_view(self):
        """Create the QWebEngineView, attach the interceptor and webchannel."""

        self.view = QWebEngineView()

        # 1. Replace the default page with our popup-capable page
        popup_page = _PopupPage(self, self.view.page().profile())
        self.view.setPage(popup_page)

        # 2. Install the tile interceptor on the shared profile so that ALL
        #    requests (including those from popup/dashboard dialogs that share
        #    the same profile) get the correct headers.
        self._interceptor = TileRefererInterceptor()
        self.view.page().profile().setUrlRequestInterceptor(self._interceptor)

        # 3. Relax the referrer policy at the engine level as an extra measure
        settings = self.view.page().settings()
        settings.setAttribute(QWebEngineSettings.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # 4. Expose the Python bridge to JavaScript
        self._webbridge = _WebBridge(self)
        self._channel = QWebChannel(self.view.page())
        self._channel.registerObject("pyMain", self._webbridge)
        self.view.page().setWebChannel(self._channel)

        # 5. Connect load-finished signal
        self.view.loadFinished.connect(self._on_map_loaded)

        # 6. Load the map HTML
        map_path = Path(__file__).parent / "static" / "map.html"
        self.view.load(QUrl.fromLocalFile(str(map_path.resolve())))

        # 7. Insert the view into the layout (stretch factor 10 → takes all space)
        self._content_layout.insertWidget(0, self.view, 10)

    # ── AIS queue polling ─────────────────────────────────────────────────────

    def _setup_ais_timer(self):
        self._queue_timer = QTimer(self)
        self._queue_timer.setInterval(200)  # ms
        self._queue_timer.timeout.connect(self._drain_queue)
        if self._ais_queue is not None:
            self._queue_timer.start()

    # ── slots / helpers ───────────────────────────────────────────────────────

    def open_manager_dialog(self):
        """Open (or bring to front) the Manager dialog."""
        if ManagerDialog is None:
            return
        if getattr(self, "manager_dialog", None) is None:
            self.manager_dialog = ManagerDialog(self)
        self.manager_dialog.show()
        self.manager_dialog.raise_()

    def _on_map_loaded(self, ok: bool):
        if not ok:
            print("[main_window] map.html failed to load", flush=True)
            return
        try:
            self._load_ports_to_map()
        except Exception as exc:
            print(f"[main_window] _load_ports_to_map: {exc}", flush=True)

    def _load_ports_to_map(self):
        if get_json is None:
            return
        try:
            items = get_json("porto/lista")
            js = f"loadPorts({json.dumps(items)})"
            self.view.page().runJavaScript(js)
        except Exception as exc:
            print(f"[main_window] _load_ports_to_map error: {exc}", flush=True)

    def _drain_queue(self):
        """Drain the AIS queue and forward updates to the map page in batches."""
        import queue as _queue_mod

        q = self._ais_queue
        if q is None:
            return

        batch = []
        MAX_BATCH = 100

        for _ in range(MAX_BATCH):
            try:
                batch.append(q.get_nowait())
            except _queue_mod.Empty:
                break
            except Exception:
                break

        if not batch:
            return

        try:
            js = (
                f"if(typeof window.updateShips === 'function'){{"
                f"  window.updateShips({json.dumps(batch)});"
                f"}} else if(typeof window.updateShip === 'function'){{"
                f"  {json.dumps(batch)}.forEach(window.updateShip);"
                f"}}"
            )
            self.view.page().runJavaScript(js)
        except Exception as exc:
            print(f"[main_window] _drain_queue JS error: {exc}", flush=True)

    def refresh_ports_on_map(self, items: list):
        """Push a fresh list of port dicts to the web map.

        Called externally (e.g. from PortiPanel) after add/edit operations.
        ``items`` must be a list of dicts with at least ``nome``, ``lat``, ``lon``.
        """
        try:
            js = f"loadPorts({json.dumps(items)})"
            self.view.page().runJavaScript(js)
        except Exception as exc:
            print(f"[main_window] refresh_ports_on_map error: {exc}", flush=True)

    def open_dashboard_embedded(
        self,
        page_relative: str,
        query: dict = None,
        title: str = None,
        size: tuple = (1500, 900),
    ):
        """Open an auxiliary HTML page as a non-modal embedded dialog.

        The new view shares the same profile as the main view so cookies and
        session data are inherited.  Multiple calls stack independent dialogs.
        """
        try:
            # Handle optional fragment (#...)
            frag = None
            if "#" in page_relative:
                page_path, frag = page_relative.split("#", 1)
            else:
                page_path = page_relative

            base = str((Path(__file__).parent / page_path).resolve())
            url = QUrl.fromLocalFile(base)

            if query:
                from urllib.parse import urlencode
                qstr = urlencode({k: str(v) for k, v in query.items()})
                if frag:
                    url.setFragment(f"{frag}?{qstr}" if "?" not in frag else f"{frag}&{qstr}")
                else:
                    url.setQuery(qstr)
            elif frag:
                url.setFragment(frag)

            dlg = QDialog(self)
            dlg.setWindowTitle(title or "Dashboard")
            dlg.resize(size[0], size[1])
            layout = QVBoxLayout(dlg)

            view = QWebEngineView(dlg)
            # Share the profile (and therefore the interceptor) with the main view
            page = QWebEnginePage(self.view.page().profile(), view)
            view.setPage(page)
            layout.addWidget(view)

            try:
                from PyQt5.QtCore import Qt
                dlg.setWindowModality(Qt.NonModal)
            except Exception:
                pass

            dlg.show()
            view.load(url)

            # Keep references alive
            self._dashboard_dialogs.append(dlg)
            self._dashboard_views.append(view)

        except Exception as exc:
            print(f"[main_window] open_dashboard_embedded error: {exc}", flush=True)