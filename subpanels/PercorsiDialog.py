from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
import os
import json

# Import get_json with fallback like other modules
try:
    from ApiClient import get_json
except Exception:
    try:
        from project.ApiClient import get_json
    except Exception:
        get_json = None


# persistence helpers for visible routes
def _get_visible_routes_path():
    try:
        # place file next to project root (one level up from this module)
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, 'visible_routes.json')


def _load_visible_routes():
    path = _get_visible_routes_path()
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(str(x) for x in data)
    except Exception:
        pass
    return set()


def _save_visible_routes(s):
    path = _get_visible_routes_path()
    try:
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(list(s), f)
        try:
            os.replace(tmp, path)
        except Exception:
            os.rename(tmp, path)
    except Exception:
        pass


class PercorsiDialog(QDialog):
    """Dialog che mostra informazioni principali di una corsa.

    Mostra un `QLabel` con: Tratta, Data, Orario, Previsione Biglietti.
    I dettagli vengono recuperati da `/corsa/{corsa_id}`.
    """
    def __init__(self, parent=None, corsa=None):
        super().__init__(parent)
        self.setWindowTitle('Dettagli Percorsi')
        # set default dialog size
        self.resize(800,600)
        # allow minimize and maximize buttons
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        # main layout
        layout = QVBoxLayout(self)

        # determine corsa id (corsa may be dict or plain id)
        corsa_id = None
        if isinstance(corsa, dict):
            corsa_id = corsa.get('id')
        elif isinstance(corsa, str):
            corsa_id = corsa
        elif corsa is not None:
            try:
                # try to coerce from other objects
                corsa_id = str(corsa)
            except Exception:
                corsa_id = None

        info_text = 'Informazioni corsa non disponibili.'

        if corsa_id is None:
            info_text = 'ID corsa non fornito.'
        elif get_json is None:
            info_text = f'Client API non disponibile per recuperare corsa {corsa_id}.'
        else:
            try:
                data = get_json(f'corsa/{corsa_id}')
                if not isinstance(data, dict):
                    raise ValueError('Risposta non valida')

                tratta = data.get('tratta_nome', '')
                orario = data.get('orario_partenza_schedulato', '')
                previsione = data.get('previsione') or {}
                pax = previsione.get('passeggeri_stimati') if isinstance(previsione, dict) else ''

                # parse datetime to separate date and time if possible
                date_str = ''
                time_str = ''
                if orario:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(str(orario))
                        date_str = dt.strftime('%d/%m/%Y')
                        time_str = dt.strftime('%H:%M')
                    except Exception:
                        # fallback: attempt simple split on 'T' or space
                        if 'T' in str(orario):
                            parts = str(orario).split('T')
                        else:
                            parts = str(orario).split(' ')
                        if len(parts) >= 2:
                            date_str = parts[0]
                            time_str = parts[1][:5]
                        else:
                            date_str = str(orario)

                info_text = f'Tratta: {tratta}  Data: {date_str}  Orario: {time_str}  Previsione Biglietti: {pax}'
            except Exception as e:
                info_text = f'Per la corsa selezionata non sono presenti percorsi sul database: {e}'

        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # table of percorsi: checkbox, tempo, consumo and comfort columns
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels([
            'Mostra',
            'Tempo Percorrenza',
            'Consumo',
            'Comfort',
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # make cells non-editable
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        # flag to suppress itemChanged while populating
        self._suppress_item_changed = False
        self.table.itemChanged.connect(self._on_item_changed)

        # ensure parent has a visible routes set to persist selections across dialog instances
        try:
            if parent is not None:
                if not hasattr(parent, '_visible_routes'):
                    # load persisted visible routes from disk
                    parent._visible_routes = _load_visible_routes()
        except Exception:
            pass

        # label shown when no percorsi are available
        self.empty_label = QLabel('')
        self.empty_label.setWordWrap(True)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        # try to load percorsi for this corsa
        if corsa_id is not None and get_json is not None:
            try:
                self.load_percorsi(corsa_id)
            except Exception:
                # silent fallback; show message
                self.table.setRowCount(0)
                self.table.hide()
                self.empty_label.setText('Impossibile caricare i percorsi per la corsa selezionata.')
                self.empty_label.show()
        else:
            # if API not available or no id, leave table empty
            if corsa_id is None:
                self.table.hide()
                self.empty_label.setText('ID corsa non fornito.')
                self.empty_label.show()
            elif get_json is None:
                self.table.hide()
                self.empty_label.setText('Client API non disponibile per recuperare percorsi.')
                self.empty_label.show()

        btn_row = QHBoxLayout()
        ok = QPushButton('Chiudi')
        ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def load_percorsi(self, corsa_id):
        """Carica i percorsi da `/percorso/by_corsa/{corsa_id}` e popola la tabella."""
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per recuperare percorsi')
            return
        data = get_json(f'percorso/by_corsa/{corsa_id}')
        if not isinstance(data, dict):
            raise ValueError('Risposta percorsi non valida')
        percorsi = data.get('percorsi') or []
        if not percorsi:
            # no percorsi — show message and hide table
            self.table.setRowCount(0)
            self.table.hide()
            self.empty_label.setText('Nessun percorso presente sul database per la corsa selezionata')
            self.empty_label.show()
            return
        else:
            self.empty_label.hide()
            self.table.show()
        # populate table
        self.table.setRowCount(0)
        for p in percorsi:
            row = self.table.rowCount()
            self.table.insertRow(row)
            tempo = p.get('tempo_percorrenza', '')
            consumo = p.get('consumo', '')
            comfort = p.get('comfort', '')

            # checkbox item in first column; store full percorso object on it via UserRole
            it_check = QTableWidgetItem()
            it_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it_check.setCheckState(Qt.Unchecked)
            it_check.setData(Qt.UserRole, p)

            it_tempo = QTableWidgetItem(str(tempo))
            it_consumo = QTableWidgetItem(str(consumo))
            it_comfort = QTableWidgetItem(str(comfort))

            for it in (it_tempo, it_consumo, it_comfort):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            # suppress itemChanged while inserting
            self._suppress_item_changed = True
            self.table.setItem(row, 0, it_check)
            self.table.setItem(row, 1, it_tempo)
            self.table.setItem(row, 2, it_consumo)
            self.table.setItem(row, 3, it_comfort)
            self._suppress_item_changed = False

        # after populating, restore checked state from parent and draw any persisted routes
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, '_visible_routes'):
                visible = parent._visible_routes
                import json as _json
                for row_idx in range(self.table.rowCount()):
                    id_item = self.table.item(row_idx, 0)
                    if id_item is None:
                        continue
                    route_obj = id_item.data(Qt.UserRole)
                    if not isinstance(route_obj, dict):
                        continue
                    rid = route_obj.get('id')
                    if rid is None:
                        continue
                    # if persisted visible, set checkbox and draw route
                    if str(rid) in visible:
                        chk = self.table.item(row_idx, 0)
                        if chk:
                            # set without triggering handler
                            self._suppress_item_changed = True
                            chk.setCheckState(Qt.Checked)
                            self._suppress_item_changed = False
                            try:
                                js = f"window.routesManager.drawRoute({_json.dumps(route_obj)})"
                                self._run_js(js)
                            except Exception:
                                pass
        except Exception:
            pass

        # resize columns
        self.table.resizeColumnsToContents()

        # quick diagnostic: check whether routesManager is available in the web view
        try:
            def _cb(res):
                print('PercorsiDialog: routesManager present?', res)
            self._run_js("Boolean(window.routesManager && window.routesManager.drawRoute)", _cb)
        except Exception:
            pass

    def _run_js(self, js, callback=None):
        """Helper to run JavaScript in the main window web view if available."""
        try:
            parent = self.parent()
            if parent is None:
                print('PercorsiDialog._run_js: no parent')
                # try to find a view from top-level widgets
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is None:
                    return
                view = None
                for w in app.topLevelWidgets():
                    try:
                        v = getattr(w, 'view', None)
                        if v is not None:
                            view = v
                            break
                    except Exception:
                        continue
                if view is None:
                    return
            else:
                view = getattr(parent, 'view', None)
                if view is None:
                    # fallback to searching top-level widgets
                    from PyQt5.QtWidgets import QApplication
                    app = QApplication.instance()
                    if app is not None:
                        for w in app.topLevelWidgets():
                            try:
                                v = getattr(w, 'view', None)
                                if v is not None:
                                    view = v
                                    break
                            except Exception:
                                continue
                if view is None:
                    print('PercorsiDialog._run_js: no QWebEngineView found')
                    return
            # print('PercorsiDialog._run_js executing JS:', js)
            if callback is None:
                view.page().runJavaScript(js)
            else:
                view.page().runJavaScript(js, callback)
        except Exception:
            import traceback
            traceback.print_exc()

    def _on_item_changed(self, item):
        """Handle checkbox toggles in the 'Mostra' column to show/hide routes on the map."""
        if self._suppress_item_changed:
            return
        try:
            col = item.column()
            # Mostra column is 0
            if col != 0:
                return
            row = item.row()
            checked = (item.checkState() == Qt.Checked)
            route_obj = item.data(Qt.UserRole)
            if not isinstance(route_obj, dict):
                return
            # use JSON serialization for safe JS passing
            try:
                import json as _json
                rid = route_obj.get('id')
                if checked:
                    # draw route
                    js = f"window.routesManager.drawRoute({_json.dumps(route_obj)})"
                    # print('PercorsiDialog: drawing route', rid)
                    self._run_js(js)
                    # persist selection in parent set
                    parent = self.parent()
                    if parent is not None:
                        try:
                                parent._visible_routes.add(str(rid))
                                # save to disk
                                _save_visible_routes(parent._visible_routes)
                        except Exception:
                            pass
                else:
                    if rid is not None:
                        js = f"window.routesManager.removeRoute({_json.dumps(rid)})"
                        # print('PercorsiDialog: removing route', rid)
                        self._run_js(js)
                        parent = self.parent()
                        if parent is not None:
                            try:
                                parent._visible_routes.discard(str(rid))
                                # save to disk
                                _save_visible_routes(parent._visible_routes)
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass
