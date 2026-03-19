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
    QComboBox,
    QGroupBox,
    QAbstractItemView,
    QLabel,
    QDoubleSpinBox,
    QTextEdit
)
import json

try:
    from ApiClient import get_json, post_json, BASE_URL
except ImportError:
    try:
        from project.ApiClient import get_json, post_json, BASE_URL
    except ImportError:
        get_json = None
        post_json = None
        BASE_URL = "http://87.26.178.190:25080/"


class ComponentiPanel(QWidget):
    """
    Pannello per la gestione dei componenti associati a un vascello.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # -- Filtro Vascello --
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Seleziona Vascello:"))
        self.combo_vascelli = QComboBox()
        self.combo_vascelli.currentIndexChanged.connect(self.on_vascello_changed)
        filter_layout.addWidget(self.combo_vascelli)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # -- Table --
        content_row = QHBoxLayout()
        
        self.table = QTableWidget(0, 6, self)
        self.table.setHorizontalHeaderLabels([
            "Nome Componente",
            "Sottosistema",
            "Ore Utilizzo",
            "Soglia Manutenzione",
            "Modello Guasto",
            "ID"
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        
        content_row.addWidget(self.table)

        # -- Right Panel (Buttons) --
        right_panel = QVBoxLayout()
        
        # Group Anagrafica
        grp_ana = QGroupBox("Anagrafica")
        vbox_ana = QVBoxLayout()
        
        self.btn_aggiorna = QPushButton("Aggiorna")
        self.btn_aggiorna.clicked.connect(self.on_vascello_changed and self.load_vascelli) # Reload current
        vbox_ana.addWidget(self.btn_aggiorna)

        self.btn_add = QPushButton("Aggiungi")
        self.btn_add.clicked.connect(self.open_add_dialog)
        vbox_ana.addWidget(self.btn_add)

        self.btn_mod = QPushButton("Modifica")
        self.btn_mod.setEnabled(False)
        self.btn_mod.clicked.connect(self.open_modify_dialog)
        vbox_ana.addWidget(self.btn_mod)

        self.btn_del = QPushButton("Elimina")
        self.btn_del.setEnabled(False)
        self.btn_del.clicked.connect(self.delete_component)
        vbox_ana.addWidget(self.btn_del)

        grp_ana.setLayout(vbox_ana)
        right_panel.addWidget(grp_ana)
        right_panel.addStretch()

        content_row.addLayout(right_panel)
        layout.addLayout(content_row)

        self._vascelli_map = [] 
        self.load_vascelli()

    def load_vascelli(self):
        if get_json is None:
            return
        try:
            items = get_json('vascello/lista')
            self.combo_vascelli.blockSignals(True)
            self.combo_vascelli.clear()
            self._vascelli_map = []
            
            for v in items:
                v_id = v.get('id')
                v_nome = v.get('nome', '???')
                self.combo_vascelli.addItem(v_nome, v_id)
                self._vascelli_map.append(v)
            
            self.combo_vascelli.blockSignals(False)
            
            if self.combo_vascelli.count() > 0:
                self.combo_vascelli.setCurrentIndex(0)
                self.on_vascello_changed() # Force load
            else:
                self.table.setRowCount(0)
                
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile caricare vascelli: {e}")

    def on_vascello_changed(self):
        v_id = self.combo_vascelli.currentData()
        if v_id:
            self.load_componenti(v_id)
        else:
            self.table.setRowCount(0)

    def load_componenti(self, vascello_id):
        if not vascello_id:
            return
        try:
            endpoint = f'componente/{vascello_id}'
            data = get_json(endpoint)
            # API returns list on success
            if not isinstance(data, list):
                data = []

            self.populate_table(data)
        except Exception as e:
            print(f"Errore caricamento componenti: {e}")
            self.table.setRowCount(0)

    def populate_table(self, items):
        self.table.setRowCount(0)
        for item in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            nome = str(item.get('nome_componente', ''))
            sott = str(item.get('sottosistema', ''))
            ore = str(item.get('ore_utilizzo_totali', 0))
            soglia = str(item.get('soglia_manutenzione', 0))
            mg_json = item.get('modello_guasto_json', {})
            # Rappresentazione sintetica del json
            mg_str = json.dumps(mg_json) if mg_json else "{}"
            c_id = str(item.get('id', ''))

            it_nome = QTableWidgetItem(nome)
            it_nome.setData(Qt.UserRole, item) # Store full object
            
            self.table.setItem(row, 0, it_nome)
            self.table.setItem(row, 1, QTableWidgetItem(sott))
            self.table.setItem(row, 2, QTableWidgetItem(ore))
            self.table.setItem(row, 3, QTableWidgetItem(soglia))
            self.table.setItem(row, 4, QTableWidgetItem(mg_str))
            self.table.setItem(row, 5, QTableWidgetItem(c_id))
            
            # ReadOnly
            for c in range(6):
                it = self.table.item(row, c)
                if it:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)

        self.table.resizeColumnsToContents()
        self._on_selection_changed(None, None)

    def _on_selection_changed(self, selected, deselected):
        has_sel = self.table.selectionModel().hasSelection()
        self.btn_mod.setEnabled(has_sel)
        self.btn_del.setEnabled(has_sel)

    def open_add_dialog(self):
        v_id = self.combo_vascelli.currentData()
        if not v_id:
            QMessageBox.warning(self, "Attenzione", "Selezionare un vascello prima.")
            return

        dlg = ComponenteDialog(self, initial=None, vascello_id=v_id)
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            try:
                post_json('componente/crea', payload)
                self.load_componenti(v_id)
                QMessageBox.information(self, "Info", "Componente creato con successo.")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Creazione fallita: {e}")

    def open_modify_dialog(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 0)
        data = item.data(Qt.UserRole)
        
        # Pass existing data
        dlg = ComponenteDialog(self, initial=data, vascello_id=data.get('vascello_id'))
        if dlg.exec_() == QDialog.Accepted:
            payload = dlg.get_payload()
            # Add ID for update
            payload['id'] = data.get('id')
            try:
                post_json('componente/modifica', payload)
                self.on_vascello_changed() # Refresh
                QMessageBox.information(self, "Info", "Componente modificato con successo.")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Modifica fallita: {e}")

    def delete_component(self):
        row = self.table.currentRow()
        if row < 0: return
        item = self.table.item(row, 0)
        data = item.data(Qt.UserRole)
        c_id = data.get('id')
        
        res = QMessageBox.question(self, "Conferma", f"Eliminare componente {data.get('nome_componente')}?", 
                                   QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            try:
                # Use POST instead of DELETE since the server returns 405 Method Not Allowed for DELETE
                post_json('componente/elimina', {"id": c_id})
                self.on_vascello_changed() # Refresh
                QMessageBox.information(self, "Info", "Componente eliminato.")
            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Eliminazione fallita: {e}")


class ComponenteDialog(QDialog):
    def __init__(self, parent=None, initial=None, vascello_id=None):
        super().__init__(parent)
        self.setWindowTitle("Componente")
        self.resize(500, 450)
        self.vascello_id = vascello_id
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.txt_nome = QLineEdit()
        self.txt_sott = QLineEdit()
        self.spin_ore = QDoubleSpinBox()
        self.spin_ore.setMaximum(999999.0)
        self.spin_soglia = QDoubleSpinBox()
        self.spin_soglia.setMaximum(999999.0)
        
        # Modello guasto fields - using QTextEdit
        self.txt_mg_json = QTextEdit()
        self.txt_mg_json.setPlaceholderText('Inserisci JSON Modello Guasto')
        
        form.addRow("Nome Componente:", self.txt_nome)
        form.addRow("Sottosistema:", self.txt_sott)
        form.addRow("Ore Utilizzo:", self.spin_ore)
        form.addRow("Soglia Manutenzione:", self.spin_soglia)
        
        grp_mg = QGroupBox("Modello Guasto (JSON)")
        layout_mg = QVBoxLayout()
        layout_mg.addWidget(self.txt_mg_json)
        grp_mg.setLayout(layout_mg)
        
        layout.addLayout(form)
        layout.addWidget(grp_mg)
        
        btns = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.check_and_accept)
        cancel_btn = QPushButton("Annulla")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        # Default JSON structure
        default_json = {
            "scale": 2200,
            "shape": 1.8,
            "type": "weibull"
        }
        
        if initial:
            self.txt_nome.setText(str(initial.get('nome_componente') or ''))
            self.txt_sott.setText(str(initial.get('sottosistema') or ''))
            self.spin_ore.setValue(float(initial.get('ore_utilizzo_totali') or 0))
            self.spin_soglia.setValue(float(initial.get('soglia_manutenzione') or 0))
            
            mg = initial.get('modello_guasto_json', {})
            if isinstance(mg, str):
                try: mg = json.loads(mg)
                except: mg = {}
            if mg is None: mg = {}
            
            if mg:
                self.txt_mg_json.setText(json.dumps(mg, indent=2))
            else:
                 self.txt_mg_json.setText(json.dumps(default_json, indent=2))
            
            if 'vascello_id' in initial and initial['vascello_id']:
                self.vascello_id = initial['vascello_id']
        else:
             self.txt_mg_json.setText(json.dumps(default_json, indent=2))

    def check_and_accept(self):
        try:
            txt = self.txt_mg_json.toPlainText()
            if not txt.strip():
                 self.txt_mg_json.setText("{}")
            else:
                 json.loads(txt)
            self.accept()
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Errore JSON", f"Il JSON del modello guasto non è valido:\n{e}")

    def get_payload(self):
        try:
            mg_json = json.loads(self.txt_mg_json.toPlainText())
        except:
            mg_json = {}
        
        return {
            "vascello_id": self.vascello_id,
            "nome_componente": self.txt_nome.text(),
            "sottosistema": self.txt_sott.text(),
            "ore_utilizzo_totali": self.spin_ore.value(),
            "soglia_manutenzione": self.spin_soglia.value(),
            "modello_guasto_json": mg_json
        }
