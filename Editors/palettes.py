import json
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
        self.editor = None
        self.is_selected = False

        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_style()

        # Right-click menu functionality
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos, b=self: self.show_edit_menu(pos, b))

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
            modifiers = a0.modifiers()
            if self.editor:
                self.editor.select_colors(self.index, modifiers)
            #self.clicked.emit(self.index, self.color)

    def show_edit_menu(self, pos, box):
        menu = QtW.QMenu(self)

        act_cut = menu.addAction("Cut")
        act_copy = menu.addAction("Copy")
        act_paste_before = menu.addAction("Paste Before")
        act_paste_over = menu.addAction("Paste Over")
        act_paste_after = menu.addAction("Paste After")
        menu.addSeparator()
        act_insert_before = menu.addAction("Insert Before")
        act_insert_after = menu.addAction("Insert After")
        menu.addSeparator()
        act_clear = menu.addAction("Clear")
        act_delete = menu.addAction("Delete")

        # Convert the widget-relative position to global screen coordinates for the menu
        global_pos = box.mapToGlobal(pos)

        # Display the menu and wait for the user to select an action
        action = menu.exec(global_pos)

        if action == act_cut:
            self.copy_colors(self.index, True)
        elif action == act_copy:
            self.copy_colors(self.index)
        elif action == act_paste_before:
            self.paste_colors("before", self.index)
        elif action == act_paste_over:
            self.paste_colors("over", self.index)
        elif action == act_paste_after:
            self.paste_colors("after", self.index)
        elif action == act_insert_before:
            self.insert_color("before", self.index)
        elif action == act_insert_after:
            self.insert_color("after", self.index)
        elif action == act_clear:
            self.clear_color(self.index)
        elif action == act_delete:
            self.delete_color(self.index)

    def copy_colors(self, target_index, cut=False):
        if not self.editor.selected_indices:
            return

        # Sort colors to keep them in visual order when pasting
        sorted_indices = sorted(self.editor.selected_indices)
        self.editor.clipboard_colors = [QColor(self.editor.palette_colors[idx]) for idx in sorted_indices]

        # If only Copying, stop here. Otherwise, remove copied colors
        if cut:
            # Delete in reverse order to avoid issues with index shifting
            sorted_indices.reverse()
            self.editor.remove_colors(sorted_indices)

    def paste_colors(self, mode, target_index):
        if not self.editor.clipboard_colors:
            return

        clipboard_length = len(self.editor.clipboard_colors)

        if mode == "over":
            # Overwrite existing slots
            start = target_index

            if max(len(self.editor.palette_colors), start + clipboard_length) > 128:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction",
                    f"Pasting {clipboard_length} colors here exceeds the 128 color limit. " +
                    "Some colors will not be pasted."
                )

            # Paste over, and clamp palette at 128.
            for _i, color in enumerate(self.editor.clipboard_colors):
                idx = start + _i
                if idx < len(self.editor.palette_colors):
                    self.editor.palette_colors[idx] = QColor(color)
                elif idx < 128:
                    self.editor.palette_colors.append(QColor(color))
                else:
                    break

        else:
            # Paste before or after the current index, shifting other colors accordingly
            start = target_index if mode == "before" else target_index + 1

            if len(self.editor.palette_colors) + clipboard_length > 128:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction",
                    f"Pasting {clipboard_length} colors here exceeds the 128 color limit. " +
                    "Some colors will not be pasted."
                )

            # Paste and shift, and clamp palette at 128.
            for i, color in enumerate(self.editor.clipboard_colors):
                self.editor.palette_colors.insert(start + i, QColor(color))

        # Rebuild from the start index onward
        self.editor.rebuild_grid(start)

        end = min(start + clipboard_length, len(self.editor.palette_colors))

        # Automatically select the newly pasted colors
        self.editor.active_index = start
        self.editor.selected_indices = list(range(start, end))
        self.editor.refresh_selection_ui()

    def insert_color(self, mode, target_index):
        if len(self.editor.palette_colors) >= 128:
            QtW.QMessageBox.warning(
                self, "Palette Size Restriction", "Palette cannot have more than 128 colors."
            )
            return

        index = target_index if mode == "before" else target_index + 1
        self.editor.palette_colors.insert(index, QColor(0, 0, 0))
        self.editor.rebuild_grid(index)
        self.editor.selected_indices = [index]
        self.editor.active_index = index
        self.editor.refresh_selection_ui()

    def clear_color(self, index):
        if not self.editor.selected_indices:
            return

        black = QColor(0, 0, 0)
        for idx in self.editor.selected_indices:
            self.editor.palette_colors[idx] = black
            self.editor.boxes[idx].set_color(black)

        self.editor.update_preview_box(black)

    def delete_color(self, index):
        if not self.editor.selected_indices:
            return

        # Delete in reverse order to avoid issues with index shifting
        sorted_indices = sorted(self.editor.selected_indices, reverse=True)
        self.editor.remove_colors(sorted_indices)


