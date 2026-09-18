import json
from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QEvent, QTimer
from PyQt6.QtGui import QColor

import PaletteEditor.color_box as cb
from PaletteEditor.pal_dialog import (
    ColorBlendDialog,
    GreyscaleDialog,
    GradientBuilderDialog,
    PaletteExtractDialog
)

from UI.md_color import snap_to_md_colors, ColorLibraryDialog

from Constants import MDCOLOR_VALUES, PALLINE_COLORS, PALEDIT_MAXCOLORS

class PaletteEditor(QtW.QWidget):
    # Signals for advanced editing preview sync
    selection_changed = pyqtSignal()
    palette_changed = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Internal Palette Storage (1 to 256 colors)
        self.palette_colors = [QColor(0, 0, 0) for _i in range(64)]  # Default 64 colors
        self.boxes = []

        # Undo/Redo stacks
        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 50

        self.selected_indices = []
        self.active_index = 0

        self.clipboard_colors = []
        self.clipboard_boxes = []

        self.active_palette_path = None
        self.project_palette_paths = []

        self._unsaved_changes = False
        self._current_dropdown_index = -1

        # Advanced Editing window handler
        self.active_advanced_dialog = None

        self.init_ui()

    # To-do: Break this apart and consolidate some of the widget generation
    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)

        # -----------------------------
        # TOP PANEL: File Functions and Palette Selection
        # -----------------------------
        pal_select_layout = QtW.QHBoxLayout()
        pal_select_layout.setSpacing(4)
        pal_select_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Palette File Dropdown
        self.pal_dropdown = QtW.QComboBox()
        self.pal_dropdown.setMaximumWidth(300)
        self.pal_dropdown.setFixedHeight(25)
        self.pal_dropdown.setSizePolicy(QtW.QSizePolicy.Policy.Maximum, QtW.QSizePolicy.Policy.Maximum)
        self.pal_dropdown.setToolTip("Select a palette file from the active project")
        self.pal_dropdown.currentIndexChanged.connect(self.on_pal_dropdown_changed)
        pal_select_layout.addWidget(self.pal_dropdown, stretch=1)

        # File Buttons
        btn_new = QtW.QPushButton("New")
        btn_load = QtW.QPushButton("Load")
        btn_save = QtW.QPushButton("Save")
        btn_saveas = QtW.QPushButton("Save As...")
        btn_remove = QtW.QPushButton("Remove")
        for btn in (btn_new, btn_load, btn_save, btn_saveas, btn_remove):
            btn.setFixedSize(QSize(65, 25))

        btn_new.clicked.connect(lambda: self.check_unsaved_changes(self.file_palette_new))
        btn_load.clicked.connect(lambda: self.check_unsaved_changes(self.file_palette_load))
        btn_save.clicked.connect(self.file_palette_save)
        btn_saveas.clicked.connect(self.file_palette_save_as)
        btn_remove.clicked.connect(self.file_palette_remove)

        pal_select_layout.addWidget(btn_new)
        pal_select_layout.addWidget(btn_load)
        pal_select_layout.addWidget(btn_save)
        pal_select_layout.addWidget(btn_saveas)
        pal_select_layout.addWidget(btn_remove)

        self.unsaved_label = QtW.QLabel("Unsaved Changes")
        self.unsaved_label.setVisible(self._unsaved_changes)
        pal_select_layout.addWidget(self.unsaved_label)

        pal_select_layout.addStretch()

        main_layout.addLayout(pal_select_layout)

        # Content layout below the upper level
        content_layout = QtW.QHBoxLayout()
        main_layout.addLayout(content_layout, stretch=1)

        # -----------------------------
        # LEFT PANEL: Palette and Clipboard
        # -----------------------------
        # Palette Grid
        color_box = QtW.QGroupBox("Palette")
        color_layout = QtW.QVBoxLayout(color_box)

        # Palette Editing Toolbar
        pal_edit_layout = QtW.QHBoxLayout()
        pal_edit_layout.setSpacing(4)

        self.btn_undo = QtW.QPushButton("Undo")
        self.btn_redo = QtW.QPushButton("Redo")
        self.btn_copy = QtW.QPushButton("Copy")
        self.btn_cut = QtW.QPushButton("Cut")
        self.btn_paste = QtW.QPushButton("Paste")
        btn_resize = QtW.QPushButton("Resize Palette")
        for btn in (self.btn_undo, self.btn_redo, self.btn_copy, self.btn_cut, self.btn_paste):
            btn.setFixedSize(QSize(55, 25))
        btn_resize.setFixedSize(QSize(85, 25))

        self.btn_undo.clicked.connect(self.edit_palette_undo)
        self.btn_redo.clicked.connect(self.edit_palette_redo)
        self.btn_copy.clicked.connect(self.copy_colors)
        self.btn_cut.clicked.connect(lambda: self.copy_colors(True))
        self.btn_paste.clicked.connect(lambda: self.paste_colors("over", self.active_index))
        btn_resize.clicked.connect(self.edit_palette_resize)

        self.update_undo_redo()  # Disable Undo/Redo at the start

        pal_edit_layout.addWidget(self.btn_undo)
        pal_edit_layout.addWidget(self.btn_redo)
        pal_edit_layout.addWidget(self.btn_copy)
        pal_edit_layout.addWidget(self.btn_cut)
        pal_edit_layout.addWidget(self.btn_paste)
        pal_edit_layout.addWidget(btn_resize)
        pal_edit_layout.addStretch()

        color_layout.addLayout(pal_edit_layout)

        # Palette Selection Instructions
        instruction_label = QtW.QLabel(
            "Click to select | Shift-click for range | "
            "Ctrl-click to toggle | Right-click for options"
        )
        instruction_label.setWordWrap(True)

        instruction_font = instruction_label.font()
        instruction_font.setPointSizeF(max(8.0, instruction_font.pointSizeF() - 1.0))
        instruction_label.setFont(instruction_font)

        color_layout.addWidget(instruction_label)

        # Scrollable palette grid (w/ resizing ColorBox)
        self.palette_scroll = QtW.QScrollArea()
        self.palette_scroll.setWidgetResizable(True)

        # Reserve scrollbar space so its appearance cannot change cell size
        self.palette_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        scroll_content = QtW.QWidget()

        # Palette grid aligns to the top-left corner
        self.grid_layout = QtW.QGridLayout(scroll_content)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.palette_scroll.setWidget(scroll_content)
        color_layout.addWidget(self.palette_scroll)

        # Defer resizing until Qt has updated the viewport geometry
        self.palette_resize_timer = QTimer(self)
        self.palette_resize_timer.setSingleShot(True)
        self.palette_resize_timer.timeout.connect(self.resize_palette_boxes)

        self.palette_scroll.viewport().installEventFilter(self)

        # Palette Clipboard
        self.clipboard_group = QtW.QGroupBox()
        clipboard_layout = QtW.QVBoxLayout(self.clipboard_group)

        clip_header_layout = QtW.QHBoxLayout()

        self.btn_toggle_clipboard = QtW.QToolButton()
        self.btn_toggle_clipboard.setText("Clipboard")
        self.btn_toggle_clipboard.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn_toggle_clipboard.setArrowType(Qt.ArrowType.DownArrow)
        self.btn_toggle_clipboard.setCheckable(True)
        self.btn_toggle_clipboard.setChecked(True)
        self.btn_toggle_clipboard.setAutoRaise(True)
        self.btn_toggle_clipboard.toggled.connect(self.toggle_clipboard)

        self.btn_clear_clipboard = QtW.QPushButton("Clear")
        self.btn_clear_clipboard.clicked.connect(self.clear_clipboard)

        clip_header_layout.addWidget(self.btn_toggle_clipboard)
        clip_header_layout.addStretch()
        clip_header_layout.addWidget(self.btn_clear_clipboard)

        clipboard_layout.addLayout(clip_header_layout)

        self.clipboard_scroll = QtW.QScrollArea()
        self.clipboard_scroll.setWidgetResizable(True)
        clipboard_content = QtW.QWidget()

        self.clipboard_empty_label = None

        self.clipboard_grid_layout = QtW.QGridLayout(clipboard_content)
        self.clipboard_grid_layout.setSpacing(6)
        self.clipboard_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.clipboard_scroll.setWidget(clipboard_content)
        clipboard_layout.addWidget(self.clipboard_scroll)

        # Create a splitter between the palette and the clipboard
        self.palette_splitter = QtW.QSplitter(Qt.Orientation.Vertical)
        self.palette_splitter.addWidget(color_box)
        self.palette_splitter.addWidget(self.clipboard_group)
        self.palette_splitter.setChildrenCollapsible(False)
        self.palette_splitter.setHandleWidth(8)
        self.palette_splitter.setStretchFactor(0, 2)
        self.palette_splitter.setStretchFactor(1, 1)
        self.palette_splitter.setSizes([400, 200])

        self.clipboard_splitter_sizes = None

        content_layout.addWidget(self.palette_splitter, stretch=2)

        # -----------------------------
        # RIGHT PANEL: Editing Controls
        # -----------------------------
        # Color Editing Tool
        control_group = QtW.QGroupBox(" Color Editing")
        control_group.setObjectName("ControlsGroup")
        control_layout = QtW.QVBoxLayout(control_group)
        # Preserve the space required by the controls and their spacing
        control_layout.setSizeConstraint(QtW.QLayout.SizeConstraint.SetMinimumSize)

        # Selected Index Label
        self.index_label = QtW.QLabel("Selected Color: #0")
        self.index_label.setObjectName("infoLabel")
        control_layout.addWidget(self.index_label)

        # Hex Preview & Large Color Box
        preview_layout = QtW.QHBoxLayout()
        self.large_preview = cb.PreviewColorBox()
        self.large_preview.clicked.connect(self.open_color_library)

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

        # Separate individual color controls from batch editing
        batch_separator = QtW.QFrame()
        batch_separator.setFrameShape(QtW.QFrame.Shape.HLine)
        batch_separator.setFrameShadow(QtW.QFrame.Shadow.Sunken)

        control_layout.addSpacing(8)
        control_layout.addWidget(batch_separator)
        control_layout.addSpacing(8)

        # Batch Editing
        mass_edit_label = QtW.QLabel("Batch Editing")
        mass_edit_label.setObjectName("infoLabel")
        control_layout.addWidget(mass_edit_label)

        mass_scope_layout = QtW.QHBoxLayout()
        self.opt_mass_all = QtW.QRadioButton("Full Palette")
        self.opt_mass_selected = QtW.QRadioButton("Selected Color(s)")
        self.opt_mass_all.setChecked(True)

        mass_scope_layout.addWidget(self.opt_mass_all)
        mass_scope_layout.addWidget(self.opt_mass_selected)
        control_layout.addLayout(mass_scope_layout)

        # Batch Channel Editing
        batch_edit_layout = QtW.QGridLayout()
        batch_edit_layout.setHorizontalSpacing(6)
        batch_edit_layout.setVerticalSpacing(4)

        channels = [
            ("Red", 'r'),
            ("Green", 'g'),
            ("Blue", 'b'),
        ]

        for idx, (label_text, ch) in enumerate(channels):
            lbl = QtW.QLabel(f"{label_text} Channel:")

            btn_minus = QtW.QPushButton("−")
            btn_plus = QtW.QPushButton("+")
            btn_invert = QtW.QPushButton("Invert")
            btn_clear = QtW.QPushButton("Clear")
            btn_minus.setFixedSize(QSize(40, 25))
            btn_plus.setFixedSize(QSize(40, 25))
            btn_invert.setFixedSize(QSize(60, 25))
            btn_clear.setFixedSize(QSize(55, 25))

            btn_minus.setToolTip(f"Decrease {label_text.lower()} by one step for all chosen colors")
            btn_plus.setToolTip(f"Increase {label_text.lower()} by one step for all chosen colors")
            btn_invert.setToolTip(f"Invert the {label_text.lower()} channel for all chosen colors")
            btn_clear.setToolTip(f"Clear the {label_text.lower()} channel to 0 for all chosen colors")

            btn_minus.clicked.connect(lambda _, channel=ch: self.batch_shift_color(-1, channel))
            btn_plus.clicked.connect(lambda _, channel=ch: self.batch_shift_color(1, channel))
            btn_invert.clicked.connect(lambda _, channel=ch: self.batch_invert_color(channel))
            btn_clear.clicked.connect(lambda _, channel=ch: self.batch_clear_color(channel))

            batch_edit_layout.addWidget(lbl, idx, 0)
            batch_edit_layout.addWidget(btn_minus, idx, 1)
            batch_edit_layout.addWidget(btn_plus, idx, 2)
            batch_edit_layout.addWidget(btn_invert, idx, 3)
            batch_edit_layout.addWidget(btn_clear, idx, 4)

        rows = len(channels)
        lbl = QtW.QLabel("All Channels:")
        batch_edit_layout.addWidget(lbl, rows, 0)

        # Decrease all three channels within the chosen batch scope
        btn_minus_colors = QtW.QPushButton("-")
        btn_minus_colors.setToolTip("Decrease RGB channels for all chosen colors")
        btn_minus_colors.clicked.connect(lambda: self.batch_shift_color(-1))
        batch_edit_layout.addWidget(btn_minus_colors, rows, 1)
        btn_minus_colors.setFixedSize(QSize(40, 25))

        # Increase all three channels within the chosen batch scope
        btn_plus_colors = QtW.QPushButton("+")
        btn_plus_colors.setToolTip("Increase RGB channels for all chosen colors")
        btn_plus_colors.clicked.connect(lambda: self.batch_shift_color(1))
        batch_edit_layout.addWidget(btn_plus_colors, rows, 2)
        btn_plus_colors.setFixedSize(QSize(40, 25))

        # Invert all three channels within the chosen batch scope
        btn_invert_colors = QtW.QPushButton("Invert")
        btn_invert_colors.setToolTip("Invert RGB channels for all chosen colors")
        btn_invert_colors.clicked.connect(lambda: self.batch_invert_color())
        batch_edit_layout.addWidget(btn_invert_colors, rows, 3)
        btn_invert_colors.setFixedSize(QSize(60, 25))

        # Clear all three channels within the chosen batch scope
        btn_clear_colors = QtW.QPushButton("Clear")
        btn_clear_colors.setToolTip("Clear RGB channels to 0 for all chosen colors")
        btn_clear_colors.clicked.connect(lambda: self.batch_clear_color())
        batch_edit_layout.addWidget(btn_clear_colors, rows, 4)
        btn_clear_colors.setFixedSize(QSize(55, 25))

        # Keep the controls together, with spare space on the right
        batch_edit_layout.setColumnStretch(5, 1)

        control_layout.addLayout(batch_edit_layout)

        # Shift Selected Colors
        shift_layout = QtW.QHBoxLayout()
        shift_layout.setSpacing(4)

        shift_label = QtW.QLabel("Shift selected colors:")
        self.btn_shift_L = QtW.QPushButton("<< Left")
        self.btn_shift_R = QtW.QPushButton("Right >>")

        self.btn_shift_L.setToolTip("Rotate selected colors left, wrapping the first to the end")
        self.btn_shift_R.setToolTip("Rotate selected colors right, wrapping the last to the start")

        self.btn_shift_L.clicked.connect(lambda: self.edit_palette_shift("left"))
        self.btn_shift_R.clicked.connect(lambda: self.edit_palette_shift("right"))

        shift_layout.addWidget(shift_label)
        shift_layout.addWidget(self.btn_shift_L)
        shift_layout.addWidget(self.btn_shift_R)
        shift_layout.addStretch()

        control_layout.addLayout(shift_layout)

        # Advanced Color Editing
        advanced_separator = QtW.QFrame()
        advanced_separator.setFrameShape(QtW.QFrame.Shape.HLine)
        advanced_separator.setFrameShadow(QtW.QFrame.Shadow.Sunken)

        control_layout.addSpacing(8)
        control_layout.addWidget(advanced_separator)
        control_layout.addSpacing(8)

        advanced_label = QtW.QLabel("Advanced Color Editing")
        advanced_label.setObjectName("infoLabel")
        control_layout.addWidget(advanced_label)

        # Advanced Option Buttons
        btn_grid_adv = QtW.QGridLayout()
        btn_grid_adv.setHorizontalSpacing(6)
        btn_grid_adv.setVerticalSpacing(6)
        btn_grid_adv.setColumnStretch(0, 1)
        btn_grid_adv.setColumnStretch(1, 1)

        btn_blend = QtW.QPushButton("Color Blending")
        btn_grey = QtW.QPushButton("Greyscaling")
        btn_gradient = QtW.QPushButton("Build Color Gradient")
        btn_extract = QtW.QPushButton("Extract Palette from Image")

        btn_blend.clicked.connect(self.adv_blend_colors)
        btn_grey.clicked.connect(self.adv_greyscale_colors)
        btn_gradient.clicked.connect(self.adv_build_gradient)
        btn_extract.clicked.connect(self.adv_extract_palette)

        btn_grid_adv.addWidget(btn_blend, 0, 0, 1, 1)
        btn_grid_adv.addWidget(btn_grey, 0, 1, 1, 1)
        btn_grid_adv.addWidget(btn_gradient, 1, 0, 1, 2)
        btn_grid_adv.addWidget(btn_extract, 2, 0, 1, 2)

        # Match the minimum height of the batch buttons
        for btn in (
            self.btn_shift_L,
            self.btn_shift_R,
            btn_blend,
            btn_grey,
            btn_gradient,
            btn_extract,
        ):
            btn.setMinimumHeight(25)

        control_layout.addLayout(btn_grid_adv)

        # Keep all editing sections together at the top
        control_layout.addStretch()

        # Scroll when the window cannot accommodate the full sidebar
        self.controls_scroll = QtW.QScrollArea()

        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.controls_scroll.setWidget(control_group)

        # Don't color this like a viewer window (Which would happen with scrolling windows.
        self.controls_scroll.viewport().setAutoFillBackground(False)
        control_group.setAutoFillBackground(False)

        content_layout.addWidget(self.controls_scroll, stretch=1)

        # Build initial grid UI and set selection to color 0
        self.set_palette_data(self.palette_colors)
        self.refresh_clipboard()
        self.btn_toggle_clipboard.setChecked(False)

    def file_palette_new(self):
        # To-Do: Clean up this flow. It should work as follows:
        # Prepare the new palette.
        # Write it and check success (it currently does this last, though this can fail).
        # Register it in the project only after success (Doing this before save can cause a bug).

        count, ok = QtW.QInputDialog.getInt(
            self, "New Palette", "Number of colors:", 16, 1, PALEDIT_MAXCOLORS, 1
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
                    QtW.QMessageBox.warning(
                        self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}"
                    )

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
            self, "Load Palette", start_dir, "Palette Files (*.bin *.pal);;All Files (*)"
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
            return self.file_palette_save_as()

    def file_palette_save_as(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "Save Palette As", start_dir, "Genesis Palette (*.bin *.pal);;All Files (*)"
        )

        # Failed Save
        if not file_path:
            return False

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

        # Save new palette copy to disk
        if not self.write_palette_to_disk(path):
            return False

        # Add path to the editor's list and select it for editing
        self.register_and_select_palette(path)

        # Successful Save
        return True

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
                    QtW.QMessageBox.warning(
                        self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}"
                    )

        # Remove entry and refresh dropdown
        if self.active_palette_path in self.project_palette_paths:
            self.project_palette_paths.remove(self.active_palette_path)

        self.active_palette_path = None
        self.populate_palette_list(self.project_palette_paths)

    def validate_selection(self):
        # Filter out-of-bounds selected indices
        self.selected_indices = [
            idx for idx in self.selected_indices
            if 0 <= idx < len(self.palette_colors)
        ]

        # Adjust the active index if out-of-bounds
        self.active_index = max(
            0, min(self.active_index, len(self.palette_colors) - 1)
        )

        # Always retain at least one selected color
        if not self.selected_indices:
            self.selected_indices = [self.active_index]

        # The active color should belong to the selection
        elif self.active_index not in self.selected_indices:
            self.active_index = self.selected_indices[-1]

    def edit_palette_undo(self):
        if not self.undo_stack:
            return

        # Push palette state to redo stack
        self.redo_stack.append([QColor(c) for c in self.palette_colors])

        # Restore previous state and validate selection
        self.palette_colors = self.undo_stack.pop()
        self.validate_selection()

        # Refresh palette
        self.rebuild_grid()
        self.refresh_selection_ui()
        self.update_undo_redo()
        self.unsaved_changes = True

    def edit_palette_redo(self):
        if not self.redo_stack:
            return

        # Push palette state to undo stack
        self.undo_stack.append([QColor(c) for c in self.palette_colors])

        # Restore next state and validate selection
        self.palette_colors = self.redo_stack.pop()
        self.validate_selection()

        self.rebuild_grid()
        self.refresh_selection_ui()
        self.update_undo_redo()
        self.unsaved_changes = True

    def edit_palette_resize(self):
        current_size = len(self.palette_colors)
        new_size, ok = QtW.QInputDialog.getInt(
            self, "Resize Palette", "Number of colors:", current_size, 1, PALEDIT_MAXCOLORS, 1
        )

        # Exit if the user cancels or doesn't change the size
        if not ok or new_size == current_size:
            return

        self.push_undo_state()  # Record state before resizing palette

        # Extending palette size
        if new_size > current_size:
            # Append black colors
            self.palette_colors.extend(QColor(0, 0, 0) for _ in range(new_size - current_size))

            # Rebuild starting from the first newly added index
            self.rebuild_grid(current_size)

        # Retracting palette size
        else:
            self.palette_colors = self.palette_colors[:new_size]
            self.validate_selection()
            self.rebuild_grid(new_size)
            self.refresh_selection_ui()

        self.unsaved_changes = True

    def edit_palette_shift(self, direction):
        # Do nothing if multiple colors aren't selected
        if len(self.selected_indices) <= 1:
            return

        self.push_undo_state()  # Record state before shifting palette

        # Sort indices to maintain sequential order
        sorted_indices = sorted(self.selected_indices)
        colors = [self.palette_colors[i] for i in sorted_indices]

        # Perform rotating shift
        if direction == "left":
            rotated = colors[1:] + colors[:1]
        elif direction == "right":
            rotated = colors[-1:] + colors[:-1]
        else:
            return

        # Update palette array and visual box widgets
        for idx, color in zip(sorted_indices, rotated):
            self.palette_colors[idx] = color
            self.boxes[idx].set_color(color)

        self.refresh_selection_ui()
        self.unsaved_changes = True

    # Tied to ColorBox resizing
    def eventFilter(self, a0, event):
        if (
            a0 is self.palette_scroll.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self.palette_resize_timer.start(0)

        return super().eventFilter(a0, event)

    def resize_palette_boxes(self):
        if not self.boxes:
            return

        columns = PALLINE_COLORS
        margins = self.grid_layout.contentsMargins()
        spacing = self.grid_layout.horizontalSpacing()

        # Subtract the grid margins and gaps between columns
        available_width = (
            self.palette_scroll.viewport().width()
            - margins.left()
            - margins.right()
            - spacing * (columns - 1)
        )

        box_size = max(32, available_width // columns)
        target_size = QSize(box_size, box_size)

        for box in self.boxes:
            if box.minimumSize() != target_size:
                box.setFixedSize(target_size)

    def open_color_library(self):
        # Get active color from the main editor
        active_color = self.palette_colors[self.active_index]

        # Unlike the other mini-windows, this one runs modally
        dialog = ColorLibraryDialog(active_color, self)
        if dialog.exec():
            self.push_undo_state()  # Record state before applying chosen color

            # Apply picked color to active index
            new_color = dialog.get_color()
            self.apply_color_change(new_color)
            self.refresh_selection_ui()
            self.unsaved_changes = True

    def batch_target_scope(self):
        if self.opt_mass_all.isChecked():
            return range(len(self.palette_colors))
        return tuple(self.selected_indices)

    def batch_apply_edit(self, edit_color):
        target_indices = self.batch_target_scope()

        if not target_indices:
            return

        changes = []    # Buffer palette

        for _i in target_indices:
            original_color = self.palette_colors[_i]
            new_color = QColor(original_color)

            # Call invert, clear, or +/- adjust here
            edit_color(new_color)

            if new_color != original_color:
                changes.append((_i, new_color))

        # Stop if nothing changed
        if not changes:
            return

        self.push_undo_state()  # Record state before applying changes

        # Modify only what's actually changed
        for idx, new_color in changes:
            self.palette_colors[idx] = new_color
            self.boxes[idx].set_color(new_color)

        self.refresh_selection_ui()
        self.unsaved_changes = True

    def batch_invert_color(self, channel=None):
        def invert_color(color):
            # Reverse selected color channels (None = all)
            if channel in (None, 'r'):
                step = snap_to_md_colors(color.red())
                color.setRed(MDCOLOR_VALUES[7 - step])

            if channel in (None, 'g'):
                step = snap_to_md_colors(color.green())
                color.setGreen(MDCOLOR_VALUES[7 - step])

            if channel in (None, 'b'):
                step = snap_to_md_colors(color.blue())
                color.setBlue(MDCOLOR_VALUES[7 - step])

        # Run the above function for the whole batch (Remembering channel)
        self.batch_apply_edit(invert_color)

    def batch_clear_color(self, channel=None):
        def clear_color(color):
            # Clear selected color channels (None = all)
            if channel in (None, 'r'):
                color.setRed(0)

            if channel in (None, 'g'):
                color.setGreen(0)

            if channel in (None, 'b'):
                color.setBlue(0)

        # Run the above function for the whole batch (Remembering channel)
        self.batch_apply_edit(clear_color)

    def batch_shift_color(self, direction, channel=None):
        def shift_color(color):
            if channel in (None, "r"):
                _r = snap_to_md_colors(color.red())
                _r = max(0, min(7, _r + direction))
                color.setRed(MDCOLOR_VALUES[_r])

            if channel in (None, "g"):
                _g = snap_to_md_colors(color.green())
                _g = max(0, min(7, _g + direction))
                color.setGreen(MDCOLOR_VALUES[_g])

            if channel in (None, "b"):
                _b = snap_to_md_colors(color.blue())
                _b = max(0, min(7, _b + direction))
                color.setBlue(MDCOLOR_VALUES[_b])

        # Run the above function for the whole batch (Remembering channel and direction)
        self.batch_apply_edit(shift_color)

    def check_active_dialog(self):
        # If an advanced dialog is open, bring it to focus
        if self.active_advanced_dialog is not None and self.active_advanced_dialog.isVisible():
            self.active_advanced_dialog.raise_()
            self.active_advanced_dialog.activateWindow()
            return True
        return False

    def open_advanced_dialog(self, dialog_class, signal_name=None, callback=None):
        # Focus the existing dialog instead of opening another (to prevent duplication)
        if self.check_active_dialog():
            return

        # Opens new window
        dialog = dialog_class(self)

        # Set up callback command (Applies to all but adv_extract_palette)
        if signal_name is not None:
            getattr(dialog, signal_name).connect(callback)

        # Keep a reference for the duplication check at the start
        self.active_advanced_dialog = dialog
        dialog.show()

    def adv_blend_colors(self):
        self.open_advanced_dialog(ColorBlendDialog,"colors_applied", self.apply_color_effect)

    def adv_greyscale_colors(self):
        self.open_advanced_dialog(GreyscaleDialog, "colors_applied", self.apply_color_effect)

    def adv_build_gradient(self):
        self.open_advanced_dialog(GradientBuilderDialog, "gradient_applied", self.apply_gradient)

    def adv_extract_palette(self):
        self.open_advanced_dialog(PaletteExtractDialog)

    def apply_color_effect(self, new_colors):
        # Effect is only applied if the user selects "Apply"
        self.push_undo_state()  # Record state before applying chosen color
        self.palette_colors = new_colors
        self.rebuild_grid()
        self.refresh_selection_ui()
        self.unsaved_changes = True

    def apply_gradient(self, gradient_colors):
        # Effect is only applied if the user selects "Apply"
        self.push_undo_state()  # Record state before applying gradient
        start = self.active_index

        # Inject gradient colors, expanding palette up to the limit if necessary
        for i, color in enumerate(gradient_colors):
            idx = start + i
            if idx < len(self.palette_colors):
                self.palette_colors[idx] = color
            elif idx < PALEDIT_MAXCOLORS:
                self.palette_colors.append(color)
            else:
                break

        self.rebuild_grid(start)

        # Mass select the newly placed gradient colors to visually confirm placement
        end = min(start + len(gradient_colors), len(self.palette_colors))
        self.selected_indices = list(range(start, end))
        self.active_index = start

        self.refresh_selection_ui()
        self.unsaved_changes = True

    def write_palette_to_disk(self, path: Path):
        binary_data = bytearray()
        for color in self.palette_colors:
            _r = snap_to_md_colors(color.red())
            _g = snap_to_md_colors(color.green())
            _b = snap_to_md_colors(color.blue())

            # store in 0BGR format
            binary_data.append((_b << 1) & 0xFF)
            val = (_g << 5) | (_r << 1)
            binary_data.append(val & 0xFF)

        try:
            with open(path, "wb") as f:
                f.write(binary_data)

            # Successful Save
            self.unsaved_changes = False
            return True

        # Failed Save
        except Exception as e:
            QtW.QMessageBox.critical(self, "Save Error", f"Failed to save palette:\n{str(e)}")
            return False

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

    def populate_palette_list(self, palette_paths):
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

    def on_pal_dropdown_changed(self, index):
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

    def load_palette_data(self, path):
        self.active_palette_path = path
        if not path.exists():
            return

        loaded_colors = []

        # Raw Binary Palette file (2-byte word per color: 0000 BBB0 GGG0 RRR0)
        try:
            with open(path, "rb") as f:
                data = f.read(512)  # Read up to 256 colors (512 bytes)
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

        except Exception as e:
            print(f"Error loading palette {path.name}: {e}")

        if loaded_colors:
            self.set_palette_data(loaded_colors)
            self.unsaved_changes = False  # clear flag on load

    def rebuild_grid(self, index=0):
        # Use index to tell Triad how much to rebuild (avoid unnecessary work)
        index = max(0, min(index, len(self.boxes)))

        # Clear color boxes, starting with [index]
        for box in self.boxes[index:]:
            box.deleteLater()

        # Remove deleted references
        self.boxes = self.boxes[:index]

        # Build grid (only the missing portion)
        for idx in range(index, len(self.palette_colors)):
            color = self.palette_colors[idx]
            row, col = idx // PALLINE_COLORS, idx % PALLINE_COLORS

            box = cb.ColorBox(idx, color)
            box.editor = self
            self.grid_layout.addWidget(box, row, col)
            self.boxes.append(box)

        # Emit signal so open dialogs know palette size changed
        self.palette_resize_timer.start(0)
        self.palette_changed.emit()

    def set_palette_data(self, colors):
        # Constrain to range [1, 256]; To-Do: Make the first line optional if palette_colors is already defined
        self.palette_colors = colors[:PALEDIT_MAXCOLORS] if colors else [QColor(0, 0, 0)]
        self.rebuild_grid()
        self.selected_indices = [0]
        self.active_index = 0
        self.refresh_selection_ui()
        self.clear_history()

    def select_colors(self, index, modifiers):
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
        self.push_undo_state()  # Record state before removing color(s)

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

        # Prevent out-of-bounds crashes by clamping to the new palette length
        safe_index = min(rebuild_start, len(self.palette_colors) - 1)

        # Adjust selection index
        self.selected_indices = [safe_index]
        self.active_index = safe_index
        self.refresh_selection_ui()

        self.unsaved_changes = True

    def swap_colors(self, src_indices, target_start):
        if not src_indices:
            return

        self.push_undo_state()  # Record state before swapping

        # Prevent swapping out of bounds
        count = len(src_indices)
        if target_start + count > len(self.palette_colors):
            target_start = len(self.palette_colors) - count

        # Single-item swap shortcut
        if count == 1:
            src_idx = src_indices[0]
            dst_idx = target_start
            self.palette_colors[src_idx], self.palette_colors[dst_idx] = (
                self.palette_colors[dst_idx],
                self.palette_colors[src_idx],
            )
            self.boxes[src_idx].set_color(self.palette_colors[src_idx])
            self.boxes[dst_idx].set_color(self.palette_colors[dst_idx])
            self.active_index = dst_idx
            self.selected_indices = [dst_idx]
        else:
            # Multi-item contiguous swap
            dst_indices = list(range(target_start, target_start + count))

            # Extract source and target color blocks
            src_colors = [QColor(self.palette_colors[_i]) for _i in src_indices]
            dst_colors = [QColor(self.palette_colors[_i]) for _i in dst_indices]

            # Exchange block colors
            for _i, idx in enumerate(src_indices):
                self.palette_colors[idx] = dst_colors[_i]
                self.boxes[idx].set_color(dst_colors[_i])

            for _i, idx in enumerate(dst_indices):
                self.palette_colors[idx] = src_colors[_i]
                self.boxes[idx].set_color(src_colors[_i])

            # Set highlighted selection to the destination
            self.active_index = target_start
            self.selected_indices = dst_indices

        self.refresh_selection_ui()
        self.unsaved_changes = True

        # Emit signal for open dialogs (Resizing shouldn't occur here though)
        self.palette_changed.emit()

    def refresh_selection_ui(self):
        # Update active selection highlighting for all boxes
        for idx, box in enumerate(self.boxes):
            box.set_selected(idx in self.selected_indices)

        # Dynamic elements based on color selection count
        count = len(self.selected_indices)
        # Shifting requires at least two selected colors
        self.btn_shift_L.setEnabled(count > 1)
        self.btn_shift_R.setEnabled(count > 1)
        # Set selected color text
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
        _r = snap_to_md_colors(active_color.red())
        _g = snap_to_md_colors(active_color.green())
        _b = snap_to_md_colors(active_color.blue())

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

    def copy_colors(self, cut=False):
        if not self.selected_indices:
            return

        # Sort colors to keep them in visual order when pasting
        sorted_indices = sorted(self.selected_indices)
        self.clipboard_colors = [QColor(self.palette_colors[idx]) for idx in sorted_indices]
        self.refresh_clipboard()

        # If only Copying, stop here. Otherwise, remove copied colors
        if cut:
            # Delete in reverse order to avoid issues with index shifting
            sorted_indices.reverse()
            # Unsaved flag and undo state recording handled here
            self.remove_colors(sorted_indices)

    def paste_colors(self, mode, target_index):
        if not self.clipboard_colors:
            return

        clipboard_length = len(self.clipboard_colors)

        # Determine where to paste and how many colors will fit.
        if mode == "over":
            # Capacity depends on the starting index because slots get overwritten
            start = target_index
            available = max(0, PALEDIT_MAXCOLORS - start)
        else:
            # Capacity depends on the current palette length because pasted colors adds new slots
            start = target_index if mode == "before" else target_index + 1
            available = max(0, PALEDIT_MAXCOLORS - len(self.palette_colors))

        # Final number of colors to paste
        pasted_count = min(clipboard_length, available)

        # If nothing changes, don't record state or change selection
        if pasted_count == 0:
            return

        elif pasted_count < clipboard_length:
            QtW.QMessageBox.warning(
                self,"Palette Size Restriction",
                f"Only {pasted_count} of {clipboard_length} clipboard "
                "colors can be pasted without exceeding the color limit."
            )

        self.push_undo_state()  # Record state before pasting colors

        # Isolate actual colors that will be pasted (if not all)
        colors_to_paste = self.clipboard_colors[:pasted_count]

        # Overwrite existing slots, extending the palette if needed
        if mode == "over":
            for _i, color in enumerate(colors_to_paste):
                idx = start + _i

                if idx < len(self.palette_colors):
                    self.palette_colors[idx] = QColor(color)
                else:
                    self.palette_colors.append(QColor(color))

        # Paste before or after the current index, shifting colors accordingly
        else:
            for _i, color in enumerate(colors_to_paste):
                self.palette_colors.insert(start + _i, QColor(color))

        # Select pasted colors
        end = start + pasted_count
        self.active_index = start
        self.selected_indices = list(range(start, end))

        # Refresh palette
        self.rebuild_grid(start)
        self.refresh_selection_ui()
        self.unsaved_changes = True

    def clear_clipboard(self):
        self.clipboard_colors.clear()
        self.refresh_clipboard()

    def refresh_clipboard(self):
        # Update clipboard header
        count = len(self.clipboard_colors)
        color_text = "color" if count == 1 else "colors"

        self.btn_toggle_clipboard.setText(f"Clipboard: {count} {color_text}")
        self.btn_clear_clipboard.setEnabled(count > 0)

        # Clear clipboard boxes
        for box in self.clipboard_boxes:
            box.deleteLater()
        self.clipboard_boxes.clear()

        if self.clipboard_empty_label:
            self.clipboard_empty_label.deleteLater()
            self.clipboard_empty_label = None

        # Display placeholder text when empty
        if not self.clipboard_colors:
            self.clipboard_empty_label = QtW.QLabel("Clipboard is empty (Right-click grid colors to Copy or Cut)")
            self.clipboard_empty_label.setStyleSheet("color: #777777; font-style: italic;")
            self.clipboard_grid_layout.addWidget(self.clipboard_empty_label, 0, 0)
            return

        # Render copied swatches
        MAX_COLUMNS = 16
        for idx, color in enumerate(self.clipboard_colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS

            box = QtW.QFrame()
            box.setFixedSize(28, 28)
            box.setToolTip(f"Clipboard #{idx}: {color.name().upper()}")
            box.setStyleSheet(f"""
                QFrame {{
                    background-color: {color.name()};
                    border: 1px solid #555555;
                }}
            """)
            self.clipboard_grid_layout.addWidget(box, row, col)
            self.clipboard_boxes.append(box)

    def toggle_clipboard(self, expanded):
        # Collapse handler
        if expanded:
            # Allow the clipboard panel to grow again
            self.clipboard_group.setMinimumHeight(0)
            self.clipboard_group.setMaximumHeight(16777215)
            self.clipboard_scroll.show()
            self.clipboard_group.layout().activate()

            self.btn_toggle_clipboard.setArrowType(Qt.ArrowType.DownArrow)

            # Restore the divider position from before collapsing
            if self.clipboard_splitter_sizes is not None:
                self.palette_splitter.setSizes(self.clipboard_splitter_sizes)

        else:
            # Remember the user's divider position
            self.clipboard_splitter_sizes = self.palette_splitter.sizes()

            self.clipboard_scroll.hide()
            self.btn_toggle_clipboard.setArrowType(Qt.ArrowType.RightArrow)

            # Shrink the panel to its header
            self.clipboard_group.layout().activate()
            self.clipboard_group.setFixedHeight(self.clipboard_group.sizeHint().height())

    def on_slider_changed(self):
        # Undo/Redo NOT called here. It's called in create_step_slider() instead

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
            self.push_undo_state()      # Record state before editing

            _r = snap_to_md_colors(color.red())
            _g = snap_to_md_colors(color.green())
            _b = snap_to_md_colors(color.blue())

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

    def push_undo_state(self):
        # Snapshot current palette colors
        state = [QColor(c) for c in self.palette_colors]
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        # Clear redo stack when we have something new to undo
        self.redo_stack.clear()
        self.update_undo_redo()

    def update_undo_redo(self):
        self.btn_undo.setEnabled(bool(self.undo_stack))
        self.btn_redo.setEnabled(bool(self.redo_stack))

    def clear_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_redo()

    @property
    def unsaved_changes(self):
        return self._unsaved_changes

    @unsaved_changes.setter
    def unsaved_changes(self, value=True):
        self._unsaved_changes = value
        self.unsaved_label.setVisible(value)

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
            if self.file_palette_save():
                pending_action_callback()
            else:
                cancel_callback()
        elif user_choice == "Save As":
            if self.file_palette_save_as():
                pending_action_callback()
            else:
                cancel_callback()
        elif user_choice == "Don't Save":
            pending_action_callback()
        elif user_choice == "Cancel":
            # Revert UI state if needed
            if cancel_callback:
                cancel_callback()
            return

    def create_step_slider(self, callback):
        slider = QtW.QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 7)
        slider.setSingleStep(1)
        slider.setPageStep(1)
        slider.setTickPosition(QtW.QSlider.TickPosition.TicksBelow)
        slider.setTickInterval(1)

        # Occurs as soon as user begins dragging slider
        slider.sliderPressed.connect(self.push_undo_state)  # Record state here
        slider.valueChanged.connect(callback)               # Callback upon slider change
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
