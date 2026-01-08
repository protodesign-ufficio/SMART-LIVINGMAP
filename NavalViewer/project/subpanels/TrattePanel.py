from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QDialog,
    QFormLayout,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QLabel,
)

# Import get_json and post_json with fallback to support different import styles
try:
    from ApiClient import get_json, post_json
except Exception:
    try:
        from project.ApiClient import get_json, post_json
    except Exception:
        get_json = None
        post_json = None


class AddTrattaDialog(QDialog):
    def __init__(self, parent=None, port_names=None):
        super().__init__(parent)
        self.setWindowTitle('Aggiungi Tratta')
        self.port_names = port_names or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(['Semplice', 'Con intermedi'])
        self.mode_cb.currentTextChanged.connect(self._on_mode_change)
        form.addRow('Tipo', self.mode_cb)

        self.start_cb = QComboBox()
        self.start_cb.addItems(self.port_names)
        self.end_cb = QComboBox()
        self.end_cb.addItems(self.port_names)
        self.lbl_start = QLabel('Partenza')
        self.lbl_arrival = QLabel('Arrivo')
        form.addRow(self.lbl_start, self.start_cb)
        form.addRow(self.lbl_arrival, self.end_cb)

        layout.addLayout(form)

        # multi widgets: available list (left) and selected (right) with controls
        lists_row = QHBoxLayout()

        self.available_list = QListWidget()
        self.available_list.addItems(self.port_names)
        lists_row.addWidget(self.available_list)

        mid_btns = QVBoxLayout()
        self.btn_move_right = QPushButton('>>')
        self.btn_move_right.clicked.connect(self._move_to_selected)
        self.btn_move_left = QPushButton('<<')
        self.btn_move_left.clicked.connect(self._move_to_available)
        mid_btns.addStretch()
        mid_btns.addWidget(self.btn_move_right)
        mid_btns.addWidget(self.btn_move_left)
        mid_btns.addStretch()
        lists_row.addLayout(mid_btns)

        right_col = QVBoxLayout()
        self.selected_list = QListWidget()
        # reorder buttons
        order_row = QHBoxLayout()
        self.btn_up = QPushButton('Su')
        self.btn_up.clicked.connect(self._move_up)
        self.btn_down = QPushButton('Giu')
        self.btn_down.clicked.connect(self._move_down)
        order_row.addWidget(self.btn_up)
        order_row.addWidget(self.btn_down)

        right_col.addWidget(self.selected_list)
        right_col.addLayout(order_row)
        lists_row.addLayout(right_col)

        layout.addLayout(lists_row)

        btn_row = QHBoxLayout()
        ok = QPushButton('Crea')
        ok.clicked.connect(self._on_create)
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        self._on_mode_change(self.mode_cb.currentText())

    def _on_mode_change(self, mode):
        is_multi = mode == 'Con intermedi'
        # show/hide start/end for simple mode (hide labels too)
        self.start_cb.setVisible(not is_multi)
        self.end_cb.setVisible(not is_multi)
        self.lbl_start.setVisible(not is_multi)
        self.lbl_arrival.setVisible(not is_multi)
        # show/hide lists for multi
        self.available_list.setVisible(is_multi)
        self.selected_list.setVisible(is_multi)
        self.btn_move_right.setVisible(is_multi)
        self.btn_move_left.setVisible(is_multi)
        self.btn_up.setVisible(is_multi)
        self.btn_down.setVisible(is_multi)
        # resize dialog a bit when multi
        if is_multi:
            self.resize(500, 400)
        else:
            self.resize(300, 100)

    def _move_to_selected(self):
        for it in list(self.available_list.selectedItems()):
            name = it.text()
            # avoid duplicates
            existing = [self.selected_list.item(i).text() for i in range(self.selected_list.count())]
            if name in existing:
                continue
            self.selected_list.addItem(QListWidgetItem(name))

    def _move_to_available(self):
        for it in list(self.selected_list.selectedItems()):
            row = self.selected_list.row(it)
            self.selected_list.takeItem(row)

    def _move_up(self):
        row = self.selected_list.currentRow()
        if row > 0:
            item = self.selected_list.takeItem(row)
            self.selected_list.insertItem(row-1, item)
            self.selected_list.setCurrentRow(row-1)

    def _move_down(self):
        row = self.selected_list.currentRow()
        if row < self.selected_list.count()-1 and row >= 0:
            item = self.selected_list.takeItem(row)
            self.selected_list.insertItem(row+1, item)
            self.selected_list.setCurrentRow(row+1)

    def get_payloads(self):
        mode = self.mode_cb.currentText()
        def abbrev(n):
            return (n[:3].upper() if n else '')

        if mode == 'Semplice':
            partenza = self.start_cb.currentText()
            arrivo = self.end_cb.currentText()
            tratta_id = f"{abbrev(partenza)}-{abbrev(arrivo)}"
            payload = {
                'id': tratta_id,
                'porto_partenza': partenza,
                'porto_arrivo': arrivo,
                'distanza_miglia': None,
            }
            return 'tratta/crea', payload
        else:
            names = [self.selected_list.item(i).text() for i in range(self.selected_list.count())]
            if len(names) < 2:
                return None, None
            tratta_id = '-'.join(abbrev(n) for n in names)
            payload = {
                'id': tratta_id,
                'porti': names,
                'distanza_miglia': None,
            }
            return 'tratta/crea_multi', payload

    def _on_create(self):
        mode = self.mode_cb.currentText()
        if mode == 'Semplice':
            partenza = self.start_cb.currentText()
            arrivo = self.end_cb.currentText()
            if partenza == arrivo:
                QMessageBox.warning(self, 'Errore', 'Porto di partenza e di arrivo non possono essere uguali')
                return
        else:
            if self.selected_list.count() < 2:
                QMessageBox.warning(self, 'Errore', 'Seleziona almeno due porti per creare la tratta con intermedi')
                return
        # validation passed
        self.accept()


