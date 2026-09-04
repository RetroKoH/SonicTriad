from UI.themes import THEMES
import PyQt6.QtWidgets as QtW

class SpriteEditor(QtW.QWidget):
    def __init__(self):
        super().__init__()

        self.init_ui()

    def init_ui(self):
        main_layout = QtW.QHBoxLayout(self)

        # -----------------------------
        # LEFT PANEL: Sprite Selection, Viewer, Data
        # -----------------------------
        left_panel = QtW.QVBoxLayout()

        # Sprite Build Dropdown
        self.spr_select_group = QtW.QGroupBox("Select Sprite")
        spr_select_layout = QtW.QHBoxLayout(self.spr_select_group)

        self.spr_dropdown = QtW.QComboBox()
        self.spr_dropdown.setToolTip("Select a sprite build from the active project")
        #self.spr_dropdown.currentIndexChanged.connect(self.on_spr_dropdown_changed)
        spr_select_layout.addWidget(self.spr_dropdown, stretch=1)

        # File Buttons
        btn_layout = QtW.QHBoxLayout()
        btn_layout.setSpacing(4)

        btn_new = QtW.QPushButton("New")
        btn_load = QtW.QPushButton("Load")
        btn_save = QtW.QPushButton("Save")
        btn_saveas = QtW.QPushButton("Save As...")
        btn_remove = QtW.QPushButton("Remove")
        for btn in (btn_new, btn_load, btn_save, btn_saveas, btn_remove):
            btn.setFixedWidth(55)

        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_saveas)
        btn_layout.addWidget(btn_remove)

        spr_select_layout.addLayout(btn_layout)
        left_panel.addWidget(self.spr_select_group)

        # Sprite Viewer
        sprite_box = QtW.QGroupBox("Sprite Viewer")
        sprite_viewer = QtW.QVBoxLayout(sprite_box)

        # Scroll area in case built sprite extends past the window border
        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        # Ensure that sprite mappings can render in this space (Add ruler widget)

        scroll_area.setWidget(scroll_content)
        sprite_viewer.addWidget(scroll_area)

        left_panel.addWidget(sprite_box, stretch=2)

        # Sprite File Manager
        self.spr_file_group = QtW.QGroupBox("Sprite Data and Files")
        spr_file_layout = QtW.QVBoxLayout(self.spr_file_group)

        spr_file_header_layout = QtW.QHBoxLayout()
        self.btn_clear_sprfile = QtW.QPushButton("Clear Sprite Data")
        self.btn_clear_sprfile.setFixedWidth(110)
        #self.btn_clear_clipboard.clicked.connect(self.clear_clipboard)
        spr_file_header_layout.addStretch()
        spr_file_header_layout.addWidget(self.btn_clear_sprfile)

        spr_file_layout.addLayout(spr_file_header_layout)

        # Put file-related elements (text box, load/save buttons) here
        # I'll also include a scrollbar on the right side of this area

        left_panel.addWidget(self.spr_file_group, stretch=1)

        main_layout.addLayout(left_panel, stretch=2)

        # -----------------------------
        # RIGHT PANEL: Editing Controls
        # -----------------------------
        right_panel = QtW.QVBoxLayout()
        main_layout.addLayout(right_panel, stretch=1)