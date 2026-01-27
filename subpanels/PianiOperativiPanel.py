from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QSizePolicy,
    QGroupBox,
    QDialog,
    QFormLayout,
    QDateEdit,
    QComboBox,
    QLabel,
)

try:
    from ApiClient import get_json, post_json
except Exception:
    try:
        from project.ApiClient import get_json, post_json
    except Exception:
        get_json = None
        post_json = None

# simple in-memory caches to avoid repeated API calls
_vascello_name_cache = {}
_corsa_name_cache = {}
_percorso_cache = {}


def get_vascello_name(vascello_id):
    """Return a human-friendly vascello name for given id (falls back to id)."""
    if not vascello_id:
        return ''
    vid = str(vascello_id)
    if vid in _vascello_name_cache:
        return _vascello_name_cache[vid]
    if get_json is None:
        _vascello_name_cache[vid] = vid
        return vid
    try:
        resp = get_json(f'vascello/{vid}')
        if isinstance(resp, dict):
            name = resp.get('nome') or resp.get('name') or vid
        else:
            name = vid
    except Exception:
        name = vid
    _vascello_name_cache[vid] = str(name)
    return str(name)


def get_corsa_name_or_from_percorso(item_id):
    """Resolve a corsa name from either a corsa id or a percorso id.

    Attempts `/corsa/{id}` first; if no name, tries `/percorso/{id}` to
    obtain a `corsa_id` and then fetch the corsa.
    Falls back to the provided id on error.
    """
    if not item_id:
        return ''
    iid = str(item_id)
    if iid in _corsa_name_cache:
        return _corsa_name_cache[iid]
    if get_json is None:
        _corsa_name_cache[iid] = iid
        return iid
    # try corsa endpoint
    try:
        resp = get_json(f'corsa/{iid}')
        if isinstance(resp, dict):
            name = resp.get('nome') or resp.get('name')
            if name:
                _corsa_name_cache[iid] = str(name)
                return str(name)
    except Exception:
        pass
    # try percorso endpoint and extract corsa_id
    try:
        p = get_json(f'percorso/{iid}')
        if isinstance(p, dict):
            # cache percorso for potential later use
            _percorso_cache[iid] = p
            corsa_id = p.get('corsa_id')
            if corsa_id:
                try:
                    c = get_json(f'corsa/{corsa_id}')
                    if isinstance(c, dict):
                        name = c.get('nome') or c.get('name') or str(corsa_id)
                        _corsa_name_cache[iid] = str(name)
                        _corsa_name_cache[str(corsa_id)] = str(name)
                        return str(name)
                except Exception:
                    pass
    except Exception:
        pass
    # fallback
    _corsa_name_cache[iid] = iid
    return iid

def _format_date(s: str) -> str:
    if not s:
        return ''
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(s))
        return dt.strftime('%d/%m/%Y')
    except Exception:
        return str(s)
        
