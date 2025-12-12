from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


class ServiziPanel(QWidget):
    """Placeholder panel for Services configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Placeholder: pannello Servizi'))
