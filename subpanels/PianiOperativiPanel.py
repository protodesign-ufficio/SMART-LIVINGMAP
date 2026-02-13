from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QMessageBox,
    QHBoxLayout,
    QSizePolicy,
    QGroupBox,
    QDialog,
    QFormLayout,
    QDateEdit,
    QComboBox,
    QLabel,
    QCheckBox,
    QSpinBox,
)

try:
    from ApiClient import get_json, post_json
except Exception:
    try:
        from project.ApiClient import get_json, post_json
    except Exception:
        get_json = None
        post_json = None

# simple in-memory caches to avoid repeated API calls
_vascello_name_cache = {}
_corsa_name_cache = {}
_percorso_cache = {}


def get_vascello_name(vascello_id):
    """Return a human-friendly vascello name for given id (falls back to id)."""
    if not vascello_id:
        return ''
    vid = str(vascello_id)
    if vid in _vascello_name_cache:
        return _vascello_name_cache[vid]
    if get_json is None:
        _vascello_name_cache[vid] = vid
        return vid
    try:
        resp = get_json(f'vascello/{vid}')
        if isinstance(resp, dict):
            name = resp.get('nome') or resp.get('name') or vid
        else:
            name = vid
    except Exception:
        name = vid
    _vascello_name_cache[vid] = str(name)
    return str(name)


def get_corsa_name_or_from_percorso(item_id):
    """Resolve a corsa name from either a corsa id or a percorso id.

    Attempts `/corsa/{id}` first; if no name, tries `/percorso/{id}` to
    obtain a `corsa_id` and then fetch the corsa.
    Falls back to the provided id on error.
    """
    if not item_id:
        return ''
    iid = str(item_id)
    if iid in _corsa_name_cache:
        return _corsa_name_cache[iid]
    if get_json is None:
        _corsa_name_cache[iid] = iid
        return iid
    # try corsa endpoint
    try:
        resp = get_json(f'corsa/{iid}')
        if isinstance(resp, dict):
            name = resp.get('nome') or resp.get('name')
            if name:
                _corsa_name_cache[iid] = str(name)
                return str(name)
    except Exception:
        pass
    # try percorso endpoint and extract corsa_id
    try:
        p = get_json(f'percorso/{iid}')
        if isinstance(p, dict):
            # cache percorso for potential later use
            _percorso_cache[iid] = p
            corsa_id = p.get('corsa_id')
            if corsa_id:
                try:
                    c = get_json(f'corsa/{corsa_id}')
                    if isinstance(c, dict):
                        name = c.get('nome') or c.get('name') or str(corsa_id)
                        _corsa_name_cache[iid] = str(name)
                        _corsa_name_cache[str(corsa_id)] = str(name)
                        return str(name)
                except Exception:
                    pass
    except Exception:
        pass
    # fallback
    _corsa_name_cache[iid] = iid
    return iid

def _format_date(s: str) -> str:
    if not s:
        return ''
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(str(s))
        return dt.strftime('%d/%m/%Y')
    except Exception:
        return str(s)
        
