from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QHeaderView
)

try:
    from ApiClient import get_json
except Exception:
    try:
        from project.ApiClient import get_json
    except Exception:
        get_json = None

def _format_datetime(s: str) -> str:
    if not s:
        return ''
    try:
        # Handle ISO format with potential timezone
        from datetime import datetime
        # Replace 'Z' with '+00:00' for fromisoformat compatibility if needed
        s = s.replace('Z', '+00:00')
        dt = datetime.fromisoformat(str(s))
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    except Exception:
        return str(s)

class SimulazioniPanel(QWidget):
    """Panel che mostra la lista delle simulazioni schedulate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Main horizontal layout: Table left, Controls right
        content_row = QHBoxLayout()

        # Left: Table and status label
        left_col = QVBoxLayout()
        
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels([
            'Vascello',
            'Corsa',
            'Orario Simulazione',
            'Stato Esecuzione'
        ])
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)

        left_col.addWidget(self.table)
        
        # Label per messaggi (es. "Nessuna simulazione schedulata")
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: gray; font-style: italic;")
        left_col.addWidget(self.lbl_status)
        
        content_row.addLayout(left_col)

        # Right: Parameters Group
        right_panel = QVBoxLayout()
        
        param_group = QGroupBox('Parametri')
        param_layout = QVBoxLayout()
        
        self.btn_refresh = QPushButton("Aggiorna")
        self.btn_refresh.clicked.connect(self.load_data)
        param_layout.addWidget(self.btn_refresh)
        
        param_group.setLayout(param_layout)
        right_panel.addWidget(param_group)
        right_panel.addStretch()
        
        content_row.addLayout(right_panel)
        layout.addLayout(content_row)
        
        # Load data on init
        self.load_data()

    def load_data(self):
        self.lbl_status.setText("")
        if get_json is None:
            QMessageBox.warning(self, "Errore", "Client API non disponibile")
            return

        try:
            # 1. Get scheduled simulations
            groups = get_json('/simulation/schedulate')
            
            # Gestione errore 404 o risposta dizionario con dettaglio
            if isinstance(groups, dict):
                detail = groups.get('detail', '')
                if 'Nessun file di simulazioni schedulate trovato' in detail:
                    self.lbl_status.setText("Nessuna simulazione schedulata")
                    self.table.setRowCount(0)
                    return
                elif 'error' in groups:
                     raise Exception(groups['error'])
            
            if not isinstance(groups, list):
                # Se arriviamo qui e non è una lista, trattiamolo come lista vuota o errore generico
                # Ma per sicurezza controlliamo se è None o altro
                groups = []

            # Flatten the list of results
            # Each group has "risultati": [ { ... }, ... ]
            rows_data = []
            
            for group in groups:
                results = group.get('risultati', [])
                if not isinstance(results, list):
                    continue
                    
                for res in results:
                    ass_id = res.get('assegnazione_id')
                    orario_sim = res.get('orario_simulazione')
                    
                    if not ass_id:
                        continue
                        
                    # 2. Fetch assignment details for each simulation
                    # Warning: This N+1 fetching might be slow if there are many simulations.
                    # Ideally the backend should return this info or support bulk fetch.
                    try:
                        ass_data = get_json(f'/assegnazione/{ass_id}?include=piano,percorso,corsa,vascello')
                        if not isinstance(ass_data, dict):
                            ass_data = {}
                    except Exception:
                         ass_data = {}

                    vascello = ass_data.get('vascello', {})
                    corsa = ass_data.get('corsa', {})
                    
                    nome_vascello = vascello.get('nome', 'N/D') if vascello else 'N/D'
                    nome_corsa = corsa.get('nome', 'N/D') if corsa else 'N/D'
                    stato_exec = ass_data.get('stato_esecuzione', 'N/D')

                    rows_data.append({
                        'vascello': nome_vascello,
                        'corsa': nome_corsa,
                        'orario_sim': orario_sim,
                        'stato': stato_exec,
                        'raw_res': res,
                        'raw_ass': ass_data
                    })
            
            # Sort by simulation time descending (newest first)
            rows_data.sort(key=lambda x: x['orario_sim'] or '', reverse=True)
            
            self.populate_table(rows_data)

        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile caricare simulazioni: {e}")

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            t_vascello = QTableWidgetItem(str(item['vascello']))
            t_corsa = QTableWidgetItem(str(item['corsa']))
            t_orario = QTableWidgetItem(_format_datetime(item['orario_sim']))
            t_stato = QTableWidgetItem(str(item['stato']))
            
            # Make read only
            for t in (t_vascello, t_corsa, t_orario, t_stato):
                t.setFlags(t.flags() ^ Qt.ItemIsEditable)

            self.table.setItem(row, 0, t_vascello)
            self.table.setItem(row, 1, t_corsa)
            self.table.setItem(row, 2, t_orario)
            self.table.setItem(row, 3, t_stato)

        self.table.resizeColumnsToContents()

