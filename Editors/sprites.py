from pathlib import Path

from UI.themes import THEMES

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

# Note: The editor uses inaccurate colors because I need to migrate constants and functions
#       from the Palette Editor file its own file that both editors (and others) can access.

class MiniColorBox(QtW.QFrame):
    def __init__(self, index, color=QColor(0, 0, 0), size=18):
        super().__init__()
        self.index = index
        self.color = color
        self.setFixedSize(size, size)
        self.update_style()

    def set_color(self, color: QColor):
        self.color = color
        self.update_style()

    def update_style(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color.name()};
                border: none;
                border-radius: 0px;
            }}
        """)

class SpriteEditor(QtW.QWidget):
    def __init__(self):
        super().__init__()

        # 64 color palette (4 palette lines) for sprite rendering
        self.palette_boxes = []
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]

        # These are used in the palette file manager
        self.pal_rows = []  # Stores (path_input, line_combo) for palette loading
        self.pal_line_combos = []

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
        btn_clear = QtW.QPushButton("Clear")
        btn_remove = QtW.QPushButton("Remove")
        for btn in (btn_new, btn_load, btn_save, btn_clear, btn_remove):
            btn.setFixedWidth(55)

        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_clear)
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

        # File-related elements here
        data_tabs = QtW.QTabWidget()

        # Art sub-tab
        art_tab = QtW.QWidget()
        art_layout = QtW.QVBoxLayout(art_tab)
        art_layout.addWidget(QtW.QLabel("Art Tile Configuration"))
        # Add file paths, load/save buttons, and scrollable controls here
        data_tabs.addTab(art_tab, "Art")

        # *** MAPPINGS SUB-TAB ***
        mappings_tab = QtW.QWidget()
        mappings_layout = QtW.QVBoxLayout(mappings_tab)
        mappings_layout.addWidget(QtW.QLabel("Sprite Mappings / DPLC Definitions"))
        # Add mapping assembly file options here
        data_tabs.addTab(mappings_tab, "Mappings")

        # *** PALETTES SUB-TAB ***
        palettes_tab = QtW.QWidget()
        palettes_layout = QtW.QHBoxLayout(palettes_tab)

        # Buttons (I'm going to try to model this after Flex 2)
        pal_btn_layout = QtW.QVBoxLayout()
        pal_btn_layout.setSpacing(12)
        pal_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_pal_add = QtW.QPushButton("Add")
        self.btn_pal_load = QtW.QPushButton("Load")
        self.btn_pal_save = QtW.QPushButton("Save")

        for btn in (self.btn_pal_add, self.btn_pal_load, self.btn_pal_save):
            btn.setFixedWidth(60)
            pal_btn_layout.addWidget(btn)

        # Load/Save are disabled by default until palettes are added
        self.btn_pal_load.setEnabled(False)
        self.btn_pal_save.setEnabled(False)

        self.btn_pal_add.clicked.connect(self.on_pal_add_clicked)
        self.btn_pal_load.clicked.connect(self.on_pal_load_clicked)
        self.btn_pal_save.clicked.connect(self.on_pal_save_clicked)

        palettes_layout.addLayout(pal_btn_layout)

        # Dynamic entry container
        pal_entries_scroll = QtW.QScrollArea()
        pal_entries_scroll.setWidgetResizable(True)

        self.pal_entries_widget = QtW.QWidget()
        self.pal_entries_layout = QtW.QVBoxLayout(self.pal_entries_widget)
        self.pal_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pal_entries_scroll.setWidget(self.pal_entries_widget)
        palettes_layout.addWidget(pal_entries_scroll, stretch=1)

        data_tabs.addTab(palettes_tab, "Palettes")
        # ************************

        spr_file_layout.addWidget(data_tabs)
        left_panel.addWidget(self.spr_file_group, stretch=1)

        main_layout.addLayout(left_panel, stretch=2)

        # -----------------------------
        # RIGHT PANEL: Editing Controls
        # -----------------------------
        right_panel = QtW.QVBoxLayout()

        # Sprite Palette
        spr_palette_group = QtW.QGroupBox("Palette")
        spr_palette_layout = QtW.QVBoxLayout(spr_palette_group)

        # 64-Color VDP Palette Grid (4 Lines x 16 Swatches)
        pal_grid_container = QtW.QWidget()
        pal_grid_layout = QtW.QGridLayout(pal_grid_container)
        pal_grid_layout.setSpacing(0)
        pal_grid_layout.setContentsMargins(0, 0, 0, 0)
        pal_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for _i in range(64):
            row = _i // 16
            col = _i % 16
            box = MiniColorBox(_i)
            pal_grid_layout.addWidget(box, row, col)
            self.palette_boxes.append(box)

        spr_palette_layout.addWidget(
            pal_grid_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        spr_palette_layout.addStretch()

        right_panel.addWidget(spr_palette_group)

        main_layout.addLayout(right_panel, stretch=1)

    def on_pal_add_clicked(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # # Save dialog for new palette file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "New Palette File", start_dir, "Palette Files (*.pal *.bin);;All Files (*)"
        )

        # If successful, create a new row under the palette tab
        if file_path:
            self.add_palette_row(file_path)

    def add_palette_row(self, file_path):
        # Appends a 3-widget row to the right-hand panel for palette editing
        row_widget = QtW.QWidget()
        row_layout = QtW.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # Line count dropdown (1-4)
        line_combo = QtW.QComboBox()
        line_combo.addItem("1")    # Prime it with 1 for eval_pal_capacity
        line_combo.setFixedWidth(50)

        # Track the combo boxes in a list for evaluation
        self.pal_line_combos.append(line_combo)
        self.pal_rows.append((path_input, line_combo))

        # Remove button
        btn_remove = QtW.QPushButton("Remove")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(
            lambda checked=False, _r=row_widget, _c=line_combo,
                   _p=path_input: self.remove_palette_row(_r, _c, _p)
        )

        # Re-evaluate capacity whenever a dropdown value is changed
        line_combo.currentIndexChanged.connect(self.eval_pal_capacity)

        row_layout.addWidget(path_input, stretch=1)
        row_layout.addWidget(line_combo)
        row_layout.addWidget(btn_remove)

        self.pal_entries_layout.addWidget(row_widget)

        # Seems redundant, but we need an initial evaluation
        self.eval_pal_capacity()

    def remove_palette_row(self, row_widget, line_combo, path_input):
        # Removes a palette widget row and re-evaluate capacity
        if line_combo in self.pal_line_combos:
            self.pal_line_combos.remove(line_combo)

        row = (path_input, line_combo)
        if row in self.pal_rows:
            self.pal_rows.remove(row)

        self.pal_entries_layout.removeWidget(row_widget)
        row_widget.deleteLater()

        self.eval_pal_capacity()

    def on_pal_load_clicked(self, *args):
        """Loads palette(s) from the filepath(s) specified into the palette grid"""
        # Palette index to load the next color into
        current_index = 0

        # Loop for each filepath added
        for path_input, line_combo in self.pal_rows:
            file_path_str = path_input.text().strip()
            if not file_path_str:
                continue

            path = Path(file_path_str)
            num_lines = int(line_combo.currentText() or "1")

            # If the file doesn't exist, skip loading for this entry
            if not path.exists():
                current_index += num_lines * 16
                continue

            num_colors = num_lines * 16

            try:
                with open(path, "rb") as f:
                    # Load palette data (2 bytes per color word; 0B GR)
                    # To-Do: implement MDCOLOR_VALUES from the Palette Editor
                    data = f.read(num_colors * 2)
                    loaded_colors = []
                    for _i in range(0, len(data), 2):
                        if _i + 1 < len(data):
                            val = (data[_i] << 8) | data[_i + 1]
                            _r = ((val >> 1) & 0x07) * 36
                            _g = ((val >> 5) & 0x07) * 36
                            _b = ((val >> 9) & 0x07) * 36
                            loaded_colors.append(QColor(_r, _g, _b))

                    # Slot colors into the palette grid
                    for _i, color in enumerate(loaded_colors):
                        target_idx = current_index + _i
                        if target_idx < len(self.palette_colors):
                            self.palette_colors[target_idx] = color

            except Exception as e:
                print(f"Error loading palette {path.name}: {e}")

            # Increment color index for the next file load
            current_index += num_colors

        # Refresh the palette grid
        for i, color in enumerate(self.palette_colors):
            if i < len(self.palette_boxes):
                self.palette_boxes[i].set_color(color)

    def on_pal_save_clicked(self, *args):
        """Saves palette grid colors to the files specified in the file manager"""
        current_index = 0

        for path_input, line_combo in self.pal_rows:
            file_path_str = path_input.text().strip()
            num_lines = int(line_combo.currentText() or "1")
            num_colors = num_lines * 16

            # If a filepath is empty, skip those palette rows and advance color offset index
            if not file_path_str:
                current_index += num_colors
                continue

            path = Path(file_path_str)

            try:
                # Ensure parent directory of a new filepath exists
                path.parent.mkdir(parents=True, exist_ok=True)

                binary_data = bytearray()
                for _i in range(num_colors):
                    target_idx = current_index + _i
                    if target_idx < len(self.palette_colors):
                        color = self.palette_colors[target_idx]
                    else:
                        color = QColor(0, 0, 0)

                    # Convert color to compatible color components
                    _r = round(color.red() / 255 * 7)
                    _g = round(color.green() / 255 * 7)
                    _b = round(color.blue() / 255 * 7)

                    # Pack into the word format: 0000 BBB0 GGG0 RRR0
                    word = (_b << 9) | (_g << 5) | (_r << 1)
                    binary_data.append((word >> 8) & 0xFF)
                    binary_data.append(word & 0xFF)

                # Write binary data to file (creates file if it doesn't exist)
                with open(path, "wb") as f:
                    f.write(binary_data)

            except Exception as e:
                print(f"Error saving palette {path.name}: {e}")
                QtW.QMessageBox.warning(self, "Save Error", f"Could not save palette file {path.name}:\n{str(e)}")

            # Advance color index for the next row file
            current_index += num_colors

    def eval_pal_capacity(self):
        # Sum the values of all active line combo boxes
        total_lines = sum(int(combo.currentText() or "1") for combo in self.pal_line_combos)

        # Disable New button if we reach the 4-line limit
        is_full = (total_lines >= 4)
        self.btn_pal_add.setDisabled(is_full)

        # Load/Save are only enabled when we have palette filepaths in the system
        has_rows = len(self.pal_rows) > 0
        self.btn_pal_load.setEnabled(has_rows)
        self.btn_pal_save.setEnabled(has_rows)

        # Dynamically restrict each dropdown so the user can't select a value that exceeds 4
        for combo in self.pal_line_combos:
            current_val = int(combo.currentText() or "1")
            # Max allowed for this specific combo is 4 minus the lines taken up
            max_allowed = 4 - (total_lines - current_val)

            # Rebuild dropdown options
            combo.blockSignals(True)
            combo.clear()

            for _i in range(1, max_allowed + 1):
                combo.addItem(str(_i))

            combo.setCurrentText(str(current_val))
            combo.blockSignals(False)
