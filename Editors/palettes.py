from pathlib import Path
import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

# MD-compatible RGB values (0x00 - 0xE0)
MDCOLOR_VALUES = [0x20*x for x in range(8)]

class ColorBox(QtW.QFrame):
    clicked = pyqtSignal(int, QColor)

    def __init__(self, index, color=QColor(0, 0, 0)):
        super().__init__()
        self.index = index
        self.color = color
        self.is_selected = False

        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

    def set_color(self, color):
        self.color = color
        self.update_style()

    def set_selected(self, selected):
        self.is_selected = selected
        self.update_style()

    def update_style(self):
        border_color = "#FFFFFF" if self.is_selected else "#444444"
        border_width = "3px" if self.is_selected else "1px"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color.name()};
                border: {border_width} solid {border_color};
                border-radius: 4px;
            }}
        """)

    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index, self.color)

class PaletteEditor(QtW.QWidget):
    def __init__(self):
        super().__init__()

        # Internal Palette Storage (1 to 128 colors)
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]  # Default 64 colors
        self.boxes = []
        self.selected_index = 0
        self.active_palette_path = None
        self.project_palette_paths = []

        self.init_ui()

    def init_ui(self):
        main_layout = QtW.QHBoxLayout(self)

        # -----------------------------
        # LEFT PANEL: Dynamic Color Grid
        # -----------------------------
        color_box = QtW.QGroupBox("Palette Grid (Up to 128 Colors)")
        color_layout = QtW.QVBoxLayout(color_box)

        # Scroll area in case palette grid extends past the window border
        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(scroll_content)
        color_layout.addWidget(scroll_area)

        main_layout.addWidget(color_box, stretch=2)

        # -----------------------------
        # RIGHT PANEL: Editing Controls
        # -----------------------------
        editor_panel = QtW.QVBoxLayout()

        # Palette File Dropdown
        pal_select_group = QtW.QGroupBox("Select Palette")
        pal_select_layout = QtW.QVBoxLayout(pal_select_group)

        self.pal_dropdown = QtW.QComboBox()
        self.pal_dropdown.setToolTip("Select a palette file from the active project")
        self.pal_dropdown.currentIndexChanged.connect(self.on_pal_dropdown_changed)
        pal_select_layout.addWidget(self.pal_dropdown, stretch=1)

        # File Buttons
        btn_grid = QtW.QGridLayout()
        self.btn_new = QtW.QPushButton("New")
        self.btn_load = QtW.QPushButton("Load")
        self.btn_save = QtW.QPushButton("Save")
        self.btn_saveas = QtW.QPushButton("Save As...")

        #self.btn_new.clicked.connect(self.new_palette)
        #self.btn_load.clicked.connect(self.load_palette_dialog)
        #self.btn_save.clicked.connect(self.save_palette)
        #self.btn_saveas.clicked.connect(self.save_palette_as)

        btn_grid.addWidget(self.btn_new, 0, 0)
        btn_grid.addWidget(self.btn_load, 0, 1)
        btn_grid.addWidget(self.btn_save, 1, 0)
        btn_grid.addWidget(self.btn_saveas, 1, 1)

        pal_select_layout.addLayout(btn_grid)
        editor_panel.addWidget(pal_select_group)

        # Color Editing Tool
        control_group = QtW.QGroupBox("Color Editing")
        control_layout = QtW.QVBoxLayout(control_group)

        # Selected Index Label
        self.index_label = QtW.QLabel("Selected Color: #0")
        self.index_label.setObjectName("infoLabel")
        control_layout.addWidget(self.index_label)

        # Hex Preview & Large Color Box
        preview_layout = QtW.QHBoxLayout()
        self.large_preview = QtW.QFrame()
        self.large_preview.setFixedSize(60, 60)

        self.hex_input = QtW.QLineEdit("#000000")
        self.hex_input.setMaxLength(7)
        self.hex_input.editingFinished.connect(self.on_hex_edited)

        preview_layout.addWidget(self.large_preview)
        preview_layout.addLayout(self.create_form_row("Hex Value:", self.hex_input))
        control_layout.addLayout(preview_layout)

        control_layout.addSpacing(15)

        self.r_slider = self.create_step_slider(self.on_slider_changed)
        self.g_slider = self.create_step_slider(self.on_slider_changed)
        self.b_slider = self.create_step_slider(self.on_slider_changed)

        self.r_val_label = QtW.QLabel("0")
        self.g_val_label = QtW.QLabel("0")
        self.b_val_label = QtW.QLabel("0")

        control_layout.addLayout(self.create_slider_row("Red:", self.r_slider, self.r_val_label))
        control_layout.addLayout(self.create_slider_row("Green:", self.g_slider, self.g_val_label))
        control_layout.addLayout(self.create_slider_row("Blue:", self.b_slider, self.b_val_label))

        control_layout.addStretch()
        editor_panel.addWidget(control_group, stretch=1)

        main_layout.addLayout(editor_panel, stretch=1)

        # Build initial grid UI
        self.rebuild_grid()
        self.select_color(0, self.palette_colors[0])

    def populate_palette_list(self, palette_paths: list[Path]):
        self.pal_dropdown.blockSignals(True)
        self.pal_dropdown.clear()

        if not palette_paths:
            self.pal_dropdown.addItem("No Palettes Found", userData=None)
            self.pal_dropdown.setEnabled(False)
            self.pal_dropdown.blockSignals(False)
            return

        self.pal_dropdown.setEnabled(True)
        for path in palette_paths:
            # Display relative filename to user, store full Path object in itemData
            self.pal_dropdown.addItem(path.name, userData=path)

        self.pal_dropdown.blockSignals(False)

        # Load the first palette by default
        self.on_pal_dropdown_changed(0)

    def on_pal_dropdown_changed(self, index: int):
        path = self.pal_dropdown.itemData(index)
        if path and isinstance(path, Path):
            self.load_palette_file(path)

    def load_palette_file(self, path: Path):
        """Reads binary (.bin/.pal) files."""
        self.active_palette_path = path
        if not path.exists():
            return

        loaded_colors = []

        # Raw Binary Palette file (2-byte word per color: 0000 BBB0 GGG0 RRR0)
        try:
            with open(path, "rb") as f:
                data = f.read(256)  # Read up to 128 colors (256 bytes)
                for i in range(0, len(data), 2):
                    if i + 1 < len(data):
                        val = (data[i] << 8) | data[i + 1]

                        # Extract 3-bit values (0-7)
                        r_step = (val >> 1) & 0x07
                        g_step = (val >> 5) & 0x07
                        b_step = (val >> 9) & 0x07

                        # Map them directly to color values
                        _r = MDCOLOR_VALUES[r_step]
                        _g = MDCOLOR_VALUES[g_step]
                        _b = MDCOLOR_VALUES[b_step]

                        loaded_colors.append(QColor(_r, _g, _b))

        except Exception:
            pass

        if loaded_colors:
            self.set_palette_data(loaded_colors)

    def rebuild_grid(self):
        # Clear existing items from layout
        for box in self.boxes:
            box.deleteLater()
        self.boxes.clear()

        # Build grid with 16 columns per row
        MAX_COLUMNS = 16
        for idx, color in enumerate(self.palette_colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS

            box = ColorBox(idx, color)
            box.clicked.connect(self.select_color)
            self.grid_layout.addWidget(box, row, col)
            self.boxes.append(box)

    def set_palette_data(self, colors: list[QColor]):
        # Constrain to range [1, 128]
        self.palette_colors = colors[:128] if colors else [QColor(0, 0, 0)]
        self.rebuild_grid()
        self.select_color(0, self.palette_colors[0])

    def select_color(self, index, color):
        # Update active selection highlighting
        if 0 <= self.selected_index < len(self.boxes):
            self.boxes[self.selected_index].set_selected(False)

        self.selected_index = index
        if 0 <= index < len(self.boxes):
            self.boxes[index].set_selected(True)

        self.index_label.setText(f"Selected Color: #{index}")

        # Block input signals
        self.r_slider.blockSignals(True)
        self.g_slider.blockSignals(True)
        self.b_slider.blockSignals(True)
        self.hex_input.blockSignals(True)

        # Now, update sliders and preview safely
        _r = self.snap_to_md_colors(color.red())
        _g = self.snap_to_md_colors(color.green())
        _b = self.snap_to_md_colors(color.blue())

        self.r_slider.setValue(_r)
        self.g_slider.setValue(_g)
        self.b_slider.setValue(_b)

        self.r_val_label.setText(f"0x{MDCOLOR_VALUES[_r]:02X}")
        self.g_val_label.setText(f"0x{MDCOLOR_VALUES[_g]:02X}")
        self.b_val_label.setText(f"0x{MDCOLOR_VALUES[_b]:02X}")

        self.hex_input.setText(color.name().upper())
        self.update_preview_box(color)

        # Unblock input signals
        self.r_slider.blockSignals(False)
        self.g_slider.blockSignals(False)
        self.b_slider.blockSignals(False)
        self.hex_input.blockSignals(False)

    def on_slider_changed(self):
        _r = MDCOLOR_VALUES[self.r_slider.value()]
        _g = MDCOLOR_VALUES[self.g_slider.value()]
        _b = MDCOLOR_VALUES[self.b_slider.value()]

        self.r_val_label.setText(f"0x{_r:02X}")
        self.g_val_label.setText(f"0x{_g:02X}")
        self.b_val_label.setText(f"0x{_b:02X}")

        new_color = QColor(_r, _g, _b)

        self.hex_input.blockSignals(True)
        self.hex_input.setText(new_color.name().upper())
        self.hex_input.blockSignals(False)

        self.apply_color_change(new_color)

    def on_hex_edited(self):
        hex_text = self.hex_input.text()
        color = QColor(hex_text)
        if color.isValid():
            _r = self.snap_to_md_colors(color.red())
            _g = self.snap_to_md_colors(color.green())
            _b = self.snap_to_md_colors(color.blue())

            snapped_color = QColor(
                MDCOLOR_VALUES[_r],
                MDCOLOR_VALUES[_g],
                MDCOLOR_VALUES[_b]
            )

            self.select_color(self.selected_index, snapped_color)
            self.apply_color_change(snapped_color)

    def apply_color_change(self, color):
        self.palette_colors[self.selected_index] = color
        self.boxes[self.selected_index].set_color(color)
        self.update_preview_box(color)

    def update_preview_box(self, color):
        self.large_preview.setStyleSheet(f"""
            QFrame {{
                background-color: {color.name()};
                border: 2px solid #555555;
                border-radius: 6px;
            }}
        """)

    @staticmethod
    def snap_to_md_colors(val):
        # Snaps an RGB color value to its corresponding slider index (0-7)
        val = min(MDCOLOR_VALUES, key=lambda x: abs(x - val))
        return MDCOLOR_VALUES.index(val)

    def create_step_slider(self, callback):
        slider = QtW.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 7)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickPosition(QtW.QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(1)
        slider.valueChanged.connect(callback)
        return slider

    def create_slider_row(self, label_text, slider, val_label):
        layout = QtW.QHBoxLayout()
        lbl = QtW.QLabel(label_text)
        lbl.setFixedWidth(50)
        val_label.setFixedWidth(30)
        layout.addWidget(lbl)
        layout.addWidget(slider)
        layout.addWidget(val_label)
        return layout

    def create_form_row(self, label_text, widget):
        layout = QtW.QVBoxLayout()
        lbl = QtW.QLabel(label_text)
        layout.addWidget(lbl)
        layout.addWidget(widget)
        return layout