class TrattePanel(QWidget):
    """Panel che mostra le tratte.

    Recupera la lista delle tratte tramite `GET /tratta/lista` e mostra una
    tabella con colonne: `ID`, `Partenza`, `Arrivo`, `Intermedi`.

    Per i campi `Partenza`, `Arrivo` e `Intermedi` risolve gli ID dei porti
    chiamando `GET /posto/{porto_id}` e visualizza il `nome` del porto.
    I nomi dei porti vengono memorizzati in cache in `self.port_cache` per
    evitare richieste ripetute.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Partenza",
            "Arrivo",
            "Intermedi",
        ])
        layout.addWidget(self.table)

        # select whole rows on click and allow single selection
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # buttons: Aggiungi (left) ... Aggiorna (right)
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)
        btn_row.addWidget(self.add_btn)
        btn_row.addStretch()
        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        btn_row.addWidget(self.refresh_btn)
        layout.addLayout(btn_row)

        # simple in-memory cache for port names keyed by porto_id
        self.port_cache = {}

        # load initial data
        self.load_data()

    def get_port_name(self, porto_id):
        """Restituisce il nome del porto per l'ID fornito, usando cache.

        Se la chiamata fallisce ritorna l'ID come fallback.
        """
        if not porto_id:
            return ''
        # if porto_id already appears to be a dict/object, try to extract name
        if isinstance(porto_id, dict):
            return str(porto_id.get('nome', ''))

        pid = str(porto_id)
        if pid in self.port_cache:
            return self.port_cache[pid]
        if get_json is None:
            return pid
        try:
            resp = get_json(f'porto/{pid}')
            if isinstance(resp, dict):
                name = resp.get('nome') or pid
            else:
                name = pid
        except Exception:
            name = pid
        self.port_cache[pid] = str(name)
        return str(name)

    def load_data(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            data = get_json('tratta/lista')
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare tratte: {e}')

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            item_id = str(item.get('id', ''))

            # origine/destinazione possono essere solo ID oppure oggetti: gestiamo entrambi
            partenza_id = item.get('porto_partenza_id')
            arrivo_id = item.get('porto_arrivo_id')
            intermedi_raw = item.get('porti_intermedi', [])

            # resolve names (uses cache)
            partenza_name = self.get_port_name(partenza_id)
            arrivo_name = self.get_port_name(arrivo_id)

            # intermedi può essere lista di id o stringa; normalizziamo a lista
            intermedi_list = []
            if intermedi_raw is None:
                intermedi_list = []
            elif isinstance(intermedi_raw, (list, tuple)):
                intermedi_list = intermedi_raw
            elif isinstance(intermedi_raw, str):
                # possibile CSV
                intermedi_list = [s.strip() for s in intermedi_raw.split(',') if s.strip()]
            else:
                intermedi_list = [intermedi_raw]

            intermedi_names = [self.get_port_name(x) for x in intermedi_list]
            intermedi_text = ', '.join([n for n in intermedi_names if n])

            it_id = QTableWidgetItem(item_id)
            it_partenza = QTableWidgetItem(partenza_name)
            it_arrivo = QTableWidgetItem(arrivo_name)
            it_intermedi = QTableWidgetItem(intermedi_text)

            # store the full object in the first column for convenience
            it_id.setData(Qt.UserRole, item)

            # make items read-only
            for it in (it_id, it_partenza, it_arrivo, it_intermedi):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_id)
            self.table.setItem(row, 1, it_partenza)
            self.table.setItem(row, 2, it_arrivo)
            self.table.setItem(row, 3, it_intermedi)

        self.table.resizeColumnsToContents()

    def open_add_dialog(self):
        port_names = []
        if get_json is not None:
            try:
                ports = get_json('porto/lista')
                if isinstance(ports, list):
                    for p in ports:
                        if isinstance(p, dict):
                            port_names.append(p.get('nome') or str(p.get('id', '')))
                        else:
                            port_names.append(str(p))
            except Exception:
                port_names = []

        dlg = AddTrattaDialog(self, port_names=port_names)
        if dlg.exec_() != QDialog.Accepted:
            return
        endpoint, payload = dlg.get_payloads()
        if endpoint is None:
            QMessageBox.warning(self, 'Errore', 'Seleziona almeno due porti per creare la tratta')
            return
        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
            return
        try:
            post_json(endpoint, payload)
            QMessageBox.information(self, 'Successo', 'Tratta creata con successo')
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile creare tratta: {e}')
