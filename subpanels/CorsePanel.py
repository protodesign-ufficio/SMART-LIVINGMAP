from PyQt5.QtCore import Qt, QDate, QTime, QThread, pyqtSignal
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
    QLineEdit,
    QLabel,
    QDateEdit,
    QTimeEdit,
    QProgressDialog,
    QSpinBox,
    QCheckBox,
    QGroupBox,
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

# import the PercorsiDialog from separate module
try:
    from .PercorsiDialog import PercorsiDialog
except Exception:
    try:
        from PercorsiDialog import PercorsiDialog
    except Exception:
        PercorsiDialog = None


class AddCorsaDialog(QDialog):
    def __init__(self, parent=None, tratta_list=None):
        super().__init__(parent)
        self.setWindowTitle('Aggiungi Corsa')
        self.resize(300,150)
        self.tratta_list = tratta_list or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.tratta_cb = QComboBox()
        for t in self.tratta_list:
            # if tratta is dict prefer to show its name but store its id as data
            if isinstance(t, dict):
                tid = str(t.get('id', ''))
                name = t.get('nome') or t.get('name') or tid
                self.tratta_cb.addItem(str(name), tid)
            else:
                s = str(t)
                self.tratta_cb.addItem(s, s)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.time_edit = QTimeEdit()
        self.arrival_time = QTimeEdit()

        # initialize to now
        now_date = QDate.currentDate()
        now_time = QTime.currentTime()
        self.date_edit.setDate(now_date)
        self.time_edit.setTime(now_time)
        # default arrival 1 hour later
        self.arrival_time.setTime(now_time.addSecs(3600))

        form.addRow('Tratta', self.tratta_cb)
        form.addRow('Data Partenza', self.date_edit)
        form.addRow('Orario Partenza', self.time_edit)
        form.addRow('Orario Arrivo Max (HH:MM)', self.arrival_time)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        ok = QPushButton('Crea')
        ok.clicked.connect(self._on_create)
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def _on_create(self):
        # prefer the stored id (userData); fallback to visible text
        tratta_id = self.tratta_cb.currentData() or self.tratta_cb.currentText()
        if not tratta_id:
            QMessageBox.warning(self, 'Errore', 'Seleziona una tratta')
            return
        date_str = self.date_edit.date().toString('yyyy-MM-dd')
        time_str = self.time_edit.time().toString('HH:mm')
        arr_time = self.arrival_time.time()
        # validate arrival time > departure time (same day)
        if arr_time <= self.time_edit.time():
            QMessageBox.warning(self, 'Errore', 'Orario di arrivo massimo deve essere dopo l\'orario di partenza')
            return
        arr_time_str = arr_time.toString('HH:mm')

        self._payload = {
            'tratta_id': tratta_id,
            'data': date_str,
            'orario': time_str,
            'orario_arrivo_max': arr_time_str,
        }
        
        self.accept()

    def get_payload(self):
        return getattr(self, '_payload', None)


class OptimizationWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, endpoint, payload, **kwargs):
        super().__init__()
        self.endpoint = endpoint
        self.payload = payload
        self.kwargs = kwargs

    def run(self):
        if post_json is None:
            self.error.emit("Client API non disponibile")
            return
        try:
            post_json(self.endpoint, self.payload, **self.kwargs)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class OptimizationDialog(QDialog):
    """Dialog per avviare l'ottimizzazione per una corsa selezionata.

    Mostra l'ID della corsa, richiede il nome dell'ottimizzazione e permette
    di scegliere un vascello recuperato tramite `GET vascello/lista`.
    """

    def __init__(self, parent=None, corsa_id=None):
        super().__init__(parent)
        self.setWindowTitle('Ottimizza Percorsi')
        self.corsa_id = str(corsa_id) if corsa_id is not None else ''

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # show selected corsa name (non editabile). If available, resolve via API.
        display_name = self.corsa_id
        try:
            if get_json is not None and self.corsa_id:
                resp = get_json(f'corsa/{self.corsa_id}')
                if isinstance(resp, dict):
                    display_name = resp.get('nome') or resp.get('name') or display_name
        except Exception:
            # fallback to id on any error
            display_name = self.corsa_id
        self.corsa_label = QLabel(display_name)
        self.vascello_cb = QComboBox()
        self.eps_spin = QSpinBox()
        self.eps_spin.setRange(0, 3600)
        self.eps_spin.setValue(5)
        self.optimize_all_cb = QCheckBox('Ottimizza per tutti i vascelli')
        self.optimize_all_cb.setToolTip("Esegue l'ottimizzazione per tutti i vascelli disponibili")
        self.optimize_all_cb.toggled.connect(self._on_optimize_all_toggled)

        form.addRow('Corsa Selezionata', self.corsa_label)
        form.addRow('Vascello', self.vascello_cb)
        form.addRow('Eps Time', self.eps_spin)
        form.addRow('', self.optimize_all_cb)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton('Avvia')
        self.start_btn.clicked.connect(self.start_optimization)
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        self.load_choices()

    def load_choices(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per caricare liste')
            return
        try:
            vascello_list = get_json('vascello/lista') or []
        except Exception:
            vascello_list = []

        self.vascello_cb.clear()
        # keep a copy of the raw list for "optimize all" option
        self._vascello_list = vascello_list
        for v in vascello_list:
            if isinstance(v, dict):
                vid = str(v.get('id', ''))
                name = v.get('nome') or v.get('name') or vid
            else:
                vid = str(v)
                name = vid
            self.vascello_cb.addItem(str(name), vid)

    def _on_optimize_all_toggled(self, checked: bool):
        # when optimizing all, disable the vascello selector to avoid confusion
        try:
            self.vascello_cb.setEnabled(not checked)
        except Exception:
            pass

    def start_optimization(self):
        vascello_id = self.vascello_cb.currentData() or self.vascello_cb.currentText()
        corsa_id = self.corsa_id
        eps_time = int(self.eps_spin.value())
        # basic validations
        if not corsa_id:
            QMessageBox.warning(self, 'Errore', 'ID corsa non disponibile')
            return

        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
            return

        payload = {}
        # Prepare payload
        if self.optimize_all_cb.isChecked():
            vlist = getattr(self, '_vascello_list', []) or []
            if not vlist:
                QMessageBox.warning(self, 'Errore', 'Nessun vascello disponibile per ottimizzare')
                return

            items_payload = []
            for v in vlist:
                if isinstance(v, dict):
                    vid = str(v.get('id', ''))
                else:
                    vid = str(v)

                items_payload.append({
                    'corsa_id': corsa_id,
                    'vascello_id': vid,
                    'eps_time': eps_time,
                    'fake_data': True,
                    'tolerance': 1,
                    've_min': 0.1
                })
            payload = {'items': items_payload}
        else:
            # single vascello flow
            if not vascello_id:
                QMessageBox.warning(self, 'Errore', 'Seleziona un vascello')
                return

            payload = {'items': [{
                'corsa_id': corsa_id,
                'vascello_id': vascello_id,
                'eps_time': eps_time,
                'fake_data': True,
                'tolerance': 1,
                've_min': 0.1
            }]}

        # Disable UI controls to prevent duplicate submits
        try:
            self.start_btn.setEnabled(False)
            self.start_btn.setText("Elaborazione...")
            self.vascello_cb.setEnabled(False)
            self.optimize_all_cb.setEnabled(False)
            self.eps_spin.setEnabled(False)
        except Exception:
            pass

        # Create and start worker
        self.worker = OptimizationWorker('weather_routing/carico', payload, timeout=300)
        self.worker.finished.connect(self._on_opt_finished)
        self.worker.error.connect(self._on_opt_error)
        self.worker.start()

    def _on_opt_finished(self):
        QMessageBox.information(self, 'Successo', 'Ottimizzazione inviata con successo')
        self.accept()

    def _on_opt_error(self, err_msg):
        QMessageBox.warning(self, 'Errore', f'Ottimizzazione fallita: {err_msg}')
        try:
            self.start_btn.setEnabled(True)
            self.start_btn.setText("Avvia")
            self.vascello_cb.setEnabled(True)
            self.optimize_all_cb.setEnabled(True)
            self.eps_spin.setEnabled(True)
        except Exception:
            pass


class OptimizationDayDialog(QDialog):
    def __init__(self, parent=None, initial_date=None):
        super().__init__(parent)
        self.setWindowTitle('Ottimizza Giorno')
        self.resize(250, 380)
        
        layout = QVBoxLayout(self)
        
        # Date selection
        form = QFormLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        if initial_date:
            self.date_edit.setDate(initial_date)
        else:
            self.date_edit.setDate(QDate.currentDate())
        form.addRow('Giorno', self.date_edit)
        layout.addLayout(form)
        
        # Table for vessels
        layout.addWidget(QLabel("Seleziona i vascelli da utilizzare:"))
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([' ', 'Vascello'])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)
        
        # Helper to toggle all
        btn_toggle = QPushButton("Seleziona/Deseleziona Tutti")
        btn_toggle.clicked.connect(self._toggle_all)
        layout.addWidget(btn_toggle)
        
        # Buttons
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton('Avvia')
        self.start_btn.clicked.connect(self.start_optimization)
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(cancel)
        
        layout.addLayout(btn_row)
        
        self.load_vessels()

    def load_vessels(self):
        if get_json is None:
            return
        try:
            vessels = get_json('vascello/lista') or []
            self.table.setRowCount(0)
            for v in vessels:
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                vid = str(v.get('id', '')) if isinstance(v, dict) else str(v)
                vname = v.get('nome') or v.get('name') or vid if isinstance(v, dict) else vid
                
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chk.setCheckState(Qt.Checked) # All selected by default
                chk.setData(Qt.UserRole, vid)
                
                name_item = QTableWidgetItem(vname)
                name_item.setFlags(Qt.ItemIsEnabled)
                
                self.table.setItem(row, 0, chk)
                self.table.setItem(row, 1, name_item)
                
        except Exception:
            pass

    def _toggle_all(self):
        cnt = self.table.rowCount()
        if cnt == 0: return
        # check first item state
        first = self.table.item(0, 0)
        new_state = Qt.Unchecked if first.checkState() == Qt.Checked else Qt.Checked
        for i in range(cnt):
            it = self.table.item(i, 0)
            it.setCheckState(new_state)

    def start_optimization(self):
        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
            
        selected_ids = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it.checkState() == Qt.Checked:
                selected_ids.append(it.data(Qt.UserRole))
        
        if not selected_ids:
            QMessageBox.warning(self, 'Errore', 'Seleziona almeno un vascello')
            return
            
        d = self.date_edit.date()
        d_str = d.toString('yyyy-MM-dd')
        
        payload = {
            "start": f"{d_str}T00:00:00",
            "end": f"{d_str}T23:59:00",
            "vessels": selected_ids,
            "eps_time": 5,
            "fake_data": True
        }
        
        # Disable UI and start thread
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Elaborazione...")
        self.table.setEnabled(False)
        self.date_edit.setEnabled(False)
        
        self.worker = OptimizationWorker('assegnazione/pianifica', payload)
        self.worker.finished.connect(self._on_opt_finished)
        self.worker.error.connect(self._on_opt_error)
        self.worker.start()

    def _on_opt_finished(self):
        QMessageBox.information(self, 'Successo', 'Pianificazione giornaliera completata')
        self.accept()

    def _on_opt_error(self, msg):
        QMessageBox.warning(self, 'Errore', f'Errore pianificazione: {msg}')
        # Re-enable UI
        self.start_btn.setText("Avvia")
        self.start_btn.setEnabled(True)
        self.table.setEnabled(True)
        self.date_edit.setEnabled(True)


