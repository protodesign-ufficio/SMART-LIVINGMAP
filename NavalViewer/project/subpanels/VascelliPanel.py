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

# Import get_json, post_json and open_dashboard with fallback
try:
    from ApiClient import get_json, post_json, open_dashboard
except Exception:
    try:
        from project.ApiClient import get_json, post_json, open_dashboard
    except Exception:
        get_json = None
        post_json = None
        open_dashboard = None


class VascelliPanel(QWidget):
    """Panel that displays vessels in a table populated from the API.

    Calls GET /vascello/lista and shows columns: Nome, MMSI, Capacità Pax.,
    Costo/Ora, Velocità Max (nodi), ID. A button `Aggiorna` refreshes data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Nome",
            "MMSI",
            "Capacità Pax.",
            "Costo/Ora",
            "Velocità Max (nodi)",
            "ID",
        ])
        # select whole rows and single selection
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table)

        # buttons: Aggiungi, Modifica (left) ... Aggiorna (right)
        btn_row = QHBoxLayout()
        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)
        btn_row.addWidget(self.add_btn)

        # modify button (enabled when a row is selected) - placed next to Add
        self.modify_btn = QPushButton('Modifica')
        self.modify_btn.setEnabled(False)
        self.modify_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.modify_btn.clicked.connect(self.open_modify_dialog)
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

        # load initial data
        self.load_data()

    def load_data(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            data = get_json('vascello/lista')
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare vascelli: {e}')

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            nome = str(item.get('nome', '-'))
            mmsi = str(item.get('mmsi', ''))
            pax = str(item.get('capacita_passeggeri', ''))
            costo = str(item.get('costo_orario_esercizio', ''))
            vel = str(item.get('velocita_max_nodi', ''))
            pid = str(item.get('id', ''))

            it_nome = QTableWidgetItem(nome)
            it_mmsi = QTableWidgetItem(mmsi)
            it_pax = QTableWidgetItem(pax)
            it_costo = QTableWidgetItem(costo)
            it_vel = QTableWidgetItem(vel)
            it_id = QTableWidgetItem(pid)

            # store the full object in the first column for convenience
            it_nome.setData(Qt.UserRole, item)

            # make items read-only
            for it in (it_nome, it_mmsi, it_pax, it_costo, it_vel, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_nome)
            self.table.setItem(row, 1, it_mmsi)
            self.table.setItem(row, 2, it_pax)
            self.table.setItem(row, 3, it_costo)
            self.table.setItem(row, 4, it_vel)
            self.table.setItem(row, 5, it_id)

        self.table.resizeColumnsToContents()

        try:
            self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

    def _on_selection_changed(self, selected, deselected):
        has = self.table.selectionModel().hasSelection()
        self.modify_btn.setEnabled(bool(has))
        self.show_dashboard_btn.setEnabled(bool(has))

    def open_add_dialog(self):
        dlg = VascelloDialog(self, initial=None)
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            if not payload:
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client POST non disponibile')
                return
            # include required fields for create
            payload['stato_salute_aggregato'] = 0
            payload['profilo_consumo_json'] = {'additionalProp1': {}}
            try:
                post_json('vascello/crea', payload)
                QMessageBox.information(self, 'OK', 'Vascello creato con successo')
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Creazione vascello fallita: {e}')

    def open_modify_dialog(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Errore', 'Seleziona un vascello da modificare')
            return
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        data = item.data(Qt.UserRole) or {}
        dlg = VascelloDialog(self, initial=data)
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            if not payload:
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client POST non disponibile')
                return
            # ensure fields per API: set stato_salute_aggregato and profilo_consumo_json as null
            payload['stato_salute_aggregato'] = None
            payload['profilo_consumo_json'] = None
            try:
                post_json('vascello/modifica', payload)
                QMessageBox.information(self, 'OK', 'Vascello modificato con successo')
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Modifica vascello fallita: {e}')

    def open_dashboard(self):
        # DEPRECATED: use _open_dashboard wrapper
        self._open_dashboard()

    def _open_dashboard(self):
        if open_dashboard is None:
            QMessageBox.warning(self, 'Errore', 'Funzione dashboard non disponibile')
            return
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, 'Errore', 'Seleziona un vascello')
            return
        item = self.table.item(row, 0)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        data = item.data(Qt.UserRole) or {}
        mmsi = data.get('mmsi') or item.text()
        open_dashboard('static/vascello.html', {'mmsi': mmsi}, title=f'Dashboard: {mmsi}', size=(1500, 800))

class VascelloDialog(QDialog):
    """Dialog per modificare (o creare) un vascello."""

    def __init__(self, parent=None, initial=None):
        super().__init__(parent)
        self.setWindowTitle('Modifica Vascello' if initial else 'Aggiungi Vascello')
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.mmsi_input = QLineEdit()
        self.nome_input = QLineEdit()
        self.pax_input = QLineEdit()
        self.costo_input = QLineEdit()
        self.vel_input = QLineEdit()
        form.addRow('MMSI:', self.mmsi_input)
        form.addRow('Nome:', self.nome_input)
        form.addRow('Capacità Pax:', self.pax_input)
        form.addRow('Costo/Ora:', self.costo_input)
        form.addRow('Velocità Max (nodi):', self.vel_input)
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
        if isinstance(initial, dict):
            self.mmsi_input.setText(str(initial.get('mmsi', '')))
            self.nome_input.setText(str(initial.get('nome', '')))
            self.pax_input.setText(str(initial.get('capacita_passeggeri', '') or ''))
            self.costo_input.setText(str(initial.get('costo_orario_esercizio', '') or ''))
            self.vel_input.setText(str(initial.get('velocita_max_nodi', '') or ''))
            self._initial_id = initial.get('id')

    def _on_next(self):
        mmsi = self.mmsi_input.text().strip()
        nome = self.nome_input.text().strip()
        pax_s = self.pax_input.text().strip()
        costo_s = self.costo_input.text().strip()
        vel_s = self.vel_input.text().strip()
        if not mmsi or not nome:
            QMessageBox.warning(self, 'Errore', 'Inserire almeno MMSI e Nome')
            return
        try:
            pax = int(pax_s) if pax_s else 0
        except Exception:
            QMessageBox.warning(self, 'Errore', 'Capacità deve essere un numero intero')
            return
        try:
            costo = float(costo_s) if costo_s else 0
        except Exception:
            QMessageBox.warning(self, 'Errore', 'Costo/Ora deve essere numerico')
            return
        try:
            vel = float(vel_s) if vel_s else 0
        except Exception:
            QMessageBox.warning(self, 'Errore', 'Velocità deve essere un numero')
            return

        self._payload = {
            'mmsi': mmsi,
            'nome': nome,
            'capacita_passeggeri': pax,
            'costo_orario_esercizio': costo,
            'velocita_max_nodi': vel,
        }
        if self._initial_id:
            self._payload['id'] = self._initial_id
        self.accept()

    def get_payload(self):
        return self._payload