class PaletteEditor(QtW.QWidget):
    def __init__(self):
        super().__init__()

        # Internal Palette Storage (1 to 128 colors)
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]  # Default 64 colors
        self.boxes = []

        self.selected_indices = []
        self.active_index = 0

        self.active_palette_path = None
        self.project_palette_paths = []

        self.init_ui()

    def init_ui(self):
        main_layout = QtW.QHBoxLayout(self)

        # -----------------------------
        # LEFT PANEL: Dynamic Color Grid
        # -----------------------------
        color_box = QtW.QGroupBox(
            "Palette Grid (Left Click: Select;"+
            "    Left+Shift: Mass Select;"+
            "    Left+Ctrl: Toggle Selection;"+
            "    Right Click: Context Menu)"
        )
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
        self.btn_remove = QtW.QPushButton("Remove")
        for btn in (self.btn_new, self.btn_load, self.btn_save, self.btn_saveas, self.btn_remove):
            btn.setFixedWidth(55)

        self.btn_new.clicked.connect(self.new_palette_file)
        self.btn_load.clicked.connect(self.load_palette_file)
        self.btn_save.clicked.connect(self.save_palette_file)
        self.btn_saveas.clicked.connect(self.save_palette_file_as)
        self.btn_remove.clicked.connect(self.remove_palette_file)

        btn_grid.addWidget(self.btn_new, 0, 0)
        btn_grid.addWidget(self.btn_load, 0, 1)
        btn_grid.addWidget(self.btn_save, 0, 2)
        btn_grid.addWidget(self.btn_saveas, 0, 3)
        btn_grid.addWidget(self.btn_remove, 0, 4)

        pal_select_layout.addLayout(btn_grid)
        editor_panel.addWidget(pal_select_group)

        # Color Entry Edit Buttons
        pal_edit_group = QtW.QGroupBox("Palette Editing")
        pal_edit_layout = QtW.QVBoxLayout(pal_edit_group)

        # Edit Buttons (Features to be considered: Undo, Redo, Resize (Add/Remove), Shift)
        btn_grid_edit = QtW.QGridLayout()
        self.btn_add = QtW.QPushButton("Add")
        self.btn_subtract = QtW.QPushButton("Remove")

        self.btn_add.clicked.connect(self.edit_palette_add_color)
        self.btn_subtract.clicked.connect(self.edit_palette_remove_color)

        btn_grid_edit.addWidget(self.btn_add, 0, 0)
        btn_grid_edit.addWidget(self.btn_subtract, 0, 1)

        pal_edit_layout.addLayout(btn_grid_edit)
        editor_panel.addWidget(pal_edit_group)

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

        #control_layout.addStretch()
        editor_panel.addWidget(control_group, stretch=1)

        # Advanced Editing Functions
        advanced_group = QtW.QGroupBox("Advanced Functions")
        advanced_layout = QtW.QVBoxLayout(advanced_group)

        # Advanced Option Buttons
        btn_grid_adv = QtW.QGridLayout()
        self.btn_blend = QtW.QPushButton("Color Blend")
        self.btn_grey = QtW.QPushButton("Greyscale")
        self.btn_invert = QtW.QPushButton("Invert Colors")
        self.btn_gradient = QtW.QPushButton("Build Gradient")

        btn_grid_adv.addWidget(self.btn_blend, 0, 0)
        btn_grid_adv.addWidget(self.btn_grey, 1, 0)
        btn_grid_adv.addWidget(self.btn_invert, 2, 0)
        btn_grid_adv.addWidget(self.btn_gradient, 3, 0)

        advanced_layout.addLayout(btn_grid_adv)
        editor_panel.addWidget(advanced_group)

        main_layout.addLayout(editor_panel, stretch=1)

        # Build initial grid UI and set selection to color 0
        self.set_palette_data(self.palette_colors)

    def new_palette_file(self):
        count, ok = QtW.QInputDialog.getInt(
            self, "New Palette", "Number of colors:", 16, 1, 128, 1
        )
        if not ok:
            return

        # Init new palette as all black
        new_pal = [QColor(0, 0, 0) for _i in range(count)]

        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new palette file
        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "Create Palette File", start_dir, "Genesis Palette (*.bin *.pal);;All Files (*)"
        )
        if not file_path:
            return

        path = Path(file_path)

        # Add palette file to project file
        if hasattr(main_win, "active_project_data") and main_win.active_project_data is not None:
            # Determine relative path string to write into JSON
            if project_dir and path.is_relative_to(project_dir):
                relative_path = str(path.relative_to(project_dir))
            else:
                relative_path = str(path)

            palettes_list = main_win.active_project_data.setdefault("palettes", [])
            if relative_path not in palettes_list:
                palettes_list.append(relative_path)

            # Persist project JSON changes back to disk
            project_json_path = getattr(main_win, "active_project_json_path", None)
            if project_json_path and Path(project_json_path).exists():
                try:
                    with open(project_json_path, "w", encoding="utf-8") as f:
                        json.dump(main_win.active_project_data, f, indent=2)
                except Exception as e:
                    QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

        # Add path to the editor's list and select it for editing
        self.register_and_select_palette(path)

        # Update palette grid and save the new file to disk
        self.set_palette_data(new_pal)
        self.write_palette_to_disk(path)

    def load_palette_file(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Load dialog for palette file
        file_path, _ = QtW.QFileDialog.getOpenFileName(
            self, "Load Palette", start_dir, "Palette Files (*.bin *.pal *.json);;All Files (*)"
        )
        if not file_path:
            return

        path = Path(file_path)

        # Add palette file to project file, if it isn't already present
        if hasattr(main_win, "active_project_data") and main_win.active_project_data is not None:
            # Determine relative path string to write into JSON
            if project_dir and path.is_relative_to(project_dir):
                relative_path = str(path.relative_to(project_dir))
            else:
                relative_path = str(path)

            palettes_list = main_win.active_project_data.setdefault("palettes", [])
            if relative_path not in palettes_list:
                palettes_list.append(relative_path)

            # Persist project JSON changes back to disk
            project_json_path = getattr(main_win, "active_project_json_path", None)
            if project_json_path and Path(project_json_path).exists():
                try:
                    with open(project_json_path, "w", encoding="utf-8") as f:
                        json.dump(main_win.active_project_data, f, indent=2)
                except Exception as e:
                    QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

        # Add path to the editor's list and select it for editing
        self.register_and_select_palette(path)

        # Update palette grid with loaded palette
        self.load_palette_data(path)

    def save_palette_file(self):
        if self.active_palette_path and self.active_palette_path.parent.exists():
            self.write_palette_to_disk(self.active_palette_path)
        else:
            self.save_palette_file_as()

    def save_palette_file_as(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "Save Palette As", start_dir, "Genesis Palette (*.bin *.pal);;All Files (*)"
        )
        if not file_path:
            return

        path = Path(file_path)

        # Add palette file to project file, if its name isn't already present
        if hasattr(main_win, "active_project_data") and main_win.active_project_data is not None:
            # Determine relative path string to write into JSON
            if project_dir and path.is_relative_to(project_dir):
                relative_path = str(path.relative_to(project_dir))
            else:
                relative_path = str(path)

            palettes_list = main_win.active_project_data.setdefault("palettes", [])
            if relative_path not in palettes_list:
                palettes_list.append(relative_path)

            # Persist project JSON changes back to disk
            project_json_path = getattr(main_win, "active_project_json_path", None)
            if project_json_path and Path(project_json_path).exists():
                try:
                    with open(project_json_path, "w", encoding="utf-8") as f:
                        json.dump(main_win.active_project_data, f, indent=2)
                except Exception as e:
                    QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

        # Savr new palette copy to disk
        self.write_palette_to_disk(path)

        # Add path to the editor's list and select it for editing
        self.register_and_select_palette(path)

    def remove_palette_file(self):
        if not self.active_palette_path:
            return

        reply = QtW.QMessageBox.question(
            self,
            "Remove Palette",
            f"Are you sure you want to remove '{self.active_palette_path.name}' from the project?\n\n"
            "Note: The actual file will NOT be deleted from your directory.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No
        )

        # Exit if confirmation fails
        if reply != QtW.QMessageBox.StandardButton.Yes:
            return

        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)

        # Remove the palette from the JSON project file
        if hasattr(main_win, "active_project_data") and main_win.active_project_data is not None:
            # Determine the exact relative path string in the file
            if project_dir and self.active_palette_path.is_relative_to(project_dir):
                relative_path = str(self.active_palette_path.relative_to(project_dir))
            else:
                relative_path = str(self.active_palette_path)

            palettes_list = main_win.active_project_data.get("palettes", [])
            if relative_path in palettes_list:
                palettes_list.remove(relative_path)

            # Persist project JSON changes back to disk
            project_json_path = getattr(main_win, "active_project_json_path", None)
            if project_json_path and Path(project_json_path).exists():
                try:
                    with open(project_json_path, "w", encoding="utf-8") as f:
                        json.dump(main_win.active_project_data, f, indent=2)
                except Exception as e:
                    QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

        # Remove entry and refresh dropdown
        if self.active_palette_path in self.project_palette_paths:
            self.project_palette_paths.remove(self.active_palette_path)

        self.active_palette_path = None
        self.populate_palette_list(self.project_palette_paths)

    def edit_palette_add_color(self):
        length = len(self.palette_colors)
        if length >= 128:
            QtW.QMessageBox.warning(
                self, "Palette Size Restriction", "Palette cannot have more than 128 colors."
            )
            return

        self.palette_colors.append(QColor(0, 0, 0))

        MAX_COLUMNS = 16
        idx = length
        row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS

        box = ColorBox(idx)
        box.editor = self
        self.grid_layout.addWidget(box, row, col)
        self.boxes.append(box)

    def edit_palette_remove_color(self):
        if len(self.palette_colors) <= 1:
            QtW.QMessageBox.warning(
                self, "Palette Size Restriction", "Palette must have at least 1 color."
            )
            return

        # This COULD be optimized, but I'll replace Add/Remove with Resize, so I won't bother
        self.palette_colors.pop()
        self.rebuild_grid(len(self.palette_colors))

        new_index = min(self.active_index, len(self.palette_colors) - 1)
        self.selected_indices = [new_index]
        self.active_index = new_index
        self.refresh_selection_ui()

    def write_palette_to_disk(self, path: Path):
        """Encodes current QColor palette into Mega Drive format (0000 BBB0 GGG0 RRR0)."""
        binary_data = bytearray()
        for color in self.palette_colors:
            _r = self.snap_to_md_colors(color.red())
            _g = self.snap_to_md_colors(color.green())
            _b = self.snap_to_md_colors(color.blue())

            # store in 0BGR format
            binary_data.append((_b << 1) & 0xFF)
            val = (_g << 5) | (_r << 1)
            binary_data.append(val & 0xFF)

        try:
            with open(path, "wb") as f:
                f.write(binary_data)
        except Exception as e:
            QtW.QMessageBox.critical(self, "Save Error", f"Failed to save palette:\n{str(e)}")

    def register_and_select_palette(self, path: Path):
        # Update the current palette file reference
        self.active_palette_path = path

        # Add it to the project if needed
        if path not in self.project_palette_paths:
            self.project_palette_paths.append(path)

        # Repopulate the dropdown list
        self.populate_palette_list(self.project_palette_paths)

        # Set dropdown selection to newly added palette
        target_index = -1
        for i in range(self.pal_dropdown.count()):
            item_data = self.pal_dropdown.itemData(i)
            if item_data and Path(item_data) == path:
                target_index = i
                break

        # Set new current index, then unblock signals again
        if target_index >= 0:
            self.pal_dropdown.setCurrentIndex(target_index)

    def populate_palette_list(self, palette_paths: list[Path]):
        self.project_palette_paths = list(palette_paths)

        self.pal_dropdown.blockSignals(True)
        self.pal_dropdown.clear()

        if not palette_paths:
            self.pal_dropdown.addItem("No Palettes Found", userData=None)
            self.pal_dropdown.setEnabled(False)
            self.pal_dropdown.blockSignals(False)
            return

        self.pal_dropdown.setEnabled(True)
        for path in self.project_palette_paths:
            # Display relative filename to user, store full Path object in itemData
            self.pal_dropdown.addItem(path.name, userData=path)

        # Silently reset the selection
        self.pal_dropdown.setCurrentIndex(-1)
        self.pal_dropdown.blockSignals(False)

        # Only auto-load index 0 if we aren't currently targeting a specific file
        if not self.active_palette_path and self.pal_dropdown.count() > 0:
            self.pal_dropdown.setCurrentIndex(0)

    def on_pal_dropdown_changed(self, index: int):
        path = self.pal_dropdown.itemData(index)
        if path and isinstance(path, Path):
            self.load_palette_data(path)

    def load_palette_data(self, path: Path):
        """Reads binary palette data"""
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

    def rebuild_grid(self, index = 0):
        # Use index to tell Triad how much to rebuild (avoid unnecessary work)
        index = max(0, min(index, len(self.boxes)))

        # Clear color boxes, starting with [index]
        for box in self.boxes[index:]:
            box.deleteLater()

        # Remove deleted references
        self.boxes = self.boxes[:index]

        # Build grid (only the missing portion)
        MAX_COLUMNS = 16
        for idx in range(index, len(self.palette_colors)):
            color = self.palette_colors[idx]
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS

            box = ColorBox(idx, color)
            box.editor = self
            self.grid_layout.addWidget(box, row, col)
            self.boxes.append(box)

    def set_palette_data(self, colors: list[QColor]):
        # Constrain to range [1, 128]; To-Do: Make the first line optional if palette_colors is already defined
        self.palette_colors = colors[:128] if colors else [QColor(0, 0, 0)]
        self.rebuild_grid()
        self.selected_indices = [0]
        self.active_index = 0
        self.refresh_selection_ui()

    def select_colors(self, index: int, modifiers):
        """Processes standard click, Ctrl+click, and Shift+click selections."""
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            # CTRL+CLICK: Toggle selection
            if index in self.selected_indices:
                self.selected_indices.remove(index)
                # Make sure we don't end up with zero selections
                if not self.selected_indices:
                    self.selected_indices = [self.active_index]
            else:
                self.selected_indices.append(index)
                self.active_index = index  # Make the newly toggled item the active index

        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            # SHIFT+CLICK: Select a range, starting from the active index
            start, end = self.active_index, index
            step = 1 if start <= end else -1

            for i in range(start, end + step, step):
                if i not in self.selected_indices:
                    self.selected_indices.append(i)
            self.active_index = index

        else:
            # NORMAL CLICK: Clear group selection (if any), and pick a single color
            self.selected_indices = [index]
            self.active_index = index

        self.refresh_selection_ui()

    def remove_colors(self, indices):
        lowest = indices[-1]     # for rebuild_grid
        clear_last = False

        # Delete colors unless we are at the final color
        for idx in indices:
            if len(self.palette_colors) <= 1:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction", "Palette must have at least 1 color."
                )
                clear_last = True
                break
            self.palette_colors.pop(idx)

        # If all colors were deleted, leave behind a single black color
        if clear_last:
            self.palette_colors = [QColor(0, 0, 0)]

        # Rebuild starting from the lowest (earliest) index
        rebuild_start = 0 if clear_last else lowest
        self.rebuild_grid(rebuild_start)

        # Adjust selection index
        self.selected_indices = [rebuild_start]
        self.active_index = rebuild_start
        self.refresh_selection_ui()

    def refresh_selection_ui(self):
        # Update active selection highlighting for all boxes
        for idx, box in enumerate(self.boxes):
            box.set_selected(idx in self.selected_indices)

        # Dynamic selection text
        count = len(self.selected_indices)
        if count > 1:
            self.index_label.setText(f"Selected: {count} Colors (Active: #{self.active_index})")
        else:
            self.index_label.setText(f"Selected Color: #{self.active_index}")

        # Editing panel will still reflect the active index color
        active_color = self.palette_colors[self.active_index]

        # Block input signals
        self.r_slider.blockSignals(True)
        self.g_slider.blockSignals(True)
        self.b_slider.blockSignals(True)
        self.hex_input.blockSignals(True)

        # Now, update sliders and preview safely
        _r = self.snap_to_md_colors(active_color.red())
        _g = self.snap_to_md_colors(active_color.green())
        _b = self.snap_to_md_colors(active_color.blue())

        self.r_slider.setValue(_r)
        self.g_slider.setValue(_g)
        self.b_slider.setValue(_b)

        self.r_val_label.setText(f"0x{MDCOLOR_VALUES[_r]:02X}")
        self.g_val_label.setText(f"0x{MDCOLOR_VALUES[_g]:02X}")
        self.b_val_label.setText(f"0x{MDCOLOR_VALUES[_b]:02X}")

        self.hex_input.setText(active_color.name().upper())
        self.update_preview_box(active_color)

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

            self.apply_color_change(snapped_color)
            self.refresh_selection_ui()

    def apply_color_change(self, color):
        self.palette_colors[self.active_index] = color
        self.boxes[self.active_index].set_color(color)
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
