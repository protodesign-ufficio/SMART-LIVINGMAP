"""Launcher for the LivingMap application.

This file provides a minimal entry point that imports `MainWindow` from
`main_window.py` and runs the Qt application.
"""

import sys
import queue
import requests
import ApiClient
from PyQt5.QtWidgets import QApplication, QMessageBox
# import os
# os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'

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
	consumer = None
	consumer_sim = None

	if ConsumerAIS is not None:
		try:
			consumer = ConsumerAIS(q)
			consumer.start()
		except Exception:
			consumer = None

	if ConsumerSimulation is not None:
		try:
			consumer_sim = ConsumerSimulation(q)
			consumer_sim.start()
		except Exception:
			consumer_sim = None

	app = QApplication(sys.argv)
	w = MainWindow(queue=q)
	w.showMaximized()
	try:
		rc = app.exec_()
	finally:
		# ensure consumers stopped cleanly
		try:
			if consumer is not None:
				consumer.stop()
				consumer.join(timeout=2)
		except Exception:
			pass
		try:
			if consumer_sim is not None:
				consumer_sim.stop()
				consumer_sim.join(timeout=2)
		except Exception:
			pass
	sys.exit(rc)


if __name__ == '__main__':
	main()

