import sys
import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor

THEMES = {
    "dark": {
        "primary": "#8088F8",
        "bg_dark": "#181818",
        "bg_medium": "#202020",
        "bg_light": "#303030",
        "text_main": "#F0F8F8",
        "text_muted": "#B8C8D0",
        "border": "#484848",
        "fusion_window": QColor(30, 30, 30),
        "fusion_base": QColor(18, 18, 18),
        "fusion_button": QColor(48, 48, 48),
    },
    "light": {
        "primary": "#5058C8",
        "bg_dark": "#E0E0E0",
        "bg_medium": "#E8E8E8",
        "bg_light": "#F8F8F8",
        "text_main": "#101828",
        "text_muted": "#586068",
        "border": "#C8C8C8",
        "fusion_window": QColor(240, 240, 240),
        "fusion_base": QColor(255, 255, 255),
        "fusion_button": QColor(224, 224, 224),
    }
}

def apply_theme(app, theme_name = "dark"):
    t = THEMES[theme_name]
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, t["fusion_window"])
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Base, t["fusion_base"])
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Button, t["fusion_button"])
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text_main"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["primary"]))
    app.setPalette(palette)

    QSS = f"""
        QLabel#dropZone {{
            font-size: 16px;
            font-weight: bold;
            color: {t["text_muted"]};
            border: 2px dashed {t["primary"]};
            border-radius: 8px;
            background-color: {t["bg_medium"]};
        }}
    """
    app.setStyleSheet(QSS)

class TriadApp(QtW.QMainWindow):
    def __init__(self, instance):
        super().__init__()
        self.app = instance
        self.current_theme = "dark"

        self.setWindowTitle("Sonic Triad Studio - RetroKoH")
        self.resize(1024, 768)
        self.setMinimumSize(800, 600)

        main_widget = QtW.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtW.QVBoxLayout(main_widget)

        # New theme toggle (temp setup)
        top_bar = QtW.QHBoxLayout()
        self.theme_btn = QtW.QPushButton("Toggle Theme")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top_bar.addStretch()
        top_bar.addWidget(self.theme_btn)
        main_layout.addLayout(top_bar)

        # Mode Tabs
        self.tabs = QtW.QTabWidget()
        main_layout.addWidget(self.tabs)

        self.projects_tab()
        self.init_tab("Palettes")
        self.init_tab("Art")
        self.init_tab("Animations")
        self.init_tab("Levels")

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        apply_theme(self.app, self.current_theme)

    def projects_tab(self):
        tab_widget = QtW.QWidget()

        dash_layout = QtW.QVBoxLayout(tab_widget)
        header_label = QtW.QLabel("Project Dashboard")
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
        drop_zone.setObjectName("dropZone")
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

    apply_theme(app, "dark")

    window = TriadApp(app)
    window.show()

    # (Without this, the window immediately closes)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
