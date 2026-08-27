import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class TriadApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sonic Triad Studio - RetroKoH")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        # Basic Drag and Drop Widget (Testing)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        welcome_label = QLabel("Ready!\nDrag & Drop file(s) here")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("""
                    QLabel {
                        font-size: 16px;
                        font-weight: bold;
                        color: #A0A0A0;
                        border: 2px dashed #8088F8;
                        border-radius: 8px;
                        background-color: #181818;
                    }
                """)

        main_layout.addWidget(welcome_label)

def main():
    app = QApplication(sys.argv)

    window = TriadApp()
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
