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

from datetime import datetime, timedelta

def _format_datetime(s) -> str:
    if not s:
        return ''
    if isinstance(s, datetime):
        return s.strftime('%d/%m/%Y %H:%M:%S')
    try:
        # Replace 'Z' with '+00:00' for fromisoformat compatibility if needed
        s_str = str(s).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s_str)
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
        
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            'Vascello',
            'Corsa',
            'Orario Inizio Simulazione',
            'Orario Fine Simulazione',
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
        
        param_group = QGroupBox('Anagrafica')
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
            # 1. Get Simulation Settings (Speed Factor)
            try:
                sim_config = get_json('/api/config/kafka-settings')
                if isinstance(sim_config, dict):
                    sim_speed_factor = float(sim_config.get('sim_speed_factor', 1))
                else:
                    sim_speed_factor = 1.0
            except Exception:
                sim_speed_factor = 1.0
            
            # Avoid division by zero
            if sim_speed_factor <= 0:
                sim_speed_factor = 1.0

            # 2. Get scheduling info
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
                        
                    # 3. Fetch assignment details for each simulation
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
                    percorso = ass_data.get('percorso', {})
                    
                    nome_vascello = vascello.get('nome', 'N/D') if vascello else 'N/D'
                    nome_corsa = corsa.get('nome', 'N/D') if corsa else 'N/D'
                    stato_exec = ass_data.get('stato_esecuzione', 'N/D')

                    orario_fine = None
                    # Calculate end time if we have start time and duration
                    if orario_sim and percorso:
                        try:
                            # Parse duration in minutes
                            durata_min = float(percorso.get('tempo_percorrenza', 0) or 0)
                            if durata_min > 0:
                                # Parse start time
                                s_start = str(orario_sim).replace('Z', '+00:00')
                                dt_start = datetime.fromisoformat(s_start)
                                
                                # Scale duration by speed factor
                                durata_scalata = durata_min / sim_speed_factor
                                
                                # Add duration
                                result_dt = dt_start + timedelta(minutes=durata_scalata)
                                orario_fine = result_dt
                        except Exception:
                            # In case of parsing errors, just leave as None/empty
                            pass

                    rows_data.append({
                        'vascello': nome_vascello,
                        'corsa': nome_corsa,
                        'orario_sim': orario_sim,
                        'orario_fine': orario_fine,
                        'stato': stato_exec,
                        'raw_res': res,
                        'raw_ass': ass_data
                    })
            
            # Sort by simulation time ascending (oldest first)
            rows_data.sort(key=lambda x: x['orario_sim'] or '')
            
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
            t_orario_inizio = QTableWidgetItem(_format_datetime(item['orario_sim']))
            t_orario_fine = QTableWidgetItem(_format_datetime(item['orario_fine']) if item['orario_fine'] else "")
            t_stato = QTableWidgetItem(str(item['stato']))
            
            # Make read only
            for t in (t_vascello, t_corsa, t_orario_inizio, t_orario_fine, t_stato):
                t.setFlags(t.flags() ^ Qt.ItemIsEditable)

            self.table.setItem(row, 0, t_vascello)
            self.table.setItem(row, 1, t_corsa)
            self.table.setItem(row, 2, t_orario_inizio)
            self.table.setItem(row, 3, t_orario_fine)
            self.table.setItem(row, 4, t_stato)

        self.table.resizeColumnsToContents()

