import json
from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
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

        self.unsaved_changes = True

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

        self.unsaved_changes = True

    def clear_color(self, index):
        if not self.editor.selected_indices:
            return

        black = QColor(0, 0, 0)
        for idx in self.editor.selected_indices:
            self.editor.palette_colors[idx] = black
            self.editor.boxes[idx].set_color(black)

        self.editor.update_preview_box(black)

        self.unsaved_changes = True

    def delete_color(self, index):
        if not self.editor.selected_indices:
            return

        # Delete in reverse order to avoid issues with index shifting
        sorted_indices = sorted(self.editor.selected_indices, reverse=True)
        self.editor.remove_colors(sorted_indices)


class AdvancedEditDialog(QtW.QDialog):
    # Signal to apply changes to the palette's colors
    colors_applied = pyqtSignal(list)

    def __init__(self, editor, title="Advanced Editing"):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle(title)
        self.setMinimumSize(680, 260)

        # Temp palette structures
        self.original_colors = []
        self.result_colors = []
        self.preview_boxes = []

        # Setup this window
        self.init_ui()
        self.reload_from_editor()

        # Connect signals for live background updating
        self.editor.selection_changed.connect(self.reload_from_editor)
        self.editor.palette_changed.connect(self.reload_from_editor)

    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)
        content_layout = QtW.QHBoxLayout()

        # -----------------------------
        # LEFT PANEL: Options
        # -----------------------------
        options_layout = QtW.QVBoxLayout()

        # Target Scope Option
        scope_group = QtW.QGroupBox("Target Scope")
        scope_layout = QtW.QVBoxLayout(scope_group)

        self.opt_selected = QtW.QRadioButton("Selected Colors Only")
        self.opt_all = QtW.QRadioButton("Entire Palette")

        # Default scope selection based on active selection count
        if len(self.editor.selected_indices) > 1:
            self.opt_selected.setChecked(True)
        else:
            self.opt_all.setChecked(True)

        self.opt_selected.toggled.connect(self.update_preview)
        self.opt_all.toggled.connect(self.update_preview)

        scope_layout.addWidget(self.opt_selected)
        scope_layout.addWidget(self.opt_all)
        options_layout.addWidget(scope_group)

        # Hook for Subclass-specific UI
        self.setup_custom_options(options_layout)

        options_layout.addStretch()
        content_layout.addLayout(options_layout, stretch=1)

        # -----------------------------
        # RIGHT PANEL: Palette Preview
        # -----------------------------
        preview_group = QtW.QGroupBox("Preview")
        preview_group_layout = QtW.QVBoxLayout(preview_group)

        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(4)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(scroll_content)
        preview_group_layout.addWidget(scroll_area)
        content_layout.addWidget(preview_group, stretch=2)

        main_layout.addLayout(content_layout)

        # -----------------------------
        # BOTTOM PANEL: Action Buttons
        # -----------------------------
        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)

        btn_apply = btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok)
        btn_apply.setText("Apply")

        btn_apply.clicked.connect(self.on_apply)
        btn_box.rejected.connect(self.reject)
        main_layout.addWidget(btn_box)

    def on_apply(self):
        self.colors_applied.emit(self.result_colors)
        self.accept()

    def update_preview(self):
        only_selected = self.opt_selected.isChecked()

        for idx, original_color in enumerate(self.original_colors):
            # Check if color should be modified based on scope selection
            if only_selected and idx not in self.editor.selected_indices:
                self.result_colors[idx] = QColor(original_color)
            else:
                # Call the subclass-specific transformation
                self.result_colors[idx] = self.transform_color(original_color)

            # Update preview box color
            if idx < len(self.preview_boxes):
                self.preview_boxes[idx].setStyleSheet(
                    f"background-color: {self.result_colors[idx].name()}; border: 1px solid #444;"
                )

    def reload_from_editor(self):
        # Get updated colors and selections from the main window
        self.original_colors = [QColor(c) for c in self.editor.palette_colors]

        # Rebuild preview boxes if palette size changed
        if len(self.original_colors) != len(self.preview_boxes):
            self.rebuild_preview_grid()

        # Reset result array length to match original
        self.result_colors = [QColor(c) for c in self.original_colors]
        self.update_preview()

    def rebuild_preview_grid(self):
        # Rebuild preview grid when palette size changes
        for box in self.preview_boxes:
            box.deleteLater()
        self.preview_boxes.clear()

        MAX_COLUMNS = 16
        for idx, color in enumerate(self.original_colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS
            box = QtW.QFrame()
            box.setFixedSize(20, 20)
            self.grid_layout.addWidget(box, row, col)
            self.preview_boxes.append(box)

    def changeEvent(self, a0):
        # Sync with main window whenever this window gains focus
        if a0.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.reload_from_editor()
        super().changeEvent(a0)

    # --- Overridden by dialog subclasses ---
    def setup_custom_options(self, layout):
        pass

    # --- Overridden by dialog subclasses ---
    def transform_color(self, original_color: QColor) -> QColor:
        return QColor(original_color)


""" The following classes are subtypes for the AdvancedEditDialog class.
    They contain their own functions that edit facets of the main editor.
"""
class GreyscaleDialog(AdvancedEditDialog):
    def __init__(self, editor):
        super().__init__(editor, title="Apply Greyscale")

    def setup_custom_options(self, layout):
        # -----------------------------
        # LEFT PANEL MOD: Greyscale Options
        # -----------------------------
        method_group = QtW.QGroupBox("Greyscale Method")
        method_layout = QtW.QVBoxLayout(method_group)

        self.gs_luminosity = QtW.QRadioButton("Luminosity")
        self.gs_luminosity.setToolTip("Weighted (0.299R, 0.587G, 0.114B)")
        self.gs_luminosity.setChecked(True)  # Default option

        self.gs_lightness = QtW.QRadioButton("Lightness")
        self.gs_lightness.setToolTip("(Max(R,G,B) + Min(R,G,B)) / 2")

        self.gs_average = QtW.QRadioButton("Average")
        self.gs_average.setToolTip("(R + G + B) / 3")

        for rad in (self.gs_luminosity, self.gs_lightness, self.gs_average):
            rad.toggled.connect(self.update_preview)
            method_layout.addWidget(rad)

        layout.addWidget(method_group)
        #layout.addStretch()
        #content_layout.addLayout(layout, stretch=1)

    def transform_color(self, original_color):
        _r, _g, _b = original_color.red(), original_color.green(), original_color.blue()

        # Calculate grey color value based on selected greyscale method
        if self.gs_luminosity.isChecked():
            grey_val = int(0.299 * _r + 0.587 * _g + 0.114 * _b)
        elif self.gs_lightness.isChecked():
            grey_val = int((max(_r, _g, _b) + min(_r, _g, _b)) / 2)
        else:  # Average
            grey_val = int((_r + _g + _b) / 3)

        # Snap calculated grey to Mega Drive color limits
        step = PaletteEditor.snap_to_md_colors(grey_val)
        md_grey = MDCOLOR_VALUES[step]

        return QColor(md_grey, md_grey, md_grey)


class InvertColorsDialog(AdvancedEditDialog):
    # Signal to apply changes to the palette's colors
    colors_applied = pyqtSignal(list)

    def __init__(self, editor):
        super().__init__(editor, title="Invert Colors")

    def setup_custom_options(self, layout):
        # -----------------------------
        # LEFT PANEL MOD: Inversion Options
        # -----------------------------
        channel_group = QtW.QGroupBox("Invert Channels")
        channel_layout = QtW.QVBoxLayout(channel_group)

        # Unlike the original Sonic Triad, users can partially invert colors
        self.chk_red = QtW.QCheckBox("Red")
        self.chk_green = QtW.QCheckBox("Green")
        self.chk_blue = QtW.QCheckBox("Blue")

        # All are checked by default for full inversion
        for chk in (self.chk_red, self.chk_green, self.chk_blue):
            chk.setChecked(True)
            chk.toggled.connect(self.update_preview)
            channel_layout.addWidget(chk)

        layout.addWidget(channel_group)
        #layout.addStretch()
        #content_layout.addLayout(layout, stretch=1)

    def transform_color(self, original_color):
        invert_r = self.chk_red.isChecked()
        invert_g = self.chk_green.isChecked()
        invert_b = self.chk_blue.isChecked()

        # Snap current RGB channels to 3-bit Genesis steps (0 to 7)
        r_step = PaletteEditor.snap_to_md_colors(original_color.red())
        g_step = PaletteEditor.snap_to_md_colors(original_color.green())
        b_step = PaletteEditor.snap_to_md_colors(original_color.blue())

        # Invert MD steps (7 - step) if channel checkbox is enabled
        new_r = MDCOLOR_VALUES[7 - r_step] if invert_r else original_color.red()
        new_g = MDCOLOR_VALUES[7 - g_step] if invert_g else original_color.green()
        new_b = MDCOLOR_VALUES[7 - b_step] if invert_b else original_color.blue()

        return QColor(new_r, new_g, new_b)


class PaletteEditor(QtW.QWidget):
    # Signals for advanced editing preview sync
    selection_changed = pyqtSignal()
    palette_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Internal Palette Storage (1 to 128 colors)
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]  # Default 64 colors
        self.boxes = []

        self.selected_indices = []
        self.active_index = 0

        self.active_palette_path = None
        self.project_palette_paths = []

        self._unsaved_changes = False
        self._current_dropdown_index = -1

        self.init_ui()

        # Advanced Editing window handlers (Might consolidate later)
        self.greyscale_dialog = None
        self.invert_dialog = None

    def init_ui(self):
        self.main_layout = QtW.QHBoxLayout(self)

        # -----------------------------
        # LEFT PANEL: Dynamic Color Grid
        # -----------------------------
        self.color_box = QtW.QGroupBox(
            "Palette Grid (Left Click: Select;"+
            "    Left+Shift: Mass Select;"+
            "    Left+Ctrl: Toggle Selection;"+
            "    Right Click: Context Menu)"
        )
        self.color_layout = QtW.QVBoxLayout(self.color_box)

        # Scroll area in case palette grid extends past the window border
        scroll_area = QtW.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QtW.QWidget()

        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll_area.setWidget(scroll_content)
        self.color_layout.addWidget(scroll_area)

        self.main_layout.addWidget(self.color_box, stretch=2)

        # -----------------------------
        # RIGHT PANEL: Editing Controls
        # -----------------------------
        self.editor_panel = QtW.QVBoxLayout()

        # Palette File Dropdown
        self.pal_select_group = QtW.QGroupBox("Select Palette")
        self.pal_select_layout = QtW.QVBoxLayout(self.pal_select_group)

        self.pal_dropdown = QtW.QComboBox()
        self.pal_dropdown.setToolTip("Select a palette file from the active project")
        self.pal_dropdown.currentIndexChanged.connect(self.on_pal_dropdown_changed)
        self.pal_select_layout.addWidget(self.pal_dropdown, stretch=1)

        # File Buttons
        btn_grid = QtW.QGridLayout()
        self.btn_new = QtW.QPushButton("New")
        self.btn_load = QtW.QPushButton("Load")
        self.btn_save = QtW.QPushButton("Save")
        self.btn_saveas = QtW.QPushButton("Save As...")
        self.btn_remove = QtW.QPushButton("Remove")
        for btn in (self.btn_new, self.btn_load, self.btn_save, self.btn_saveas, self.btn_remove):
            btn.setFixedWidth(55)

        self.btn_new.clicked.connect(lambda: self.check_unsaved_changes(self.file_palette_new))
        self.btn_load.clicked.connect(lambda: self.check_unsaved_changes(self.file_palette_load))
        self.btn_save.clicked.connect(self.file_palette_save)
        self.btn_saveas.clicked.connect(self.file_palette_save_as)
        self.btn_remove.clicked.connect(self.file_palette_remove)

        btn_grid.addWidget(self.btn_new, 0, 0)
        btn_grid.addWidget(self.btn_load, 0, 1)
        btn_grid.addWidget(self.btn_save, 0, 2)
        btn_grid.addWidget(self.btn_saveas, 0, 3)
        btn_grid.addWidget(self.btn_remove, 0, 4)

        self.pal_select_layout.addLayout(btn_grid)
        self.editor_panel.addWidget(self.pal_select_group)

        # Color Entry Edit Buttons
        self.pal_edit_group = QtW.QGroupBox("Palette Editing")
        self.pal_edit_layout = QtW.QVBoxLayout(self.pal_edit_group)

        # Edit Buttons (Features to be considered: Undo, Redo, Resize (Add/Remove), Shift)
        btn_grid_edit = QtW.QGridLayout()
        self.btn_undo = QtW.QPushButton("Undo")
        self.btn_redo = QtW.QPushButton("Redo")
        self.btn_resize = QtW.QPushButton("Resize")
        for btn in (self.btn_undo, self.btn_redo, self.btn_resize):
            btn.setFixedWidth(60)

        self.btn_resize.clicked.connect(self.edit_palette_resize)

        btn_grid_edit.addWidget(self.btn_undo, 0, 0)
        btn_grid_edit.addWidget(self.btn_redo, 0, 1)
        btn_grid_edit.addWidget(self.btn_resize, 0, 2)

        self.pal_edit_layout.addLayout(btn_grid_edit)
        self.editor_panel.addWidget(self.pal_edit_group)

        # Color Editing Tool
        self.control_group = QtW.QGroupBox("Color Editing")
        self.control_layout = QtW.QVBoxLayout(self.control_group)

        # Selected Index Label
        self.index_label = QtW.QLabel("Selected Color: #0")
        self.index_label.setObjectName("infoLabel")
        self.control_layout.addWidget(self.index_label)

        # Hex Preview & Large Color Box
        self.preview_layout = QtW.QHBoxLayout()
        self.large_preview = QtW.QFrame()
        self.large_preview.setFixedSize(60, 60)

        self.hex_input = QtW.QLineEdit("#000000")
        self.hex_input.setMaxLength(7)
        self.hex_input.editingFinished.connect(self.on_hex_edited)

        self.preview_layout.addWidget(self.large_preview)
        self.preview_layout.addLayout(self.create_form_row("Hex Value:", self.hex_input))
        self.control_layout.addLayout(self.preview_layout)

        self.control_layout.addSpacing(15)

        self.r_slider = self.create_step_slider(self.on_slider_changed)
        self.g_slider = self.create_step_slider(self.on_slider_changed)
        self.b_slider = self.create_step_slider(self.on_slider_changed)

        self.r_val_label = QtW.QLabel("0")
        self.g_val_label = QtW.QLabel("0")
        self.b_val_label = QtW.QLabel("0")

        self.control_layout.addLayout(self.create_slider_row("Red:", self.r_slider, self.r_val_label))
        self.control_layout.addLayout(self.create_slider_row("Green:", self.g_slider, self.g_val_label))
        self.control_layout.addLayout(self.create_slider_row("Blue:", self.b_slider, self.b_val_label))

        self.control_layout.addStretch()
        self.editor_panel.addWidget(self.control_group, stretch=1)

        # Advanced Editing Functions
        self.advanced_group = QtW.QGroupBox("Advanced Functions")
        self.advanced_layout = QtW.QVBoxLayout(self.advanced_group)

        # Advanced Option Buttons
        btn_grid_adv = QtW.QGridLayout()
        self.btn_blend = QtW.QPushButton("Color Blend")
        self.btn_grey = QtW.QPushButton("Greyscale")
        self.btn_invert = QtW.QPushButton("Invert Colors")
        self.btn_gradient = QtW.QPushButton("Build Gradient")
        for btn in (self.btn_undo, self.btn_redo, self.btn_resize):
            btn.setFixedWidth(80)

        self.btn_grey.clicked.connect(self.adv_greyscale_colors)
        self.btn_invert.clicked.connect(self.adv_invert_colors)

        btn_grid_adv.addWidget(self.btn_blend, 0, 0)
        btn_grid_adv.addWidget(self.btn_grey, 0, 1)
        btn_grid_adv.addWidget(self.btn_invert, 1, 0)
        btn_grid_adv.addWidget(self.btn_gradient, 1, 1)

        self.advanced_layout.addLayout(btn_grid_adv)
        self.editor_panel.addWidget(self.advanced_group)

        self.main_layout.addLayout(self.editor_panel, stretch=1)

        # Build initial grid UI and set selection to color 0
        self.set_palette_data(self.palette_colors)

    def file_palette_new(self):
        count, ok = QtW.QInputDialog.getInt(
            self, "New Palette", "Number of colors:", 16, 1, 128, 1
        )

        # Exit if the user cancels
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

    def file_palette_load(self):
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

    def file_palette_save(self):
        if self.active_palette_path and self.active_palette_path.parent.exists():
            self.write_palette_to_disk(self.active_palette_path)
        else:
            self.file_palette_save_as()

    def file_palette_save_as(self):
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

    def file_palette_remove(self):
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

    def edit_palette_resize(self):
        current_size = len(self.palette_colors)
        new_size, ok = QtW.QInputDialog.getInt(
            self, "Resize Palette", "Number of colors:", current_size, 1, 128, 1
        )

        # Exit if the user cancels or doesn't change the size
        if not ok or new_size == current_size:
            return

        if new_size > current_size:
            # Append black colors
            self.palette_colors.extend([QColor(0, 0, 0)] * (new_size - current_size))

            # Rebuild starting from the first newly added index
            self.rebuild_grid(current_size)

        else:
            # Truncate the palette
            self.palette_colors = self.palette_colors[:new_size]
            self.rebuild_grid(new_size)

            # Filter out-of-bounds selected indices
            self.selected_indices = [idx for idx in self.selected_indices if idx < new_size]

            # If all selected colors were truncated, fallback to the last valid color
            if not self.selected_indices:
                self.selected_indices = [new_size - 1]

            # Adjust the active index if out-of-bounds
            if self.active_index >= new_size:
                self.active_index = self.selected_indices[-1]

            self.refresh_selection_ui()

            self.unsaved_changes = True

    def adv_greyscale_colors(self):
        # If this window is already open, bring it to focus instead of opening a duplicate
        if self.greyscale_dialog is not None and self.greyscale_dialog.isVisible():
            self.greyscale_dialog.raise_()
            self.greyscale_dialog.activateWindow()
            return

        # Opens new window for effect preview
        self.greyscale_dialog = GreyscaleDialog(self)
        self.greyscale_dialog.colors_applied.connect(self.apply_color_effect)
        self.greyscale_dialog.show()

    def adv_invert_colors(self):
        # If this window is already open, bring it to focus instead of opening a duplicate
        if self.invert_dialog is not None and self.invert_dialog.isVisible():
            self.invert_dialog.raise_()
            self.invert_dialog.activateWindow()
            return

        # Opens new window for effect preview
        self.invert_dialog = InvertColorsDialog(self)
        self.invert_dialog.colors_applied.connect(self.apply_color_effect)
        self.invert_dialog.show()

    def apply_color_effect(self, new_colors):
        # Effect is only applied if the user selects "Apply"
        self.palette_colors = new_colors
        self.rebuild_grid()
        self.refresh_selection_ui()
        self.unsaved_changes = True

    def write_palette_to_disk(self, path: Path):
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
            self.unsaved_changes = False    # clear flag on save
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
        # Ignore if only reverting/resetting UI
        if index == self._current_dropdown_index or index == -1:
            return

        def load_new_selection():
            # Load selected palette
            self._current_dropdown_index = index
            path = self.pal_dropdown.itemData(index)
            if path and isinstance(path, Path):
                self.load_palette_data(path)

        def revert_selection():
            # Silently revert dropdown, don't replace palette
            self.pal_dropdown.blockSignals(True)
            self.pal_dropdown.setCurrentIndex(self._current_dropdown_index)
            self.pal_dropdown.blockSignals(False)

        self.check_unsaved_changes(load_new_selection, revert_selection)

    def load_palette_data(self, path: Path):
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
            self.unsaved_changes = False  # clear flag on load

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

        # Emit signal so open dialogs know palette size changed
        self.palette_changed.emit()

    def set_palette_data(self, colors: list[QColor]):
        # Constrain to range [1, 128]; To-Do: Make the first line optional if palette_colors is already defined
        self.palette_colors = colors[:128] if colors else [QColor(0, 0, 0)]
        self.rebuild_grid()
        self.selected_indices = [0]
        self.active_index = 0
        self.refresh_selection_ui()

    def select_colors(self, index: int, modifiers):
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

        self.unsaved_changes = True

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

        # Emit signal so open dialogs know selection or active colors changed
        self.selection_changed.emit()

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

        self.unsaved_changes = True

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

            self.unsaved_changes = True

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

    @property
    def unsaved_changes(self):
        return self._unsaved_changes

    @unsaved_changes.setter
    def unsaved_changes(self, value=True):
        self._unsaved_changes = value
        if value:
            self.pal_select_group.setTitle("Select Palette (Unsaved Changes)")
        else:
            self.pal_select_group.setTitle("Select Palette")

    def show_save_prompt_dialog(self):
        prompt = QtW.QMessageBox(self)
        prompt.setWindowTitle("Unsaved Changes")
        prompt.setText("You have unsaved changes in the current palette. What would you like to do?")

        btn_save = prompt.addButton("Save", QtW.QMessageBox.ButtonRole.AcceptRole)
        btn_save_as = prompt.addButton("Save As...", QtW.QMessageBox.ButtonRole.AcceptRole)
        btn_dont_save = prompt.addButton("Don't Save", QtW.QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = prompt.addButton("Cancel", QtW.QMessageBox.ButtonRole.RejectRole)

        prompt.exec()

        clicked_btn = prompt.clickedButton()
        if clicked_btn == btn_save:
            return "Save"
        elif clicked_btn == btn_save_as:
            return "Save As"
        elif clicked_btn == btn_dont_save:
            return "Don't Save"
        else:
            return "Cancel"

    def check_unsaved_changes(self, pending_action_callback, cancel_callback=None):
        if not self.unsaved_changes:
            pending_action_callback()
            return

        user_choice = self.show_save_prompt_dialog()

        if user_choice == "Save":
            self.file_palette_save()
            pending_action_callback()
        elif user_choice == "Save As":
            self.file_palette_save_as()
            pending_action_callback()
        elif user_choice == "Don't Save":
            pending_action_callback()
        elif user_choice == "Cancel":
            # Revert UI state if needed
            if cancel_callback:
                cancel_callback()
            return

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
