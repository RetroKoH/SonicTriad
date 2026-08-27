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

        self.projects_tab()
        self.init_tab("Palettes")
        self.init_tab("Art")
        self.init_tab("Animations")
        self.init_tab("Levels")

    def projects_tab(self):
        tab_widget = QtW.QWidget()

        dash_layout = QtW.QVBoxLayout(tab_widget)
        header_label = QtW.QLabel(f"Project Dashboard")
        header_label.setFixedHeight(40)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setStyleSheet(
            """
            color: #A0A0A0;
            font-size: 18px;
            font-weight: bold;
            """
        )
        dash_layout.addWidget(header_label)

        content_layout = QtW.QHBoxLayout()
        info_label = QtW.QLabel("No Project Loaded")
        info_label.setFixedWidth(200)
        info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        info_label.setStyleSheet(
            """
            color: #A0A0A0;
            font-size: 14px;
            font-weight: bold;
            """
        )
        content_layout.addWidget(info_label)

        drop_zone = QtW.QLabel("Drop Project file here")
        drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_zone.setStyleSheet(
            """
            font-size: 16px;
            font-weight: bold;
            color: #A0A0A0;
            border: 2px dashed #8088F8;
            border-radius: 8px;
            background-color: #181818;
            """
        )
        content_layout.addWidget(drop_zone)

        dash_layout.addLayout(content_layout)

        self.tabs.addTab(tab_widget, "Projects")

    def init_tab(self, tab_name):
        # for placeholder tabs
        tab_widget = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab_widget)

        label = QtW.QLabel(f"{tab_name} Editor")
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

def main():
    app = QtW.QApplication(sys.argv)

    window = TriadApp()
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
