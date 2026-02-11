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
    QComboBox,
    QHeaderView,
    QAbstractItemView,
)

# Import get_json and post_json with fallback like other modules
try:
    from ApiClient import get_json, post_json
except Exception:
    try:
        from project.ApiClient import get_json, post_json
    except Exception:
        get_json = None
        post_json = None

import json


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
                data = get_json(f'corsa/{corsa_id}?include=tratta')
                if not isinstance(data, dict):
                    raise ValueError('Risposta non valida')

                # Adapt to new structure
                nom_corsa = data.get('nome', '')
                tratta_node = data.get('tratta')
                if isinstance(tratta_node, dict):
                    tratta = tratta_node.get('nome', '') 
                else:
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

                info_text = f'Corsa: {nom_corsa}  Tratta: {tratta}  Data: {date_str}  Orario: {time_str}  Previsione Biglietti: {pax}'
            except Exception as e:
                info_text = f'Per la corsa selezionata non sono presenti percorsi sul database: {e}'

        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # vascello filter: show all by default
        self._current_corsa_id = corsa_id
        filter_row = QHBoxLayout()
        filter_row.addStretch()
        self.vascello_combo = QComboBox(self)
        self.vascello_combo.setToolTip('Seleziona vascello per filtrare i percorsi')
        self.vascello_combo.addItem('Tutti', None)
        self.vascello_combo.currentIndexChanged.connect(self._on_vascello_changed)
        filter_row.addWidget(QLabel('Vascello:'))
        filter_row.addWidget(self.vascello_combo)
        layout.addLayout(filter_row)

        # populate vascello combo with full list from API (show names, store ids)
        try:
            self._load_vascelli_list()
        except Exception:
            pass

        # table of percorsi: checkbox, tempo, consumo, comfort, vascello and delete button
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            'Mostra',
            'Tempo Percorrenza',
            'Consumo',
            'Comfort',
            'Vascello',
            'Elimina',
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # make cells non-editable
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

        # flag to suppress itemChanged while populating
        self._suppress_item_changed = False
        self.table.itemChanged.connect(self._on_item_changed)

        # ensure parent has an in-memory set to persist visible routes during app runtime
        try:
            if parent is not None:
                if not hasattr(parent, '_visible_routes'):
                    parent._visible_routes = set()
            else:
                # fallback: keep a dialog-local set for sessions without parent
                if not hasattr(self, '_visible_routes'):
                    self._visible_routes = set()
        except Exception:
            pass

        # label shown when no percorsi are available
        self.empty_label = QLabel('')
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

        # try to load percorsi for this corsa
        if corsa_id is not None and get_json is not None:
            try:
                self.load_percorsi(corsa_id) 
            except Exception:
                # silent fallback; show message
                self.table.setRowCount(0)
                self.table.show()
                self.empty_label.setText('Impossibile caricare i percorsi per la corsa selezionata.')
                self.empty_label.show()
        else:
            # if API not available or no id, leave table empty 
            if corsa_id is None:
                self.table.setRowCount(0)
                self.table.show()
                self.empty_label.setText('ID corsa non fornito.')
                self.empty_label.show()
            elif get_json is None:
                self.table.setRowCount(0) 
                self.table.show()
                self.empty_label.setText('Client API non disponibile per recuperare percorsi.')
                self.empty_label.show()

        btn_row = QHBoxLayout()
        ok = QPushButton('Chiudi')
        ok.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

    def load_percorsi(self, corsa_id, vascello_id=None):
        """Carica i percorsi da `/percorso/by_corsa/{corsa_id}` e popola la tabella."""
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per recuperare percorsi')
            return
        # support optional vascello_id query parameter

        path = f'percorso/by_corsa/{corsa_id}'
        if vascello_id is not None:
            path = f"{path}?vascello_id={vascello_id}"

        # call API and handle error cases (404 may return a {'detail':...} payload)
        try:
            data = get_json(path)
        except Exception:
            # treat API failures as "no percorsi" for the selected filter
            self.table.setRowCount(0)
            self.table.show()
            self.empty_label.setText('Nessun percorso presente sul database per la corsa selezionata')
            self.empty_label.show()
            return

        if not isinstance(data, dict):
            raise ValueError('Risposta percorsi non valida')

        # some endpoints may return 404 with a {'detail': ...} body
        if 'detail' in data and not data.get('percorsi'):
            self.table.setRowCount(0)
            self.table.show() 
            self.empty_label.setText('Nessun percorso presente sul database per la corsa selezionata')
            self.empty_label.show()
            return

        percorsi = data.get('percorsi') or []

        # DEBUG
        # print(f'PercorsiDialog: loaded {len(percorsi)} percorsi for \ncorsa: {corsa_id}\nvascello filter: {vascello_id}')
        # for p in percorsi:
        #     print(p.get('id'), p.get('vascello_id'))
        
        if not percorsi:
            print('PercorsiDialog: no percorsi found for vascello filter', vascello_id)
            # no percorsi — show message and hide table
            self.table.setRowCount(0)
            self.table.show() 
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

            # determine vascello name for this percorso
            vname = ''
            try:
                # prefer explicit name fields if present
                if isinstance(p, dict):
                    if p.get('vascello_nome'):
                        vname = str(p.get('vascello_nome'))
                    else:
                        vid = p.get('vascello_id')
                        if vid is not None:
                            vname = self._vascello_map.get(str(vid), str(vid))
                        else:
                            # try nested vascello object
                            vobj = p.get('vascello')
                            if isinstance(vobj, dict):
                                vname = vobj.get('nome') or vobj.get('name') or ''
            except Exception:
                vname = ''

            for it in (it_tempo, it_consumo, it_comfort):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            it_vascello = QTableWidgetItem(str(vname))
            it_vascello.setFlags(it_vascello.flags() & ~Qt.ItemIsEditable)

            # suppress itemChanged while inserting
            self._suppress_item_changed = True
            self.table.setItem(row, 0, it_check)
            self.table.setItem(row, 1, it_tempo)
            self.table.setItem(row, 2, it_consumo)
            self.table.setItem(row, 3, it_comfort)
            self.table.setItem(row, 4, it_vascello)
            # delete button in last column
            try:
                btn = QPushButton('🗑')
                btn.setToolTip('Elimina percorso')
                # store route id on button for handler
                rid = p.get('id') if isinstance(p, dict) else None
                btn.setProperty('route_id', str(rid) if rid is not None else '')
                btn.clicked.connect(self._on_delete_clicked)
                self.table.setCellWidget(row, 5, btn)
            except Exception:
                pass
            self._suppress_item_changed = False
        

        # restore checked state from in-memory parent._visible_routes (no disk persistence)
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, '_visible_routes'):
                visible = parent._visible_routes
            else:
                visible = getattr(self, '_visible_routes', set())
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
                # if marked visible in-memory, set checkbox and draw route
                if str(rid) in visible:
                    chk = self.table.item(row_idx, 0)
                    if chk:
                        self._suppress_item_changed = True
                        chk.setCheckState(Qt.Checked)
                        self._suppress_item_changed = False
                        try:
                            js = f"window.routesManager.drawRoute({json.dumps(route_obj)})"
                            self._run_js(js)
                        except Exception:
                            pass
                # ensure delete buttons reflect row indices (no-op here since buttons stored per-row)
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

    def _load_vascelli_list(self):
        """Load the full list of vascelli from API and populate the combo with names."""
        if get_json is None:
            return
        try:
            vascello_list = get_json('vascello/lista') or []
        except Exception:
            vascello_list = []

        try:
            # preserve current selection
            cur = self.vascello_combo.currentData()
            self.vascello_combo.blockSignals(True)
            self.vascello_combo.clear()
            self.vascello_combo.addItem('Tutti', None)
            # keep a mapping id -> name for lookup when populating table
            self._vascello_map = {}
            for v in vascello_list:
                if isinstance(v, dict):
                    vid = str(v.get('id', ''))
                    name = v.get('nome') or v.get('name') or vid
                else:
                    vid = str(v)
                    name = vid
                self.vascello_combo.addItem(str(name), vid)
                self._vascello_map[vid] = str(name)
            # restore previous selection if still present
            if cur is not None:
                idx = self.vascello_combo.findData(cur)
                if idx != -1:
                    self.vascello_combo.setCurrentIndex(idx)
            self.vascello_combo.blockSignals(False)
        except Exception:
            pass

    def _on_delete_clicked(self):
        """Handle delete button clicked: confirm, call API, remove row and route from map."""
        try:
            sender = self.sender()
            if sender is None:
                return
            rid = sender.property('route_id') or ''
            if not rid:
                QMessageBox.warning(self, 'Errore', 'ID percorso non disponibile')
                return
            # confirmation
            resp = QMessageBox.question(self, 'Conferma eliminazione', f'Eliminare il percorso selezionato?', QMessageBox.Yes | QMessageBox.No)
            if resp != QMessageBox.Yes:
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client API non disponibile per eliminazione')
                return
            # call API
            try:
                post_json('percorso/elimina', payload={'id': rid})
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Eliminazione fallita: {e}')
                return
            # remove any drawn route on map
            try:
                self._run_js(f"window.routesManager.removeRoute({json.dumps(rid)})")
            except Exception:
                pass
            # remove row from table (find by matching UserRole id)
            try:
                for row_idx in range(self.table.rowCount()):
                    it = self.table.item(row_idx, 0)
                    if it is None:
                        continue
                    route_obj = it.data(Qt.UserRole)
                    if not isinstance(route_obj, dict):
                        continue
                    if str(route_obj.get('id')) == str(rid):
                        self.table.removeRow(row_idx)
                        break
            except Exception:
                pass
            # remove from visible set if present
            try:
                parent = self.parent()
                if parent is not None and hasattr(parent, '_visible_routes'):
                    parent._visible_routes.discard(str(rid))
                else:
                    getattr(self, '_visible_routes', set()).discard(str(rid))
            except Exception:
                pass
            QMessageBox.information(self, 'Successo', 'Percorso eliminato')
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

    def _on_vascello_changed(self, index:int):
        """Handle vascello filter changes and reload percorsi accordingly."""
        try:
            vid = self.vascello_combo.currentData()
            # reload percorsi for current corsa id with optional vascello_id
            try:
                self.load_percorsi(self._current_corsa_id, vascello_id=vid)
            except Exception:
                pass
        except Exception:
            pass

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
                rid = route_obj.get('id')
                if checked:
                    # draw route
                    js = f"window.routesManager.drawRoute({json.dumps(route_obj)})"
                    self._run_js(js)
                    # store selection in-memory on parent (or locally if no parent)
                    parent = self.parent()
                    try:
                        if parent is not None:
                            parent._visible_routes.add(str(rid))
                        else:
                            self._visible_routes.add(str(rid))
                    except Exception:
                        pass
                else:
                    if rid is not None:
                        js = f"window.routesManager.removeRoute({json.dumps(rid)})"
                        self._run_js(js)
                        parent = self.parent()
                        try:
                            if parent is not None:
                                parent._visible_routes.discard(str(rid))
                            else:
                                self._visible_routes.discard(str(rid))
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass
