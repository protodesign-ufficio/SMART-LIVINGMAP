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
)

# Import get_json with fallback to support different import styles
try:
    from ApiClient import get_json
except Exception:
    try:
        from project.ApiClient import get_json
    except Exception:
        get_json = None


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

        layout.addWidget(self.table)

        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(self.refresh_btn)

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
