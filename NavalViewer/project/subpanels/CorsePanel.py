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
        self.tratta_list = tratta_list or []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.tratta_cb = QComboBox()
        for t in self.tratta_list:
            if isinstance(t, dict):
                self.tratta_cb.addItem(str(t.get('id') or ''))
            else:
                self.tratta_cb.addItem(str(t))

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
        tratta = self.tratta_cb.currentText()
        if not tratta:
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
            'tratta_id': tratta,
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

        # show selected corsa id (non editabile)
        self.corsa_label = QLabel(self.corsa_id)
        self.name_edit = QLineEdit()
        self.vascello_cb = QComboBox()

        form.addRow('Corsa Selezionata (ID)', self.corsa_label)
        form.addRow('Nome Ottimizzazione', self.name_edit)
        form.addRow('Vascello', self.vascello_cb)

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
        for v in vascello_list:
            if isinstance(v, dict):
                vid = str(v.get('id', ''))
                name = v.get('nome') or v.get('name') or vid
            else:
                vid = str(v)
                name = vid
            self.vascello_cb.addItem(str(name), vid)

    def start_optimization(self):
        name = self.name_edit.text().strip()
        vascello_id = self.vascello_cb.currentData() or self.vascello_cb.currentText()
        corsa_id = self.corsa_id
        if not name:
            QMessageBox.warning(self, 'Errore', 'Inserisci il Nome Ottimizzazione')
            return
        if not corsa_id:
            QMessageBox.warning(self, 'Errore', 'ID corsa non disponibile')
            return
        if not vascello_id:
            QMessageBox.warning(self, 'Errore', 'Seleziona un vascello')
            return

        if post_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
            return

        payload = {
            'corsa_id': corsa_id,
            'vascello_id': vascello_id,
            'optimization_id': name,
        }

        progress = QProgressDialog('Avviando ottimizzazione...', None, 0, 0, self)
        progress.setWindowTitle('Ottimizzazione')
        progress.setCancelButton(None)
        progress.setModal(True)
        progress.show()
        try:
            post_json('ottimizzatore', payload=payload, timeout=300)
            progress.close()
            QMessageBox.information(self, 'Successo', 'Ottimizzazione avviata con successo')
            self.accept()
        except Exception as e:
            progress.close()
            QMessageBox.warning(self, 'Errore', f'Ottimizzazione fallita: {e}')



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

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Tratta",
            "Orario Partenza",
            "Previsione Passeggeri",
            "Arrivo Max",
        ])

        # select whole rows on click and allow single selection
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # update details button when selection changes
        # (connected later after details button exists)

        layout.addWidget(self.table)
        # buttons
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)
        btn_row.addWidget(self.add_btn)

        # details button to show PercorsiDialog for selected row
        self.details_btn = QPushButton('Dettagli Percorsi')
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self.open_details_dialog)
        btn_row.addWidget(self.details_btn)
        # button to show selected corsa in the dashboard (similar to PortiPanel)
        self.show_dashboard_btn = QPushButton('Mostra in Dashboard')
        self.show_dashboard_btn.setEnabled(False)
        self.show_dashboard_btn.clicked.connect(self._open_dashboard)
        btn_row.addWidget(self.show_dashboard_btn)
        # optimize button to start optimization for selected corsa
        self.optimize_btn = QPushButton('Ottimizza Percorsi')
        self.optimize_btn.setEnabled(False)
        self.optimize_btn.clicked.connect(self.open_optimization_dialog)
        if post_json is None:
            # posting required to start optimization
            self.optimize_btn.setEnabled(False)
        btn_row.addWidget(self.optimize_btn)
        btn_row.addStretch()
        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        btn_row.addWidget(self.refresh_btn)
        layout.addLayout(btn_row)

        # connect selection change now that details button exists
        self.table.itemSelectionChanged.connect(self.update_details_button_state)

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
            tratta = str(item.get('tratta_id', ''))
            orario_raw = item.get('orario_partenza_schedulato', '')
            orario = self._format_dt(orario_raw)
            arrivo_max = item.get('orario_arrivo_max')
            arrivo_text = '' if arrivo_max is None else self._format_dt(arrivo_max)

            previsione = item.get('previsione') or {}
            pax = previsione.get('passeggeri_stimati') if isinstance(previsione, dict) else ''
            pax_text = '' if pax is None else str(pax)

            it_id = QTableWidgetItem(cid)
            it_tratta = QTableWidgetItem(tratta)
            it_orario = QTableWidgetItem(orario)
            it_pax = QTableWidgetItem(pax_text)
            it_arrivo = QTableWidgetItem(arrivo_text)

            # store full object in first column
            it_id.setData(Qt.UserRole, item)

            for it in (it_id, it_tratta, it_orario, it_pax, it_arrivo):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_id)
            self.table.setItem(row, 1, it_tratta)
            self.table.setItem(row, 2, it_orario)
            self.table.setItem(row, 3, it_pax)
            self.table.setItem(row, 4, it_arrivo)

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
        item = self.table.item(row, 0)
        corsa = item.data(Qt.UserRole) if item is not None else None
        dlg = PercorsiDialog(self, corsa=corsa)
        dlg.exec_()

    def open_optimization_dialog(self):
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessuna corsa selezionata')
            return
        row = sel[0].row()
        item = self.table.item(row, 0)
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
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        corsa = item.data(Qt.UserRole) or {}
        # try to get a friendly label
        corsa_id = str(corsa.get('id') if isinstance(corsa, dict) else item.text())
        desc = corsa.get('tratta_id') if isinstance(corsa, dict) else corsa_id

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
            main.open_dashboard_embedded('static/index.html#/previsione_domanda', {'corsa': corsa_id}, title=f'Previsione Corsa: {corsa_id}', size=(1500, 800))
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile aprire la dashboard integrata: {e}')
