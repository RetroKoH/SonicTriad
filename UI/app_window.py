import json
from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt

from UI.themes import apply_theme
from Editors.palettes import PaletteEditor

class TriadApp(QtW.QMainWindow):
    def __init__(self, instance):
        super().__init__()
        self.app = instance
        self.current_theme = "dark"
        self.active_project_data = None
        self.project_root_dir = None

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

        self.palette_editor = PaletteEditor()
        self.tabs.addTab(self.palette_editor, "Palettes")

        self.init_tab("Art")
        self.init_tab("Animations")
        self.init_tab("Levels")

        status_label = QtW.QLabel("Status: Idle")
        status_label.setFixedHeight(25)
        main_layout.addWidget(status_label)

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        apply_theme(self.app, self.current_theme)

    def projects_tab(self):
        tab_widget = QtW.QWidget()

        dash_layout = QtW.QVBoxLayout(tab_widget)
        header_label = QtW.QLabel("Project Dashboard")
        header_label.setFixedHeight(40)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setObjectName("headerLabel")
        dash_layout.addWidget(header_label)

        content_layout = QtW.QHBoxLayout()
        self.info_label = QtW.QLabel("No Project Loaded")
        self.info_label.setFixedWidth(200)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.info_label.setObjectName("infoLabel")
        content_layout.addWidget(self.info_label)

        self.drop_zone = DropWidget(self, "Drop Project file here (.json)")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setObjectName("dropZone")
        content_layout.addWidget(self.drop_zone)

        dash_layout.addLayout(content_layout)

        self.tabs.addTab(tab_widget, "Projects")

    def init_tab(self, tab_name):
        # for placeholder tabs
        tab_widget = QtW.QWidget()
        layout = QtW.QVBoxLayout(tab_widget)

        header_label = QtW.QLabel(f"{tab_name} Editor")
        header_label.setFixedHeight(40)
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_label.setObjectName("headerLabel")
        layout.addWidget(header_label)
        self.tabs.addTab(tab_widget, tab_name)

    def load_project_file(self, json_path_str):
        json_path = Path(json_path_str)

        # Root disassembly directory is that of the project file
        self.project_root_dir = json_path.parent

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                self.active_project_data = json.load(f)

            # Resolve relative paths against disassembly directory
            rom_path = self.project_root_dir / self.active_project_data.get("rom_path", "")

            raw_palettes = self.active_project_data.get("palettes", [])
            resolved_palettes = [self.project_root_dir / p for p in raw_palettes]

            assembler = self.active_project_data.get("settings", {}).get("assembler", "N/A")

            # Update UI Labels
            proj_name = self.active_project_data.get("project_name", "Unnamed Project")

            # To-Do: Relocate or remove the root directory string
            self.info_label.setText(
                f"<b>Project:</b> {proj_name}<br><br>"
                f"<b>Root:</b><br>{self.project_root_dir}<br><br>"

                f"<b>ROM:</b><br>{rom_path.name}<br>"
                f"<i>(Exists: {rom_path.exists()})</i><br><br>"

                f"<b>Assembler:</b> {assembler}"
            )

            self.drop_zone.setText(
                f"Loaded Project: {proj_name}\n\n"
                f"Drag & Drop another .json file to switch"
            )

            # Populate Palettes Tab dropdown with project files
            self.palette_editor.populate_palette_list(resolved_palettes)

        except Exception as e:
            self.info_label.setText(f"Error loading project:\n{str(e)}")

class DropWidget(QtW.QLabel):
    def __init__(self, app, text=""):
        super().__init__(text)
        self.app = app
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0):
        if a0 is None:
            return

        if a0.mimeData().hasUrls():
            # Check if at least one dragged file ends with .json
            for url in a0.mimeData().urls():
                if url.toLocalFile().lower().endswith(".json"):
                    a0.acceptProposedAction()
                    return
        a0.ignore()

    def dropEvent(self, a0):
        if a0 is None:
            return

        for url in a0.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".json"):
                self.app.load_project_file(file_path)
                a0.acceptProposedAction()
                break