class PianiOperativiPanel(QWidget):
    """Panel che mostra la lista dei piani operativi da `/piano/lista`."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # top row: date selector
        top_row = QHBoxLayout()
        top_row.addWidget(QLabel('Piani Operativi per il giorno:'))
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        from PyQt5.QtCore import QDate
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self._on_date_changed)
        # slightly increase width for easier picking
        try:
            self.date_filter.setFixedWidth(140)
        except Exception:
            pass
        top_row.addWidget(self.date_filter)
        top_row.addStretch()
        layout.addLayout(top_row)

        # table columns: Data, Stato, Profitto Stimato, Robustezza, ID(hidden)
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels([
            'Data',
            'Stato',
            'Profitto Stimato',
            'Robustezza',
            'ID',
        ])
        self.table.setSelectionBehavior(self.table.SelectRows)
        self.table.setSelectionMode(self.table.SingleSelection)

        # assemble main content with right-side grouped controls
        content_row = QHBoxLayout()
        content_row.addWidget(self.table)

        right_panel = QVBoxLayout()

        # Parametri group: Aggiorna, Aggiungi, Modifica
        self.refresh_btn = QPushButton('Aggiorna')
        self.refresh_btn.clicked.connect(self.load_data)
        self.refresh_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        self.add_btn = QPushButton('Aggiungi')
        self.add_btn.clicked.connect(self.open_add_dialog)
        if post_json is None:
            self.add_btn.setEnabled(False)

        self.modify_btn = QPushButton('Modifica')
        self.modify_btn.clicked.connect(self.open_modify_dialog)
        self.modify_btn.setEnabled(False)

        param_group = QGroupBox('Parametri')
        param_layout = QVBoxLayout()
        param_layout.addWidget(self.refresh_btn)
        param_layout.addWidget(self.add_btn)
        param_layout.addWidget(self.modify_btn)
        param_group.setLayout(param_layout)
        right_panel.addWidget(param_group)

        # Servizi group: Dettagli Piano
        self.details_btn = QPushButton('Dettagli Piano')
        self.details_btn.setEnabled(False)
        self.details_btn.clicked.connect(self.open_details_dialog)
        
        self.gantt_btn = QPushButton('Gantt')
        self.gantt_btn.setEnabled(False)
        self.gantt_btn.clicked.connect(self.open_gantt_dashboard)

        serv_group = QGroupBox('Servizi')
        serv_layout = QVBoxLayout()
        serv_layout.addWidget(self.details_btn)
        serv_layout.addWidget(self.gantt_btn)
        serv_group.setLayout(serv_layout)
        right_panel.addWidget(serv_group)

        right_panel.addStretch()
        content_row.addLayout(right_panel)
        layout.addLayout(content_row)

        # load initial data for current date
        self.load_data()

    def _on_date_changed(self, qdate):
        # reload list when the selected date changes
        try:
            self.load_data()
        except Exception:
            pass

    def load_data(self):
        # use selected date from date_filter if available
        try:
            d = self.date_filter.date()
            date_str = d.toString('yyyy-MM-dd')
            # RFC-like value with midnight UTC
            query_date = f"{date_str}T00:00:00.000Z"
        except Exception:
            query_date = None

        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            path = 'piano/lista'
            if query_date:
                path = f"piano/lista?data_riferimento={query_date}"
            data = get_json(path)
            if not isinstance(data, list):
                raise ValueError('Risposta API non è una lista')
            self.populate_table(data)
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare piani: {e}')

        try:
            # connect selection change to enable/disable buttons
            self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        except Exception:
            pass

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            pid = str(item.get('id', ''))
            data_raw = item.get('data_riferimento')
            data_text = _format_date(data_raw)
            stato = str(item.get('stato', ''))
            profitto = item.get('kpi_profitto_stimato')
            profitto_text = '' if profitto is None else str(profitto)
            robustezza = item.get('kpi_robustezza')
            robustezza_text = '' if robustezza is None else str(robustezza)

            it_data = QTableWidgetItem(data_text)
            it_stato = QTableWidgetItem(stato)
            it_profitto = QTableWidgetItem(profitto_text)
            it_rob = QTableWidgetItem(robustezza_text)
            it_id = QTableWidgetItem(pid)
            it_id.setData(Qt.UserRole, item)

            for it in (it_data, it_stato, it_profitto, it_rob, it_id):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_data)
            self.table.setItem(row, 1, it_stato)
            self.table.setItem(row, 2, it_profitto)
            self.table.setItem(row, 3, it_rob)
            self.table.setItem(row, 4, it_id)

        self.table.resizeColumnsToContents()

    def open_add_dialog(self):
        dlg = AddPianoDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return

        mode, payload, search_params = dlg.get_data()

        if mode == 'manual':
            if payload is None:
                QMessageBox.warning(self, 'Errore', 'Dati non validi')
                return
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
                return
            try:
                post_json('piano/crea', payload)
                QMessageBox.information(self, 'Successo', 'Piano operativo creato')
                # reload for currently selected date
                self.load_data()
            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Creazione piano fallita: {e}')

        elif mode == 'auto':
            if post_json is None:
                QMessageBox.warning(self, 'Errore', 'Client API non disponibile per invio')
                return
            
            # 1. Chiama scheduling/giorno
            try:
                resp = post_json('scheduling/giorno', search_params)
                if not isinstance(resp, dict) or resp.get('status') != 'ok':
                    msg = resp.get('message') if isinstance(resp, dict) else 'Risposta imprevista'
                    raise ValueError(msg or 'Errore scheduling remoto')
                
                solutions = resp.get('solutions', [])
                if not solutions:
                    QMessageBox.information(self, 'Info', 'Nessuna soluzione trovata.')
                    return

                # 2. Mostra Dialog Selezione Soluzioni
                sel_dlg = SolutionsSelectionDialog(self, solutions)
                if sel_dlg.exec_() != QDialog.Accepted:
                    return
                
                selected_sols = sel_dlg.get_selected_solutions()
                if not selected_sols:
                    return

                # 3. Crea piani e assegnazioni per ogni soluzione selezionata
                count_ok = 0
                giorno_str = search_params.get('giorno')
                # costruiamo data riferimento base
                data_rif = f"{giorno_str}T00:00:00.000Z"

                for sol in selected_sols:
                    try:
                        # Crea Piano
                        plan_payload = {
                            "data_riferimento": data_rif,
                            "stato": "CREATO"
                        }
                        plan_resp = post_json('piano/crea', plan_payload)
                        if not plan_resp or 'id' not in plan_resp:
                            print(f"Errore creazione piano per solution {sol.get('solution_id')}")
                            continue
                        
                        pid = plan_resp['id']
                        activities = sol.get('activities', [])
                        
                        # Crea Assegnazioni (Bulk)
                        percorsi_list = []
                        for act in activities:
                            if act.get('route_id') is None: # TODO GESTIRE RIPOSIZIONAMENTI
                                continue
                            else:
                                percorsi_list.append({
                                    "percorso_id": act.get('route_id'),
                                    "virtuale": False
                                })

                        if percorsi_list:
                            bulk_payload = {
                                "piano_id": pid,
                                "percorsi": percorsi_list
                            }
                            post_json('assegnazione/bulk', bulk_payload)
                        
                        count_ok += 1
                        
                    except Exception as e:
                        print(f"Errore salvataggio soluzione {sol.get('solution_id')}: {e}")

                QMessageBox.information(self, 'Successo', f'Creati {count_ok} piani operativi.')
                self.load_data()

            except Exception as e:
                QMessageBox.warning(self, 'Errore', f'Procedura automatica fallita: {e}')

    def open_modify_dialog(self):
        QMessageBox.information(self, 'Modifica', 'Funzionalità Modifica da implementare')

    def _on_selection_changed(self, selected, deselected):
        has = self.table.selectionModel().hasSelection()
        try:
            self.modify_btn.setEnabled(bool(has))
        except Exception:
            pass
        try:
            self.details_btn.setEnabled(bool(has))
        except Exception:
            pass
        try:
            self.gantt_btn.setEnabled(bool(has))
        except Exception:
            pass

    def open_details_dialog(self):
        # get selected row and piano id
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessun piano selezionato')
            return
        row = sel[0].row()
        item = self.table.item(row, 4)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
        piano = item.data(Qt.UserRole) or {}
        piano_id = piano.get('id') if isinstance(piano, dict) else item.text()
        data_rif = piano.get('data_riferimento') if isinstance(piano, dict) else ''

        dlg = DettagliPianoDialog(self, piano_id=piano_id, data_riferimento=data_rif)
        dlg.exec_()
    
    def open_gantt_dashboard(self):
        # recupera piano selezionato
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.warning(self, 'Errore', 'Nessun piano selezionato')
            return
        row = sel[0].row()
        item = self.table.item(row, 4)
        if item is None:
            QMessageBox.warning(self, 'Errore', 'Elemento selezionato non valido')
            return
            
        piano = item.data(Qt.UserRole) or {}
        piano_id = piano.get('id') if isinstance(piano, dict) else item.text()
        data_rif = piano.get('data_riferimento') if isinstance(piano, dict) else ''
        
        # estrai giorno YYYY-MM-DD da data_riferimento (ISO)
        giorno_str = str(data_rif).split('T')[0] if data_rif else ''
        
        # cerca main window per aprire dashboard
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
            # try finding via QApplication
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
            QMessageBox.warning(self, 'Errore', 'Funzionalità dashboard non disponibile')
            return
            
        try:
            main.open_dashboard_embedded(
                'static/gantt/gantt.html', 
                query={'giorno': giorno_str, 'piano': str(piano_id)},
                title=f'Gantt Piano {piano_id}', 
                size=(1600, 900)
            )
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile aprire il Gantt: {e}')


class DettagliPianoDialog(QDialog):
    def __init__(self, parent=None, piano_id=None, data_riferimento=None):
        super().__init__(parent)
        self.setWindowTitle(f"Dettagli Piano Operativo: {_format_date(data_riferimento)}")
        self.resize(700, 600)
        layout = QVBoxLayout(self)

        # table for assignments with separated columns
        self.table = QTableWidget(0, 8, self)
        self.table.setHorizontalHeaderLabels([
            'Tratta', 'Partenza', 'Durata', 'Vascello', 
            'Stato Esecuzione', 'Virtuale', 'Consumo', 'Comfort'
        ])
        
        layout.addWidget(self.table)

        # load assignments
        self.load_assignments(piano_id)

        btn_row = QHBoxLayout()
        close_btn = QPushButton('Chiudi')
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def load_assignments(self, piano_id):
        if piano_id is None:
            return
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile')
            return
        try:
            path = f'assegnazione/by_piano/{piano_id}'
            data = get_json(path) or []
        except Exception as e:
            QMessageBox.warning(self, 'Errore', f'Impossibile caricare assegnazioni: {e}')
            return

        # Prepare list for sorting
        row_items = []

        for a in data:
            percorso_id = a.get('percorso_id') or ''
            vascello_id = a.get('vascello_id') or ''
            
            vascello_name = get_vascello_name(vascello_id) if vascello_id else ''
            stato = str(a.get('stato_esecuzione') or '')
            virtuale = str(a.get('virtuale', False))

            # info retrieved from expanded endpoint
            tratta_nome = "N/D"
            orario_fmt = ""
            orario_sort = ""
            tempo_str = ""
            consumo_str = ""
            comfort_str = ""

            if percorso_id:
                try:
                    # Request with includes
                    p_info = get_json(f'percorso/{percorso_id}?include=corsa,tratta,vascello')
                    if isinstance(p_info, dict):
                        # Extract info
                        tratta_obj = p_info.get('tratta') or {}
                        tratta_nome = tratta_obj.get('nome') or 'Tratta N/D'
                        
                        corsa_obj = p_info.get('corsa') or {}
                        orario_partenza = corsa_obj.get('orario_partenza_schedulato') or ''
                        orario_sort = orario_partenza
                        
                        # Format time
                        if orario_partenza:
                            orario_fmt = orario_partenza
                            if 'T' in str(orario_partenza):
                                try:
                                    from datetime import datetime
                                    dt = datetime.fromisoformat(str(orario_partenza).replace('Z', '+00:00'))
                                    orario_fmt = dt.strftime('%H:%M')
                                except Exception:
                                    pass
                        
                        tempo_val = p_info.get('tempo_percorrenza')
                        if tempo_val is not None:
                            try:
                                tempo_str = f"{float(tempo_val):.2f}"
                            except ValueError:
                                tempo_str = str(tempo_val)
                        
                        consumo_str = str(p_info.get('consumo') or '')
                        comfort_str = str(p_info.get('comfort') or '')
                        
                except Exception as e:
                    print(f"Errore recupero dettagli percorso {percorso_id}: {e}")

            row_items.append({
                'sort_key': orario_sort,
                'tratta': tratta_nome,
                'partenza': orario_fmt,
                'durata': tempo_str,
                'vascello': vascello_name,
                'stato': stato,
                'virtuale': virtuale,
                'consumo': consumo_str,
                'comfort': comfort_str
            })
            
        # Sort rows by departure time (orario_sort)
        row_items.sort(key=lambda x: x['sort_key'])

        self.table.setRowCount(0)
        for item in row_items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            it_tratta = QTableWidgetItem(item['tratta'])
            it_partenza = QTableWidgetItem(item['partenza'])
            it_durata = QTableWidgetItem(item['durata'])
            it_vas = QTableWidgetItem(item['vascello'])
            it_st = QTableWidgetItem(item['stato'])
            it_vi = QTableWidgetItem(item['virtuale'])
            it_cons = QTableWidgetItem(item['consumo'])
            it_comf = QTableWidgetItem(item['comfort'])
            
            for it in (it_tratta, it_partenza, it_durata, it_vas, it_st, it_vi, it_cons, it_comf):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_tratta)
            self.table.setItem(row, 1, it_partenza)
            self.table.setItem(row, 2, it_durata)
            self.table.setItem(row, 3, it_vas)
            self.table.setItem(row, 4, it_st)
            self.table.setItem(row, 5, it_vi)
            self.table.setItem(row, 6, it_cons)
            self.table.setItem(row, 7, it_comf)

        self.table.resizeColumnsToContents()


class AddPianoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Aggiungi Piano Operativo')
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        from PyQt5.QtCore import QDate
        self.date_edit.setDate(QDate.currentDate())

        self.assegnazione_cb = QComboBox()
        # ItemData: 'manual' o 'auto'
        self.assegnazione_cb.addItem('Singolo (Ass. Manuale)', 'manual')
        self.assegnazione_cb.addItem('Multipli (Ass. Automatica)', 'auto')
        self.assegnazione_cb.currentIndexChanged.connect(self._on_mode_changed)

        form.addRow('Data', self.date_edit)
        form.addRow('Modalità', self.assegnazione_cb)

        layout.addLayout(form)

        # Widget parametri Auto
        self.auto_widget = QWidget()
        auto_layout = QFormLayout(self.auto_widget)
        
        self.chk_future = QCheckBox("Solo Future")
        self.chk_future.setChecked(True)
        
        self.spin_max_sol = QSpinBox()
        self.spin_max_sol.setRange(1, 50)
        self.spin_max_sol.setValue(5)
        
        self.spin_eps = QSpinBox()
        self.spin_eps.setRange(0, 120)
        self.spin_eps.setValue(5)
        
        self.chk_details = QCheckBox("Includi Dettagli")
        self.chk_details.setChecked(True)
        
        self.chk_fake = QCheckBox("Fake Data")
        self.chk_fake.setChecked(False)

        auto_layout.addRow('Future', self.chk_future)
        auto_layout.addRow('Soluzioni Massime', self.spin_max_sol)
        auto_layout.addRow('Eps Time (min)', self.spin_eps)
        auto_layout.addRow('Includi Dettagli', self.chk_details)
        auto_layout.addRow('Fake Data', self.chk_fake)

        self.auto_widget.setVisible(False)
        layout.addWidget(self.auto_widget)

        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton('Crea')
        self.btn_ok.clicked.connect(self._on_ok)
        annulla = QPushButton('Annulla')
        annulla.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(annulla)
        layout.addLayout(btn_row)

        self._mode = 'manual'
        self._payload = None
        self._search_params = None

    def _on_mode_changed(self, idx):
        self._mode = self.assegnazione_cb.itemData(idx)
        is_auto = (self._mode == 'auto')
        self.auto_widget.setVisible(is_auto)
        self.btn_ok.setText('Cerca Soluzioni' if is_auto else 'Crea')
        # resize dialog to fit content
        self.adjustSize()

    def _on_ok(self):
        d = self.date_edit.date()
        date_str = d.toString('yyyy-MM-dd')
        
        if self._mode == 'manual':
            # build payload with date at midnight UTC
            data_rif = f"{date_str}T00:00:00.000Z"
            self._payload = {
                'data_riferimento': data_rif,
                'stato': 'CREATO',
            }
            self._search_params = None
        else:
            self._payload = None
            self._search_params = {
                "giorno": date_str,
                "solo_future": self.chk_future.isChecked(),
                "max_solutions": self.spin_max_sol.value(),
                "include_details": self.chk_details.isChecked(),
                "eps_time": self.spin_eps.value(),
                "fake_data": self.chk_fake.isChecked()
            }
        
        self.accept()

    def get_data(self):
        """Returns (mode, payload, search_params)"""
        return self._mode, self._payload, self._search_params


class SolutionsSelectionDialog(QDialog):
    def __init__(self, parent=None, solutions=None):
        super().__init__(parent)
        self.setWindowTitle('Risultati Scheduling Automatico')
        self.resize(500, 400)
        self.solutions = solutions or []

        layout = QVBoxLayout(self)
        
        lbl = QLabel(f"Trovate {len(self.solutions)} soluzioni. Seleziona quelle da salvare come Piani Operativi:")
        layout.addWidget(lbl)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(['Seleziona', 'Costo', 'Rischio', 'N. Attività'])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        self.populate()

        btn_row = QHBoxLayout()
        ok_btn = QPushButton('Salva Selezionati')
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton('Annulla')
        cancel_btn.clicked.connect(self.reject)
        
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def populate(self):
        self.table.setRowCount(0)
        for sol in self.solutions:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox item
            it_check = QTableWidgetItem()
            it_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            it_check.setCheckState(Qt.Unchecked)
            # Store full solution object
            it_check.setData(Qt.UserRole, sol)

            cost = str(sol.get('cost', ''))
            risk = str(sol.get('risk', ''))
            n_acts = str(len(sol.get('activities', [])))

            it_cost = QTableWidgetItem(cost)
            it_risk = QTableWidgetItem(risk)
            it_n = QTableWidgetItem(n_acts)
            
            for it in (it_cost, it_risk, it_n):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)

            self.table.setItem(row, 0, it_check)
            self.table.setItem(row, 1, it_cost)
            self.table.setItem(row, 2, it_risk)
            self.table.setItem(row, 3, it_n)

        self.table.resizeColumnsToContents()

    def get_selected_solutions(self):
        selected = []
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it.checkState() == Qt.Checked:
                selected.append(it.data(Qt.UserRole))
        return selected
