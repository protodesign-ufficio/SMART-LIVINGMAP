from PyQt5.QtCore import Qt, QDate, QTime
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

        # disable UI controls to prevent duplicate submits
        try:
            self.start_btn.setEnabled(False)
            self.vascello_cb.setEnabled(False)
            self.optimize_all_cb.setEnabled(False)
        except Exception:
            pass

        # show a simple status dialog with only a text label (no progress bar)
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QApplication
        corsa_name = self.corsa_label.text() or str(corsa_id)
        status_dlg = QDialog(self)
        status_dlg.setWindowTitle('Ottimizzazione')
        status_dlg.setWindowModality(Qt.ApplicationModal)
        status_layout = QVBoxLayout(status_dlg)
        status_label = QLabel(f"Avvio ottimizzazione per la corsa {corsa_name}")
        status_layout.addWidget(status_label)
        status_dlg.show()
        QApplication.processEvents()

        errors = []
        try:
            if self.optimize_all_cb.isChecked():
                vlist = getattr(self, '_vascello_list', []) or []
                if not vlist:
                    QMessageBox.warning(self, 'Errore', 'Nessun vascello disponibile per ottimizzare')
                    return
                for v in vlist:
                    if isinstance(v, dict):
                        vid = str(v.get('id', ''))
                        name = v.get('nome') or v.get('name') or vid
                    else:
                        vid = str(v)
                        name = vid
                    # update progress label with current target
                    status_label.setText(f"Ottimizzazione percorsi per la corsa {corsa_name} per il vascello {name}")
                    QApplication.processEvents()
                    try:
                        post_json('weather_routing/carico', payload={
                            'corsa_id': corsa_id,
                            'vascello_id': vid,
                            'eps_time': eps_time,
                            'fake_data': True,
                        }, timeout=300)
                    except Exception as e:
                        errors.append((vid, str(e)))
                status_dlg.close()
                if errors:
                    QMessageBox.warning(self, 'Errore', f'Ottimizzazione completata con errori: {errors}')
                else:
                    QMessageBox.information(self, 'Successo', 'Ottimizzazione completata per tutti i vascelli')
                self.accept()
                return

            # single vascello flow
            if not vascello_id:
                QMessageBox.warning(self, 'Errore', 'Seleziona un vascello')
                return

            vname = self.vascello_cb.currentText() or str(vascello_id)
            payload = {
                'corsa_id': corsa_id,
                'vascello_id': vascello_id,
                'eps_time': eps_time,
                'fake_data': True,
            }
            status_label.setText(f"Ottimizzazione percorsi per la corsa {corsa_name} per il vascello {vname}")
            QApplication.processEvents()
            post_json('weather_routing/carico', payload=payload, timeout=300)
            status_dlg.close()
            QMessageBox.information(self, 'Successo', 'Ottimizzazione completata con successo')
            self.accept()
        except Exception as e:
            progress.close()
            QMessageBox.warning(self, 'Errore', f'Ottimizzazione fallita: {e}')
        finally:
            try:
                self.start_btn.setEnabled(True)
                self.vascello_cb.setEnabled(True)
                self.optimize_all_cb.setEnabled(True)
            except Exception:
                pass


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

        # columns: Nome, Tratta (nome), Orario Partenza, Previsione Passeggeri, Arrivo Max, ID
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Nome",
            "Tratta",
            "Orario Partenza",
            "Previsione Passeggeri",
            "Arrivo Max",
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
        serv_layout.addWidget(self.show_dashboard_btn)
        serv_layout.addWidget(self.details_btn)
        serv_layout.addWidget(self.optimize_btn)
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

    def load_data(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            data = get_json('corsa/lista')
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
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
            tratta_raw = item.get('tratta_id')
            # tratta can be an object or id
            tratta_id = None
            if isinstance(tratta_raw, dict):
                tratta_id = tratta_raw.get('id')
            else:
                tratta_id = tratta_raw
            tratta = self.get_tratta_name(tratta_id)
            orario_raw = item.get('orario_partenza_schedulato', '')
            orario = self._format_dt(orario_raw)
            arrivo_max = item.get('orario_arrivo_max')
            arrivo_text = '' if arrivo_max is None else self._format_dt(arrivo_max)

            previsione = item.get('previsione') or {}
            pax = previsione.get('passeggeri_stimati') if isinstance(previsione, dict) else ''
            pax_text = '' if pax is None else str(pax)

            it_name = QTableWidgetItem(corsa_name)
            it_tratta = QTableWidgetItem(tratta)
            it_orario = QTableWidgetItem(orario)
            it_pax = QTableWidgetItem(pax_text)
            it_arrivo = QTableWidgetItem(arrivo_text)
            # ID cell (last column) holds the full object in Qt.UserRole
            it_id = QTableWidgetItem(cid)
            it_id.setData(Qt.UserRole, item)

            for it in (it_name, it_tratta, it_orario, it_pax, it_arrivo, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            # Nome, Tratta, Orario, Previsione, Arrivo, ID
            self.table.setItem(row, 0, it_name)
            self.table.setItem(row, 1, it_tratta)
            self.table.setItem(row, 2, it_orario)
            self.table.setItem(row, 3, it_pax)
            self.table.setItem(row, 4, it_arrivo)
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
