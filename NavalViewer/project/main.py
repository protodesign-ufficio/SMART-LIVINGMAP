"""Launcher for the NavalViewer application.

This file provides a minimal entry point that imports `MainWindow` from
`main_window.py` and runs the Qt application.
"""

import sys
from PyQt5.QtWidgets import QApplication

from main_window import MainWindow


def main():
	app = QApplication(sys.argv)
	w = MainWindow()
	w.showMaximized()
	sys.exit(app.exec_())


if __name__ == '__main__':
	main()