class CorsePanel(QWidget):
    """Panel that displays scheduled runs (corse).

    Calls `GET /corsa/lista` and shows columns:
    - `ID`
    - `Tratta` (tratta_id)
    - `Orario Partenza` (orario_partenza_schedulato)
    - `Previsione Passeggeri` (previsione.passeggeri_stimati)
    - `Arrivo Max` (orario_arrivo_max)

    A button `Aggiorna` refreshes the data. The full JSON object for each
    row is stored in the first column's `Qt.UserRole`.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Row filtri (Data)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Giorno:"))
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self._on_date_changed)
        # Increase width slightly
        self.date_filter.setFixedWidth(120)
        filter_layout.addWidget(self.date_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # columns: Nome, Tratta (nome), Orario Partenza, Previsione Passeggeri, Arrivo Max, ID
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Nome",
            "Tratta",
            "Orario Partenza",
            "Arrivo Max",
            "Previsione Passeggeri",
            "ID",
        ])

        # select whole rows on click and allow single selection
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # update details button when selection changes
        # (connected later after details button exists)

        # create buttons (they will be placed in right-side groups)
        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)

        # details button to show PercorsiDialog for selected row
        self.details_btn = QPushButton('Dettagli Percorsi')
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self.open_details_dialog)

        # button to show selected corsa in the dashboard (similar to PortiPanel)
        self.show_dashboard_btn = QPushButton('Mostra in Dashboard')
        self.show_dashboard_btn.setEnabled(False)
        self.show_dashboard_btn.clicked.connect(self._open_dashboard)

        # optimize button to start optimization for selected corsa
        self.optimize_btn = QPushButton('Ottimizza Percorsi')
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.clicked.connect(self.open_optimization_dialog)
        if post_json is None:
            # posting required to start optimization
            self.optimize_btn.setEnabled(False)

        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)

        # assemble main content: table on the left, controls grouped on the right
        content_row = QHBoxLayout()
        content_row.addWidget(self.table)

        # right-side vertical panel with two group boxes: Parametri and Servizi
        right_panel_widget = QVBoxLayout()

        # Parametri group: Aggiorna, Aggiungi
        param_group = QGroupBox('Parametri')
        param_layout = QVBoxLayout()
        param_layout.addWidget(self.refresh_btn)
        param_layout.addWidget(self.add_btn)
        param_group.setLayout(param_layout)
        right_panel_widget.addWidget(param_group)

        # Servizi group: Mostra in Dashboard, Ottimizza Percorsi, Dettagli Percorsi
        serv_group = QGroupBox('Servizi')
        serv_layout = QVBoxLayout()
        
        self.optimize_day_btn = QPushButton('Ottimizza Giorno')
        self.optimize_day_btn.clicked.connect(self.open_optimize_day_dialog)
        if post_json is None:
            self.optimize_day_btn.setEnabled(False)
            
        serv_layout.addWidget(self.show_dashboard_btn)
        serv_layout.addWidget(self.details_btn)
        serv_layout.addWidget(self.optimize_btn)
        serv_layout.addWidget(self.optimize_day_btn)
        serv_group.setLayout(serv_layout)
        right_panel_widget.addWidget(serv_group)

        right_panel_widget.addStretch()
        content_row.addLayout(right_panel_widget)
        layout.addLayout(content_row)

        # connect selection change now that details button exists
        self.table.itemSelectionChanged.connect(self.update_details_button_state)

        # cache for tratta names
        self.tratta_cache = {}

        # load initial data
        self.load_data()

    def _format_dt(self, s: str) -> str:
        """Formatta una stringa ISO datetime in 'gg/mm/aaaa hh:mm'."""
        if not s:
            return ''
        try:
            from datetime import datetime
            # strip timezone if present for fromisoformat compatibility on Py<3.11
            # but datetime.fromisoformat can handle offsets; we'll try directly
            dt = datetime.fromisoformat(str(s))
            return dt.strftime('%d/%m/%Y %H:%M')
        except Exception:
            return str(s)

    def get_tratta_name(self, tratta_id):
        """Resolve tratta name from id using simple cache and GET /tratta/{id}.

        If `tratta_id` is falsy returns empty string.
        """
        if not tratta_id:
            return ''
        tid = str(tratta_id)
        if tid in self.tratta_cache:
            return self.tratta_cache[tid]
        # if tratta_id looks like an object, try to extract name
        try:
            # attempt API call if available
            if get_json is not None:
                resp = get_json(f'tratta/{tid}')
                if isinstance(resp, dict):
                    name = resp.get('nome') or resp.get('name') or tid
                else:
                    name = tid
            else:
                name = tid
        except Exception:
            name = tid
        self.tratta_cache[tid] = str(name)
        return str(name)

    def _on_date_changed(self, qdate):
        self.load_data()

    def load_data(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            d = self.date_filter.date()
            date_str = d.toString('yyyy-MM-dd')
            path = f'corsa/giorno?giorno={date_str}'
            data = get_json(path)
            
            if not isinstance(data, list):
                # sometimes APIs return dict with list wrapped
                if isinstance(data, dict) and 'items' in data:
                    data = data['items']
                elif isinstance(data, dict) and 'data' in data:
                    data = data['data']
                else:
                    # fallback validation
                    # raise ValueError('Risposta API non è una lista')
                    data = [] # empty list on unexpected structure
            
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare corse: {e}')

    def open_add_dialog(self):
        tratta_list = []
        if get_json is not None:
            try:
                tratta_list = get_json('tratta/lista') or []
            except Exception:
                tratta_list = []

        dlg = AddCorsaDialog(self, tratta_list=tratta_list)
        if dlg.exec_() != QDialog.Accepted:
            return
        payload = dlg.get_payload()
        if payload is None:
            QMessageBox.warning(self, 'Errore', 'Payload non valido')
            return
        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
            return
        try:
            post_json('corsa/crea', payload)
            QMessageBox.information(self, 'Successo', 'Corsa creata con successo')
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile creare corsa: {e}')

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            cid = str(item.get('id', ''))
            # corsa name if present
            corsa_name = str(item.get('nome') or item.get('nome_corsa') or item.get('name') or '')
            
            # Tratta: prefer display string 'tratta'; fallback to resolving 'tratta_id'
            tratta_display = item.get('tratta')
            if not tratta_display:
                tratta_raw = item.get('tratta_id')
                tratta_id = None
                if isinstance(tratta_raw, dict):
                    tratta_id = tratta_raw.get('id')
                else:
                    tratta_id = tratta_raw
                tratta_display = self.get_tratta_name(tratta_id)
            
            # Orario: prefer 'orario'; fallback to 'orario_partenza_schedulato'
            orario_raw = item.get('orario') or item.get('orario_partenza_schedulato') or ''
            # if orario_raw is already HH:MM, _format_dt might fail or return as is. 
            # Let's ensure consistency. If it's a simple time, we leave it. If ISO, we format.
            if 'T' in str(orario_raw):
                orario = self._format_dt(orario_raw)
            else:
                orario = str(orario_raw)

            arrivo_max = item.get('orario_arrivo_max')
            # arrival sometimes full ISO, sometimes time. 
            arrivo_text = ''
            if arrivo_max:
                 if 'T' in str(arrivo_max):
                     arrivo_text = self._format_dt(arrivo_max)
                 else:
                     arrivo_text = str(arrivo_max)

            previsione = item.get('previsione') or {}
            pax = previsione.get('passeggeri_stimati') if isinstance(previsione, dict) else ''
            pax_text = '' if pax is None else str(pax)

            it_name = QTableWidgetItem(corsa_name)
            it_tratta = QTableWidgetItem(str(tratta_display))
            it_orario = QTableWidgetItem(orario)
            it_pax = QTableWidgetItem(pax_text)
            it_arrivo = QTableWidgetItem(arrivo_text)
            # ID cell (last column) holds the full object in Qt.UserRole
            it_id = QTableWidgetItem(cid)
            it_id.setData(Qt.UserRole, item)

            for it in (it_name, it_tratta, it_orario, it_pax, it_arrivo, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            # Nome, Tratta, Orario, Arrivo, Previsione, ID
            self.table.setItem(row, 0, it_name)
            self.table.setItem(row, 1, it_tratta)
            self.table.setItem(row, 2, it_orario)
            self.table.setItem(row, 3, it_arrivo)
            self.table.setItem(row, 4, it_pax)
            self.table.setItem(row, 5, it_id)

        self.table.resizeColumnsToContents()

    def update_details_button_state(self):
        has_sel = self.table.selectionModel().hasSelection()
        self.details_btn.setEnabled(bool(has_sel))
        # keep optimize button in sync with selection
        try:
            self.optimize_btn.setEnabled(bool(has_sel) and post_json is not None)
        except Exception:
            pass
        try:
            self.show_dashboard_btn.setEnabled(bool(has_sel))
        except Exception:
            pass

    def open_details_dialog(self):
        # get selected row
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessuna corsa selezionata')
            return
        row = sel[0].row()
        # full object stored in last column
        last_col = self.table.columnCount() - 1
        item = self.table.item(row, last_col)
        corsa = item.data(Qt.UserRole) if item is not None else None
        dlg = PercorsiDialog(self, corsa=corsa)
        dlg.exec_()

    def open_optimization_dialog(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessuna corsa selezionata')
            return
        row = sel[0].row()
        last_col = self.table.columnCount() - 1
        item = self.table.item(row, last_col)
        corsa = item.data(Qt.UserRole) if item is not None else None
        corsa_id = None
        if isinstance(corsa, dict):
            corsa_id = corsa.get('id')
        if corsa_id is None and item is not None:
            corsa_id = item.text()

        dlg = OptimizationDialog(self, corsa_id=corsa_id)
        dlg.exec_()

    def _open_dashboard(self):
        # open the previsione_domanda dashboard page for the selected corsa
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessuna corsa selezionata')
            return
        row = sel[0].row()
        last_col = self.table.columnCount() - 1
        item = self.table.item(row, last_col)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        corsa = item.data(Qt.UserRole) or {}
        # try to get a friendly label
        corsa_id = str(corsa.get('id') if isinstance(corsa, dict) else item.text())
        corsa_name = str(corsa.get('nome') or corsa.get('name'))
        print(f'Opening dashboard for corsa: {corsa_name} (ID: {corsa_id})')

        # find ancestor MainWindow or fallback to top-level widgets (same approach as PortiPanel)
        p = self
        main = None
        for _ in range(8):
            p = p.parent()
            if p is None:
                break
            if hasattr(p, 'open_dashboard_embedded'):
                main = p
                break

        if main is None:
            try:
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app is not None:
                    for w in app.topLevelWidgets():
                        try:
                            if hasattr(w, 'open_dashboard_embedded'):
                                main = w
                                break
                        except Exception:
                            continue
            except Exception:
                main = None

        if main is None:
            QMessageBox.warning(self, 'Errore', 'Embedded dashboard non disponibile nella applicazione')
            return

        try:
            main.open_dashboard_embedded('static/dashboard/index.html#/previsione_domanda', {'corsa': corsa_id}, title=f'Previsione Corsa: {corsa_name}', size=(1500, 900))
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile aprire la dashboard integrata: {e}')

    def open_optimize_day_dialog(self):
        cur_date = self.date_filter.date()
        dlg = OptimizationDayDialog(self, initial_date=cur_date)
        dlg.exec_()
