from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from Constants import *
from Editors.palettes import snap_to_md_colors
from PaletteEditor.colorbox import MiniColorBox

class SpriteEditor(QtW.QWidget):
    def __init__(self):
        super().__init__()

        # 64 color palette (4 palette lines) for sprite rendering
        self.palette_boxes = []
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]

        # These are used in the palette file manager
        self.pal_rows = []  # Stores (path_input, line_combo) for palette loading
        self.pal_line_combos = []

        # VRAM art tile structure
        self.vram_tiles = {}

        # Used in the art file manager
        self.art_rows = []  # Stores (path_input, offset_spin, comp_combo) for art loading

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

        # *** ART TILE SUB-TAB ***
        art_tab = QtW.QWidget()
        art_layout = QtW.QHBoxLayout(art_tab)

        # Buttons (Built off the Palettes Tab
        art_btn_layout = QtW.QVBoxLayout()
        art_btn_layout.setSpacing(12)
        art_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_art_add = QtW.QPushButton("Add")
        self.btn_art_load = QtW.QPushButton("Load")
        self.btn_art_save = QtW.QPushButton("Save")

        for btn in (self.btn_art_add, self.btn_art_load, self.btn_art_save):
            btn.setFixedWidth(60)
            art_btn_layout.addWidget(btn)

        # Load/Save are disabled by default until palettes are added
        self.btn_art_load.setEnabled(False)
        self.btn_art_save.setEnabled(False)

        self.btn_art_add.clicked.connect(self.on_art_add_clicked)
        self.btn_art_load.clicked.connect(self.on_art_load_clicked)

        art_layout.addLayout(art_btn_layout)

        # Dynamic entry container
        art_entries_scroll = QtW.QScrollArea()
        art_entries_scroll.setWidgetResizable(True)

        self.art_entries_widget = QtW.QWidget()
        self.art_entries_layout = QtW.QVBoxLayout(self.art_entries_widget)
        self.art_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        art_entries_scroll.setWidget(self.art_entries_widget)
        art_layout.addWidget(art_entries_scroll, stretch=1)

        data_tabs.addTab(art_tab, "Art")
        # ************************

        # *** MAPPINGS SUB-TAB ***
        mappings_tab = QtW.QWidget()
        mappings_layout = QtW.QHBoxLayout(mappings_tab)

        # Buttons (I'm going to try to model this after Flex 2)
        map_btn_layout = QtW.QVBoxLayout()
        map_btn_layout.setSpacing(12)
        map_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_map_add = QtW.QPushButton("Add")
        self.btn_map_load = QtW.QPushButton("Load")
        self.btn_map_save = QtW.QPushButton("Save")

        for btn in (self.btn_map_add, self.btn_map_load, self.btn_map_save):
            btn.setFixedWidth(60)
            map_btn_layout.addWidget(btn)

        # Load/Save are disabled by default until mappings are added
        self.btn_map_load.setEnabled(False)
        self.btn_map_save.setEnabled(False)

        mappings_layout.addLayout(map_btn_layout)

        # Mapping/DPLC entry container
        map_entries_scroll = QtW.QScrollArea()
        map_entries_scroll.setWidgetResizable(True)

        self.map_entries_widget = QtW.QWidget()
        self.map_entries_layout = QtW.QVBoxLayout(self.map_entries_widget)
        self.map_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        map_entries_scroll.setWidget(self.map_entries_widget)
        mappings_layout.addWidget(map_entries_scroll, stretch=1)

        data_tabs.addTab(mappings_tab, "Mappings")
        # ************************

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

        # Art Viewer (Moved from left panel)
        self.vram_box = QtW.QGroupBox("Art Tile Viewer")
        art_viewer_layout = QtW.QVBoxLayout(self.vram_box)

        # Active Palette Line Selector for the Viewer
        viewer_controls = QtW.QHBoxLayout()
        viewer_controls.addWidget(QtW.QLabel("Preview Palette Line:"))
        self.viewer_line_combo = QtW.QComboBox()
        self.viewer_line_combo.addItems(["Line 0", "Line 1", "Line 2", "Line 3"])
        self.viewer_line_combo.currentIndexChanged.connect(self.update_sprite_viewer)

        viewer_controls.addWidget(self.viewer_line_combo)
        viewer_controls.addStretch()
        art_viewer_layout.addLayout(viewer_controls)

        # Scrollable Canvas
        self.vram_scroll = QtW.QScrollArea()
        self.vram_scroll.setWidgetResizable(True)
        self.vram_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vram_scroll.setStyleSheet("background-color: #222222;")  # Dark backdrop

        self.vram_label = QtW.QLabel()
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vram_scroll.setWidget(self.vram_label)

        art_viewer_layout.addWidget(self.vram_scroll)
        right_panel.addWidget(self.vram_box, stretch=2)

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

            # Number of colors to load based on number of lines in the entry
            num_colors = num_lines * 16

            # Raw Binary Palette file (2-byte word per color: 0000 BBB0 GGG0 RRR0)
            try:
                with open(path, "rb") as f:
                    data = f.read(num_colors * 2)   # Read 2 bytes for every color loaded
                    loaded_colors = []
                    for _i in range(0, len(data), 2):
                        if _i + 1 < len(data):
                            val = (data[_i] << 8) | data[_i + 1]

                            # Extract 3-bit values (0-7)
                            r_step = (val >> 1) & 0x07
                            g_step = (val >> 5) & 0x07
                            b_step = (val >> 9) & 0x07

                            # Map them directly to color values
                            _r = MDCOLOR_VALUES[r_step]
                            _g = MDCOLOR_VALUES[g_step]
                            _b = MDCOLOR_VALUES[b_step]

                            loaded_colors.append(QColor(_r, _g, _b))

                    # Slot colors into the palette grid
                    for _i, color in enumerate(loaded_colors):
                        target_idx = current_index + _i
                        if target_idx < len(self.palette_colors):
                            self.palette_colors[target_idx] = color

            except Exception as e:
                print(f"Error loading palette {path.name}: {e}")
                QtW.QMessageBox.warning(
                    self, "Palette Load Error", f"Could not load palette file {path.name}:\n{str(e)}"
                )

            # Increment color index for the next file load
            current_index += num_colors

        # Refresh the palette grid
        for _i, color in enumerate(self.palette_colors):
            if _i < len(self.palette_boxes):
                self.palette_boxes[_i].set_color(color)

        # Refresh VRAM after loading art
        self.update_sprite_viewer()

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
                    _r = snap_to_md_colors(color.red())
                    _g = snap_to_md_colors(color.green())
                    _b = snap_to_md_colors(color.blue())

                    # store in 0BGR format
                    binary_data.append((_b << 1) & 0xFF)
                    val = (_g << 5) | (_r << 1)
                    binary_data.append(val & 0xFF)

                # Write binary data to file (creates file if it doesn't exist)
                with open(path, "wb") as f:
                    f.write(binary_data)

            except Exception as e:
                print(f"Error saving palette {path.name}: {e}")
                QtW.QMessageBox.warning(self, "Save Error", f"Could not save palette file {path.name}:\n{str(e)}")

            # Advance color index for the next row file
            current_index += num_colors

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

    def on_art_add_clicked(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # # Save dialog for new art file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "New Art Tile File", start_dir, "Art Tile Files (*.unc *.bin);;All Files (*)"
        )

        # If successful, create a new row under the art tab
        if file_path:
            self.add_art_row(file_path)

    def on_art_load_clicked(self, *args):
        """Loads art tile data from the filepath(s) specified into virtual VRAM storage"""
        # Flush out VRAM
        self.vram_tiles.clear()

        # Loop for each filepath added
        for path_input, offset_spin, comp_combo in self.art_rows:
            file_path_str = path_input.text().strip()
            if not file_path_str:
                continue

            # If the file doesn't exist, skip loading for this entry
            path = Path(file_path_str)
            if not path.exists():
                print(f"Art file not found: {path}")
                continue

            # Starting VRAM tile index (0 to 2047) from the hex spinbox
            current_tile_idx = offset_spin.value()

            # Raw Binary art file (8x8 = 64px = 32 bytes per tile)
            try:
                with open(path, "rb") as f:
                    raw_data = f.read()

                # Each 8x8 tile is 32 bytes (64 pixels at 4 bits per pixel)
                tile_count = len(raw_data) // 32

                for _t in range(tile_count):
                    tile_bytes = raw_data[_t * 32: (_t + 1) * 32]
                    pixel_indices = []

                    # Unpack 32 bytes into 64 palette indices (high nibble first)
                    for byte in tile_bytes:
                        pixel_indices.append((byte >> 4) & 0x0F)  # Left pixel
                        pixel_indices.append(byte & 0x0F)  # Right pixel

                    # Slot tile into virtual VRAM storage
                    target_idx = current_tile_idx + _t
                    if target_idx < 2048:
                        self.vram_tiles[target_idx] = pixel_indices

            except Exception as e:
                print(f"Error loading art file {path.name}: {e}")
                QtW.QMessageBox.warning(
                    self, "Art Load Error", f"Could not load art file {path.name}:\n{str(e)}"
                )

        # Refresh VRAM after loading art
        self.update_sprite_viewer()

    def add_art_row(self, file_path):
        # Cap sprite build at 3 art files
        if len(self.art_rows) >= 3:
            return

        # Appends a 3-widget row to the right-hand panel for art editing
        row_widget = QtW.QWidget()
        row_layout = QtW.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # VRAM Tile Offset Input (Hexadecimal)
        offset_spin = QtW.QSpinBox()
        offset_spin.setRange(0, 2047)  # Cap at 2048 tiles (I'll worry about specifics later)
        offset_spin.setDisplayIntegerBase(16)  # Display in hex
        offset_spin.setPrefix("$")
        offset_spin.setToolTip("Starting VRAM Tile Index (Hex)")
        offset_spin.setFixedWidth(70)

        # Compression Dropdown
        comp_combo = QtW.QComboBox()
        comp_combo.addItems(["Uncompressed", "Nemesis", "Kosinski", "Kosinski-M"])
        comp_combo.setToolTip("Compression Format")
        comp_combo.setFixedWidth(110)

        # Store elements in the tracking array
        row_data = (path_input, offset_spin, comp_combo)
        self.art_rows.append(row_data)

        # Remove button
        btn_remove = QtW.QPushButton("Remove")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(
            lambda checked=False, _r=row_widget, _data=row_data: self.remove_art_row(_r, _data)
        )

        row_layout.addWidget(path_input, stretch=1)
        row_layout.addWidget(offset_spin)
        row_layout.addWidget(comp_combo)
        row_layout.addWidget(btn_remove)

        self.art_entries_layout.addWidget(row_widget)

        # Initial evaluation
        self.eval_art_capacity()

    def remove_art_row(self, row_widget, row_data):
        # Removes an art widget row and re-evaluate capacity
        if row_data in self.art_rows:
            self.art_rows.remove(row_data)

        self.art_entries_layout.removeWidget(row_widget)
        row_widget.deleteLater()

        self.eval_art_capacity()

    def update_sprite_viewer(self):
        """Renders the virtual VRAM contents into an image and refreshes the viewer canvas."""
        from PyQt6.QtGui import QImage, QPixmap

        # size: 16 x 128 tiles
        vram_width_px = 16 * 8
        vram_height_px = 128 * 8

        # Transparent ARGB canvas
        image = QImage(vram_width_px, vram_height_px, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        # Calc palette offset based on the selected line (0, 16, 32, or 48)
        line_offset = self.viewer_line_combo.currentIndex() * 16

        # Loop through every tile (within each tile, loop through each pixel)
        for tile_idx, pixel_indices in self.vram_tiles.items():
            # Stop at the end of the VRAM space
            if tile_idx >= 2048:
                continue

            # Calculate base coords for the top-left pixel of this 8x8 tile
            tile_x = (tile_idx % 32) * 8
            tile_y = (tile_idx // 32) * 8

            for i, p_val in enumerate(pixel_indices):
                # Index 0 is transparent (To-Do: Make displaying color 0 optional)
                if p_val == 0:
                    continue

                # Pixel coordinates
                px = tile_x + (i % 8)
                py = tile_y + (i // 8)

                # Fetch color from palette grid, using the line offset + pixel value
                color_idx = line_offset + p_val
                if color_idx < len(self.palette_colors):
                    color = self.palette_colors[color_idx]
                    image.setPixelColor(px, py, color)

        # Scale up 2x
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            vram_width_px * 2,
            vram_height_px * 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

        self.vram_label.setPixmap(scaled_pixmap)

    def eval_art_capacity(self):
        # Disable Add button if we reach the 3-file limit
        is_full = (len(self.art_rows) >= 3)
        self.btn_art_add.setDisabled(is_full)

        # Load/Save are only enabled when art filepaths are present
        has_rows = len(self.art_rows) > 0
        self.btn_art_load.setEnabled(has_rows)
        self.btn_art_save.setEnabled(has_rows)
