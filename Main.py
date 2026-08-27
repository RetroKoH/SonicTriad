import sys
import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

class TriadApp(QtW.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sonic Triad Studio - RetroKoH")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        # Mode Tabs
        self.tabs = QtW.QTabWidget()
        self.setCentralWidget(self.tabs)

        self.init_tab("Project")
        self.init_tab("Palettes")
        self.init_tab("Art")
        self.init_tab("Animations")
        self.init_tab("Levels")

    def init_tab(self, tab_name):
        # for placeholder tabs
        tab_widget = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab_widget)

        label = QtW.QLabel(f"{tab_name} Mode Workspace")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            """
            color: #A0A0A0;
            font-size: 18px;
            font-weight: bold;
            """
        )

        layout.addWidget(label)
        self.tabs.addTab(tab_widget, tab_name)

        # Temporarily removing Drag/Drop stuff
        """# Basic Drag and Drop Widget (Testing)
        central_widget = QtW.QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QtW.QVBoxLayout()
        central_widget.setLayout(main_layout)

        welcome_label = QtW.QLabel("Ready!\nDrag & Drop file(s) here")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet(
                    QLabel {
                        font-size: 16px;
                        font-weight: bold;
                        color: #A0A0A0;
                        border: 2px dashed #8088F8;
                        border-radius: 8px;
                        background-color: #181818;
                    }
                )

        main_layout.addWidget(welcome_label)"""

def main():
    app = QtW.QApplication(sys.argv)

    window = TriadApp()
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
