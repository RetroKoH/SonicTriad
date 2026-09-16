import sys
import PyQt6.QtWidgets as QtW

from UI.app_window import TriadApp
from UI.themes import apply_theme

def main():
    app = QtW.QApplication(sys.argv)

    apply_theme(app, "dark")

    window = TriadApp(app)
    #window.showMaximized()  # Temporary (To-Do: Make a preference option)
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
