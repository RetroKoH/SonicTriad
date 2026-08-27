import sys
from PyQt6.QtWidgets import QApplication, QMainWindow

class TriadApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sonic Triad Studio - RetroKoH")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

def main():
    app = QApplication(sys.argv)

    window = TriadApp()
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