class PianiOperativiPanel(QWidget):
    """Panel che mostra la lista dei piani operativi da `/piano/lista`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # top row: date selector
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel('Piani Operativi per il giorno:'))
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        from PyQt5.QtCore import QDate
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self._on_date_changed)
        # slightly increase width for easier picking
        try:
            self.date_filter.setFixedWidth(140)
        except Exception:
            pass
        top_row.addWidget(self.date_filter)
        top_row.addStretch()
        layout.addLayout(top_row)

        # table columns: Data, Stato, Profitto Stimato, Robustezza, ID(hidden)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            'Data',
            'Stato',
            'Profitto Stimato',
            'Robustezza',
            'ID',
        ])
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)

        # assemble main content with right-side grouped controls
        content_row = QHBoxLayout()
        content_row.addWidget(self.table)

        right_panel = QVBoxLayout()

        # Parametri group: Aggiorna, Aggiungi, Modifica
        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)

        self.modify_btn = QPushButton('Modifica')
        self.modify_btn.clicked.connect(self.open_modify_dialog)
        self.modify_btn.setEnabled(False)

        param_group = QGroupBox('Parametri')
        param_layout = QVBoxLayout()
        param_layout.addWidget(self.refresh_btn)
        param_layout.addWidget(self.add_btn)
        param_layout.addWidget(self.modify_btn)
        param_group.setLayout(param_layout)
        right_panel.addWidget(param_group)

        # Servizi group: Dettagli Piano
        self.details_btn = QPushButton('Dettagli Piano')
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self.open_details_dialog)

        serv_group = QGroupBox('Servizi')
        serv_layout = QVBoxLayout()
        serv_layout.addWidget(self.details_btn)
        serv_group.setLayout(serv_layout)
        right_panel.addWidget(serv_group)

        right_panel.addStretch()
        content_row.addLayout(right_panel)
        layout.addLayout(content_row)

        # load initial data for current date
        self.load_data()

    def _on_date_changed(self, qdate):
        # reload list when the selected date changes
        try:
            self.load_data()
        except Exception:
            pass

    def load_data(self):
        # use selected date from date_filter if available
        try:
            d = self.date_filter.date()
            date_str = d.toString('yyyy-MM-dd')
            # RFC-like value with midnight UTC
            query_date = f"{date_str}T00:00:00.000Z"
        except Exception:
            query_date = None

        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            path = 'piano/lista'
            if query_date:
                path = f"piano/lista?data_riferimento={query_date}"
            data = get_json(path)
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare piani: {e}')

        try:
            # connect selection change to enable/disable buttons
            self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            pid = str(item.get('id', ''))
            data_raw = item.get('data_riferimento')
            data_text = _format_date(data_raw)
            stato = str(item.get('stato', ''))
            profitto = item.get('kpi_profitto_stimato')
            profitto_text = '' if profitto is None else str(profitto)
            robustezza = item.get('kpi_robustezza')
            robustezza_text = '' if robustezza is None else str(robustezza)

            it_data = QTableWidgetItem(data_text)
            it_stato = QTableWidgetItem(stato)
            it_profitto = QTableWidgetItem(profitto_text)
            it_rob = QTableWidgetItem(robustezza_text)
            it_id = QTableWidgetItem(pid)
            it_id.setData(Qt.UserRole, item)

            for it in (it_data, it_stato, it_profitto, it_rob, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_data)
            self.table.setItem(row, 1, it_stato)
            self.table.setItem(row, 2, it_profitto)
            self.table.setItem(row, 3, it_rob)
            self.table.setItem(row, 4, it_id)

        self.table.resizeColumnsToContents()

    def open_add_dialog(self):
        dlg = AddPianoDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        payload = dlg.get_payload()
        if payload is None:
            QMessageBox.warning(self, 'Errore', 'Dati non validi')
            return
        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
            return
        try:
            post_json('piano/crea', payload)
            QMessageBox.information(self, 'Successo', 'Piano operativo creato')
            # reload for currently selected date
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Creazione piano fallita: {e}')

    def open_modify_dialog(self):
        QMessageBox.information(self, 'Modifica', 'Funzionalità Modifica da implementare')

    def _on_selection_changed(self, selected, deselected):
        has = self.table.selectionModel().hasSelection()
        try:
            self.modify_btn.setEnabled(bool(has))
        except Exception:
            pass
        try:
            self.details_btn.setEnabled(bool(has))
        except Exception:
            pass

    def open_details_dialog(self):
        # get selected row and piano id
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessun piano selezionato')
            return
        row = sel[0].row()
        item = self.table.item(row, 4)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        piano = item.data(Qt.UserRole) or {}
        piano_id = piano.get('id') if isinstance(piano, dict) else item.text()
        data_rif = piano.get('data_riferimento') if isinstance(piano, dict) else ''

        dlg = DettagliPianoDialog(self, piano_id=piano_id, data_riferimento=data_rif)
        dlg.exec_()


class DettagliPianoDialog(QDialog):
    def __init__(self, parent=None, piano_id=None, data_riferimento=None):
        super().__init__(parent)
        self.setWindowTitle(f"Dettagli Piano Operativo: {_format_date(data_riferimento)}")
        self.resize(800,600)
        layout = QVBoxLayout(self)

        # table for assignments (include additional percorso fields)
        self.table = QTableWidget(0, 7, self)
        self.table.setHorizontalHeaderLabels([
            'Percorso', 'Vascello', 'Stato Esecuzione', 'Virtuale',
            'Tempo Percorrenza', 'Consumo', 'Comfort'
        ])
        layout.addWidget(self.table)

        # load assignments
        self.load_assignments(piano_id)

        btn_row = QHBoxLayout()
        close_btn = QPushButton('Chiudi')
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def load_assignments(self, piano_id):
        if piano_id is None:
            return
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            path = f'assegnazione/by_piano/{piano_id}'
            data = get_json(path) or []
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare assegnazioni: {e}')
            return

        self.table.setRowCount(0)
        for a in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            percorso_id = a.get('percorso_id') or ''
            vascello_id = a.get('vascello_id') or ''
            percorso = get_corsa_name_or_from_percorso(percorso_id) if percorso_id else ''
            vascello = get_vascello_name(vascello_id) if vascello_id else ''
            stato = str(a.get('stato_esecuzione') or '')
            virtuale = str(a.get('virtuale', False))

            # default additional fields
            tempo_percorrenza = ''
            consumo = ''
            comfort = ''
            # try to fetch percorso details (use cache if available)
            try:
                pid = str(percorso_id)
                p = None
                if pid and pid in _percorso_cache:
                    p = _percorso_cache[pid]
                elif pid and get_json is not None:
                    try:
                        p = get_json(f'percorso/{pid}')
                        if isinstance(p, dict):
                            _percorso_cache[pid] = p
                    except Exception:
                        p = None
                if isinstance(p, dict):
                    tempo_percorrenza = str(p.get('tempo_percorrenza') or '')
                    consumo = str(p.get('consumo') or '')
                    comfort = str(p.get('comfort') or '')
            except Exception:
                pass

            it_per = QTableWidgetItem(percorso)
            it_vas = QTableWidgetItem(vascello)
            it_st = QTableWidgetItem(stato)
            it_vi = QTableWidgetItem(virtuale)
            it_tp = QTableWidgetItem(tempo_percorrenza)
            it_cons = QTableWidgetItem(consumo)
            it_comf = QTableWidgetItem(comfort)
            for it in (it_per, it_vas, it_st, it_vi, it_tp, it_cons, it_comf):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_per)
            self.table.setItem(row, 1, it_vas)
            self.table.setItem(row, 2, it_st)
            self.table.setItem(row, 3, it_vi)
            self.table.setItem(row, 4, it_tp)
            self.table.setItem(row, 5, it_cons)
            self.table.setItem(row, 6, it_comf)

        self.table.resizeColumnsToContents()


class AddPianoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Aggiungi Piano Operativo')
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        from PyQt5.QtCore import QDate
        self.date_edit.setDate(QDate.currentDate())

        self.assegnazione_cb = QComboBox()
        self.assegnazione_cb.addItem('Automatica')
        self.assegnazione_cb.addItem('Manuale')

        form.addRow('Data', self.date_edit)
        form.addRow('Assegnazione Vascelli', self.assegnazione_cb)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        crea = QPushButton('Crea')
        crea.clicked.connect(self._on_create)
        annulla = QPushButton('Annulla')
        annulla.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(crea)
        btn_row.addWidget(annulla)
        layout.addLayout(btn_row)

        self._payload = None

    def _on_create(self):
        # build payload with date at midnight UTC (simple format)
        d = self.date_edit.date()
        date_str = d.toString('yyyy-MM-dd')
        # append time at midnight with Z
        data_rif = f"{date_str}T00:00:00.000Z"

        self._payload = {
            'data_riferimento': data_rif,
            'stato': 'CREATO',
        }
        self.accept()

    def get_payload(self):
        return getattr(self, '_payload', None)
