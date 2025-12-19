from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
)

# Import get_json and post_json with fallback
try:
    from ApiClient import get_json, post_json
except Exception:
    try:
        from project.ApiClient import get_json, post_json
    except Exception:
        get_json = None
        post_json = None


class OptimizationDialog(QDialog):
    """Dialog per creare/avviare un'ottimizzazione: nome, corsa e vascello."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Ottimizzazione Percorsi')
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.corsa_cb = QComboBox()
        self.vascello_cb = QComboBox()

        form.addRow('Nome Ottimizzazione', self.name_edit)
        form.addRow('Corsa', self.corsa_cb)
        form.addRow('Vascello', self.vascello_cb)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton('Avvia Ottimizzazione')
        self.start_btn.clicked.connect(self.start_optimization)
        cancel = QPushButton('Annulla')
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

        # carica le opzioni per corsa e vascello
        self.load_choices()

    def load_choices(self):
        if get_json is None:
            QMessageBox.warning(self, 'Errore', 'Client API non disponibile per caricare liste')
            return
        try:
            corsa_list = get_json('corsa/lista') or []
        except Exception:
            corsa_list = []
        try:
            vascello_list = get_json('vascello/lista') or []
        except Exception:
            vascello_list = []

        self.corsa_cb.clear()
        for c in corsa_list:
            if isinstance(c, dict):
                cid = str(c.get('id', ''))
            else:
                cid = str(c)
            # store id as userData so we can display friendly text later if needed
            self.corsa_cb.addItem(cid, cid)

        self.vascello_cb.clear()
        for v in vascello_list:
            if isinstance(v, dict):
                vid = str(v.get('id', ''))
                # prefer Italian 'nome' then 'name' then id
                name = v.get('nome') or v.get('name') or vid
            else:
                vid = str(v)
                name = vid
            # show the vessel name but store the id as userData
            self.vascello_cb.addItem(str(name), vid)

    def start_optimization(self):
        name = self.name_edit.text().strip()
        # retrieve the ids from the combo userData, fallback to text
        corsa_id = self.corsa_cb.currentData() or self.corsa_cb.currentText()
        vascello_id = self.vascello_cb.currentData() or self.vascello_cb.currentText()
        if not name:
            QMessageBox.warning(self, 'Errore', 'Inserisci il Nome Ottimizzazione')
            return
        if not corsa_id:
            QMessageBox.warning(self, 'Errore', 'Seleziona una corsa')
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
            resp = post_json('ottimizzatore', payload)
            progress.close()
            QMessageBox.information(self, 'Successo', 'Ottimizzazione Riuscita')
            self.accept()
        except Exception as e:
            progress.close()
            QMessageBox.warning(self, 'Errore', f'Ottimizzazione fallita: {e}')


class ServiziPanel(QWidget):
    """Panel dei servizi con funzione di avvio ottimizzazioni."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel('Ottimizzazione Percorsi'))
        opt_btn = QPushButton('Ottimizzazione')
        opt_btn.clicked.connect(self.open_optimization_dialog)
        row.addWidget(opt_btn)
        row.addStretch()

        layout.addLayout(row)

    def open_optimization_dialog(self):
        dlg = OptimizationDialog(self)
        dlg.exec_()
