from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSizePolicy,
    QAbstractItemView,
)

from PyQt5.QtCore import QUrl
import os
import webbrowser

# Try to import QWebEngineView for embedded HTML preview; fallback to external browser
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None

# Import get_json, post_json and open_dashboard with fallback to support different import styles
try:
    from ApiClient import get_json, post_json, open_dashboard
except Exception:
    try:
        from project.ApiClient import get_json, post_json, open_dashboard
    except Exception:
        get_json = None
        post_json = None
        open_dashboard = None

class PortiPanel(QWidget):
    """Panel that displays ports in a table populated from the API.

    Calls GET /porto/lista and shows columns Nome, Lat, Lon, ID. A
    button `Aggiorna` refreshes the data on demand.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels([
            "Nome", 
            "Lat", 
            "Lon", 
            "ID",
        ])
        # select whole rows when clicked
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table)

        # buttons row: Aggiungi (sinistra) ... Aggiorna (destra)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)

        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        # disable if posting not available
        if post_json is None:
            self.add_btn.setEnabled(False)
        self.add_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_row.addWidget(self.add_btn)

        # modify button (enabled when a row is selected) - placed next to Add
        self.modify_btn = QPushButton('Modifica')
        self.modify_btn.clicked.connect(self.open_modify_dialog)
        self.modify_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.modify_btn.setEnabled(False)
        btn_row.addWidget(self.modify_btn)

        # button to show selected port in the dashboard (inline or external)
        self.show_dashboard_btn = QPushButton('Mostra in Dashboard')
        self.show_dashboard_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.show_dashboard_btn.setEnabled(False)
        self.show_dashboard_btn.clicked.connect(self._open_dashboard)
        btn_row.addWidget(self.show_dashboard_btn)

        btn_row.addStretch()

        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_row.addWidget(self.refresh_btn)

        layout.addLayout(btn_row)

        # carica i dati iniziali
        self.load_data()

    def load_data(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            data = get_json('porto/lista')
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare porti: {e}')

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            nome = str(item.get('nome', ''))
            lat = str(item.get('lat', ''))
            lon = str(item.get('lon', ''))
            pid = str(item.get('id', ''))

            it_nome = QTableWidgetItem(nome)
            it_lat = QTableWidgetItem(lat)
            it_lon = QTableWidgetItem(lon)
            it_id = QTableWidgetItem(pid)

            # store the full object in the first column for convenience
            it_nome.setData(Qt.UserRole, item)

            # make items read-only
            for it in (it_nome, it_lat, it_lon, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)


            self.table.setItem(row, 0, it_nome)
            self.table.setItem(row, 1, it_lat)
            self.table.setItem(row, 2, it_lon)
            self.table.setItem(row, 3, it_id)
        self.table.resizeColumnsToContents()

        # connect selection change to enable/disable modify button
        try:
            self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

        # notify main map (if available) so ports appear on the map as well
        try:
            # climb parents to find MainWindow which holds .view and refresh helper
            p = self
            main = None
            for _ in range(6):
                p = p.parent()
                if p is None:
                    break
                if hasattr(p, 'view'):
                    main = p
                    break
            if main is not None and hasattr(main, 'refresh_ports_on_map'):
                try:
                    main.refresh_ports_on_map(items)
                except Exception:
                    pass
        except Exception:
            pass

    def open_add_dialog(self):
        dlg = AddPortDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            if not payload:
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client POST non disponibile')
                return
            try:
                post_json('porto/crea', payload)
                QMessageBox.information(self, 'OK', 'Porto creato con successo')
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Creazione porto fallita: {e}')

    def _on_selection_changed(self, selected, deselected):
        # enable modify button when a row is selected
        has = self.table.selectionModel().hasSelection()
        self.modify_btn.setEnabled(bool(has))
        self.show_dashboard_btn.setEnabled(bool(has))

    def open_modify_dialog(self):
        # require a selected row
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Errore', 'Seleziona un porto da modificare')
            return
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        data = item.data(Qt.UserRole) or {}
        dlg = AddPortDialog(self, initial=data)
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            if not payload:
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client POST non disponibile')
                return
            try:
                post_json('porto/modifica', payload)
                QMessageBox.information(self, 'OK', 'Porto modificato con successo')
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Modifica porto fallita: {e}')

    def _open_dashboard(self):
        # open the selected port in the dashboard HTML via ApiClient.open_dashboard
        if open_dashboard is None:
            QMessageBox.warning(self, 'Errore', 'Funzione dashboard non disponibile')
            return
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Errore', 'Seleziona un porto')
            return
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        data = item.data(Qt.UserRole) or {}
        nome = data.get('nome') or item.text()
        # call shared helper
        open_dashboard('static/index.html#/porto', {'port': nome}, title=f'Dashboard: {nome}', size=(1500, 800))


class AddPortDialog(QDialog):
    """Dialog per creare o modificare un porto: richiede nome, lat, lon.

    Se viene passato `initial` (dict) i campi vengono pre-popolati e il
    payload restituito includerà la chiave `id`.
    """

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle('Aggiungi Porto' if initial is None else 'Modifica Porto')
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.lat_input = QLineEdit()
        self.lon_input = QLineEdit()
        self.lat_input.setPlaceholderText('es. 40.6321')
        self.lon_input.setPlaceholderText('es. 14.6028')
        form.addRow('Nome:', self.name_input)
        form.addRow('Lat:', self.lat_input)
        form.addRow('Lon:', self.lon_input)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.next_btn = QPushButton('Avanti')
        self.next_btn.clicked.connect(self._on_next)
        btns.addWidget(self.next_btn)
        self.cancel_btn = QPushButton('Annulla')
        self.cancel_btn.clicked.connect(self.reject)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)

        self._payload = None
        self._initial_id = None
        # prefill if initial provided
        if isinstance(initial, dict):
            self.name_input.setText(str(initial.get('nome', '')))
            lat = initial.get('lat')
            lon = initial.get('lon')
            if lat is not None:
                self.lat_input.setText(str(lat))
            if lon is not None:
                self.lon_input.setText(str(lon))
            self._initial_id = initial.get('id')

    def _on_next(self):
        nome = self.name_input.text().strip()
        lat_s = self.lat_input.text().strip()
        lon_s = self.lon_input.text().strip()
        if not nome:
            QMessageBox.warning(self, 'Errore', 'Inserire il nome')
            return
        try:
            lat = float(lat_s)
            lon = float(lon_s)
        except Exception:
            QMessageBox.warning(self, 'Errore', 'Lat e Lon devono essere numerici')
            return
        self._payload = {'nome': nome, 'lat': lat, 'lon': lon}
        self.accept()

    def get_payload(self):
        if not self._payload:
            return None
        out = dict(self._payload)
        if getattr(self, '_initial_id', None):
            out['id'] = self._initial_id
        return out
