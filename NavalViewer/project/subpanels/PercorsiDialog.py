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

# Import get_json with fallback like other modules
try:
    from ApiClient import get_json
except Exception:
    try:
        from project.ApiClient import get_json
    except Exception:
        get_json = None


class PercorsiDialog(QDialog):
    """Dialog che mostra informazioni principali di una corsa.

    Mostra un `QLabel` con: Tratta, Data, Orario, Previsione Biglietti.
    I dettagli vengono recuperati da `/corsa/{corsa_id}`.
    """
    def __init__(self, parent=None, corsa=None):
        super().__init__(parent)
        self.setWindowTitle('Dettagli Percorsi')
        # set default dialog size
        self.resize(800,0)
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

                tratta = data.get('tratta_id', '')
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
                info_text = f'Impossibile recuperare dettagli corsa: {e}'

        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # table of percorsi
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            'Tempo Percorrenza',
            'Consumo',
            'P_Ref',
            'V_Ref',
            'Geom. Rotta',
            'ID',
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        # make cells non-editable
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.table)

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
            pref = p.get('pref', '')
            vref = p.get('vref', '')
            geom = p.get('geom_rotta', '')
            pid = p.get('id', '')

            it_tempo = QTableWidgetItem(str(tempo))
            it_consumo = QTableWidgetItem(str(consumo))
            it_pref = QTableWidgetItem(str(pref))
            it_vref = QTableWidgetItem(str(vref))
            it_geom = QTableWidgetItem(str(geom))
            it_id = QTableWidgetItem(str(pid))

            # store full percorso object in ID column user role
            it_id.setData(Qt.UserRole, p)

            for it in (it_tempo, it_consumo, it_pref, it_vref, it_geom, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_tempo)
            self.table.setItem(row, 1, it_consumo)
            self.table.setItem(row, 2, it_pref)
            self.table.setItem(row, 3, it_vref)
            self.table.setItem(row, 4, it_geom)
            self.table.setItem(row, 5, it_id)

        # resize columns
        self.table.resizeColumnsToContents()
