"""Launcher for the NavalViewer application.

This file provides a minimal entry point that imports `MainWindow` from
`main_window.py` and runs the Qt application.
"""

import sys
from PyQt5.QtWidgets import QApplication

from main_window import MainWindow
try:
	# start dashboard in background when launching GUI
	from consumer_dashboards import start_dashboard
except Exception:
	start_dashboard = None


def main():
	# start the dashboard server (non-blocking) if available
	if start_dashboard is not None:
		try:
			start_dashboard()
		except Exception:
			pass

	app = QApplication(sys.argv)
	w = MainWindow()
	w.showMaximized()
	sys.exit(app.exec_())


if __name__ == '__main__':
	main()

