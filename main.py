import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow
import db

def main():
    db.init()
    app = QApplication(sys.argv)

    # Optional: Set app style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
