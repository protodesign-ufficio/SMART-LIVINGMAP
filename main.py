"""Launcher for the LivingMap application.

This file provides a minimal entry point that imports `MainWindow` from
`main_window.py` and runs the Qt application.
"""

import sys
import os

# CONFIGURAZIONE GPU E WEBENGINE
# Usa ANGLE (DirectX su Windows) per maggiore stabilità senza sacrificare le prestazioni
os.environ["QT_OPENGL"] = "angle"
# --no-sandbox risolve molti crash "silenziosi" del processo di rendering
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox"

import queue
import requests
import ApiClient
from PyQt5.QtWidgets import QApplication, QMessageBox

from main_window import MainWindow
try:
	from consumer_dashboards import start_dashboard
except Exception:
	print("[main] consumer_dashboards.start_dashboard not available", flush=True)
	start_dashboard = None

try:
	from consumer_ais import ConsumerAIS, ConsumerSimulation
except Exception:
	print("[main] consumer_ais.ConsumerAIS not available", flush=True)
	ConsumerAIS = None
	ConsumerSimulation = None

try:
	from consumer_notification import ConsumerNotification
except Exception:
	print("[main] consumer_notification.ConsumerNotification not available", flush=True)
	ConsumerNotification = None


def handle_notification(msg):
    """Gestisce le notifiche in arrivo dal consumer."""
    try:
        msg_type = msg.get("msg_type", "notification_base")
        
        if msg_type == "replanning":
            motivo = msg.get("motivo", "Nessun motivo specificato")
            # Mostra dialog con due bottoni
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Notifica Replanning")
            msg_box.setText(f"Replanning necessario per il seguente motivo:\n{motivo}")
            
            btn_ignora = msg_box.addButton("Ignora", QMessageBox.RejectRole)
            btn_avvia = msg_box.addButton("Avvia Replanning", QMessageBox.AcceptRole)
            
            msg_box.exec_()
            
            if msg_box.clickedButton() == btn_avvia:
                print("L'utente ha scelto di avviare il replanning.", flush=True)
                # TODO Qui andrebbe la logica per avviare il replanning
            else:
                print("L'utente ha ignorato la notifica di replanning.", flush=True)
                
        else:
            # Comportamento di default: notification_base o altro
            content = msg.get("message", str(msg))
            QMessageBox.information(None, "Notifica", str(content))
            
    except Exception as e:
        print(f"Errore nella gestione della notifica: {e}", flush=True)


def main():
	
	# Verifica raggiungibilità backend
	try:
		# Timeout breve per non bloccare l'avvio troppo a lungo
		requests.get(ApiClient.BASE_URL, timeout=3)
	except Exception as e:
		QMessageBox.critical(
			None, 
			"Backend non raggiungibile", 
			f"Impossibile connettersi al server:\n{ApiClient.BASE_URL}\n\nL'applicazione verrà chiusa."
		)
		sys.exit(1)

	# start the dashboard server (non-blocking) if available
	if start_dashboard is not None:
		try:
			start_dashboard()
		except Exception:
			pass

	# prepare queue and consumer thread
	q = queue.Queue()
	consumer_ais = None
	consumer_sim = None
	consumer_replanning = None

	if ConsumerAIS is not None:
		try:
			consumer_ais = ConsumerAIS(q)
			consumer_ais.start()
		except Exception:
			consumer_ais = None

	if ConsumerSimulation is not None:
		try:
			consumer_sim = ConsumerSimulation(q)
			consumer_sim.start()
		except Exception:
			consumer_sim = None

	if ConsumerNotification is not None:
		try:
			consumer_notification = ConsumerNotification()
			# Connect signal to handle parsed messages
			consumer_notification.notificationReceived.connect(handle_notification)
			consumer_notification.start()
		except Exception:
			consumer_notification = None

	app = QApplication(sys.argv)
	w = MainWindow(queue=q)
	w.showMaximized()
	try:
		rc = app.exec_()
	finally:
		# ensure consumers stopped cleanly
		try:
			if consumer_ais is not None:
				consumer_ais.stop()
				consumer_ais.join(timeout=2)
		except Exception:
			pass
		try:
			if consumer_sim is not None:
				consumer_sim.stop()
				consumer_sim.join(timeout=2)
		except Exception:
			pass
		try:
			if consumer_notification is not None:
				consumer_notification.stop()
		except Exception:
			pass
	sys.exit(rc)


if __name__ == '__main__':
	main()

