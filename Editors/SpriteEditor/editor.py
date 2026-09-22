import json
from pathlib import Path

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, QEvent, QPoint, QRect
from PyQt6.QtGui import QColor, QImage, QPixmap, QPainter

from UI.widgets import (
    create_combobox,
    create_pushbutton,
    create_scrollarea,
    create_splitter,
    create_spinbox,
    create_toolbutton
)

from Constants import *
from PaletteEditor.editor import snap_to_md_colors, ColorLibraryDialog
from PaletteEditor.color_box import MiniColorBox
from SpriteEditor.map_loading import load_mappings
from SpriteEditor.map_saving import save_mappings

from Formats import compress, decompress


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

        # Widget group used in the map file manager
        self.map_widget = None
        self.map_path_input = None
        self.map_dropdown = None
        self.map_name_input = None
        self.macro_cb = None

        self.map_frames = []    # Stores the parsed mapping data in memory
        # Not loading DPLCs right now

        # Frame labels (I'll work this into map_frames later)
        self.frame_labels = []

        self.active_sprite_build = None
        self.project_sprite_builds = {}

        self._current_dropdown_index = -1

        # Sprite canvas dimensions
        self.sprite_canvas_width = 256
        self.sprite_canvas_height = 256
        self.sprite_zoom = 2

        # Piece selection and dragging
        self.hovered_piece = None   # Hovered pieces will have transparency if not selected
        self.selected_pieces = set()
        self.piece_drag = None      # Remember where the mouse and piece were when dragging began
        self.selection_drag = None

        self.ui_init()


    # --------------------------------------------------
    # UI Setup
    # --------------------------------------------------
    def ui_init(self):
        main_layout = QtW.QVBoxLayout(self)
        main_layout.addLayout(self.ui_build_file_toolbar())

        sprite_panel = self.ui_build_sprite_panel()
        editing_panel = self.ui_build_editing_panel()

        self.content_splitter = create_splitter(
            (sprite_panel, editing_panel),
            orientation=Qt.Orientation.Horizontal,
            stretch_factors=(2, 1), sizes=(664, 336))
        main_layout.addWidget(self.content_splitter, stretch=1)

        self.btn_toggle_filemanager.setChecked(False)

    def ui_build_file_toolbar(self):
        file_toolbar = QtW.QHBoxLayout()
        file_toolbar.setSpacing(4)
        file_toolbar.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Sprite Build Dropdown
        self.spr_dropdown = create_combobox(
            tooltip="Select a sprite build from the active project",
            on_index_changed=self.on_sprite_dropdown_changed, layout=file_toolbar)

        # File Buttons
        create_pushbutton("New", tooltip="Create a new sprite build",
            on_clicked=self.file_sprite_new, layout=file_toolbar)
        create_pushbutton("Load", tooltip="Load an existing sprite build",
            on_clicked=self.file_sprite_load, layout=file_toolbar)
        create_pushbutton("Save", tooltip="Save the current sprite build",
            on_clicked=self.file_sprite_save, layout=file_toolbar)
        create_pushbutton("Remove", tooltip="Remove the current sprite build from the project",
            on_clicked=self.file_sprite_remove, layout=file_toolbar)
        create_pushbutton("Clear Data", tooltip="Clear the current sprite data",
            on_clicked=self.file_sprite_clear, layout=file_toolbar)

        file_toolbar.addStretch()
        return file_toolbar

    def ui_build_sprite_panel(self):
        sprite_panel = QtW.QWidget()
        sprite_layout = QtW.QVBoxLayout(sprite_panel)
        sprite_layout.setContentsMargins(0, 0, 0, 0)

        sprite_layout.addWidget(self.ui_build_sprite_viewer(), stretch=2)
        sprite_layout.addWidget(self.ui_build_file_manager(), stretch=1)
        return sprite_panel

    def ui_build_sprite_viewer(self):
        # Sprite Viewer
        sprite_box = QtW.QGroupBox("Sprite Viewer")
        sprite_viewer = QtW.QVBoxLayout(sprite_box)

        # Selection controls
        frame_controls = QtW.QHBoxLayout()

        # The following items emulate an in-game object's art_tile OST
        # VRAM Address Selector
        frame_controls.addWidget(QtW.QLabel("VRAM Address:"))
        self.vram_spinbox = create_spinbox(minimum=0, maximum=2047,
            display_base=16, prefix="$", width=50, tooltip="Starting VRAM Tile Index (Hex)",
            on_value_changed=self.render_sprite_frame, layout=frame_controls)

        # VRAM Base Palette Selector
        frame_controls.addWidget(QtW.QLabel("Palette:"))
        self.sprpal_spinbox = create_spinbox(minimum=0, maximum=3,
            width=40, tooltip="Base Palette Line",
            on_value_changed=self.render_sprite_frame, layout=frame_controls)

        # VRAM Base Priority Checkbox (Consider adding later with additions)

        # Frame Selector
        frame_controls.addWidget(QtW.QLabel("Frame Index:"))
        self.frame_spinbox = create_spinbox(minimum=0, maximum=0,
            on_value_changed=self.on_sprite_frame_changed, layout=frame_controls)

        frame_controls.addStretch()
        sprite_viewer.addLayout(frame_controls)

        # Scrollable Sprite Viewer
        self.sprite_label = QtW.QLabel()
        self.sprite_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.sprite_label.setMargin(0)
        self.sprite_label.setFrameShape(QtW.QFrame.Shape.NoFrame)
        self.sprite_label.setFixedSize(
            self.sprite_canvas_width * self.sprite_zoom,
            self.sprite_canvas_height * self.sprite_zoom)
        self.sprite_label.setMouseTracking(True)
        self.sprite_label.installEventFilter(self)      # install for click and drag mechanics

        # Selection rectangle, positioned manually over the sprite canvas
        # (To-Do: Color based on theme, or by preference)
        self.selection_box = QtW.QFrame(self.sprite_label)
        self.selection_box.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.selection_box.setStyleSheet("""
            QFrame {
                background-color: rgba(100, 180, 255, 45);
                border: 1px solid rgba(100, 180, 255, 220);
            }
        """)
        self.selection_box.hide()

        scroll_area = create_scrollarea(
            self.sprite_label, resizable=False, layout=sprite_viewer)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        return sprite_box

    def ui_build_file_manager(self):
        # Sprite File Manager
        self.spr_file_group = QtW.QGroupBox()
        spr_file_layout = QtW.QVBoxLayout(self.spr_file_group)

        file_header_layout = QtW.QHBoxLayout()

        self.btn_toggle_filemanager = create_toolbutton("Sprite Data and Files",
            arrow_type=Qt.ArrowType.DownArrow,
            tool_button_style=Qt.ToolButtonStyle.ToolButtonTextBesideIcon,
            checkable=True, checked=True, tooltip="Expand or collapse the file manager",
            on_toggled=self.filemanager_toggle, layout=file_header_layout)

        file_header_layout.addStretch()
        spr_file_layout.addLayout(file_header_layout)

        # File-related elements here
        self.filemanager_tabs = QtW.QTabWidget()
        self.filemanager_tabs.addTab(self.ui_build_art_tab(), "Art")
        self.filemanager_tabs.addTab(self.ui_build_mappings_tab(), "Mappings")
        self.filemanager_tabs.addTab(self.ui_build_palettes_tab(), "Palettes")
        spr_file_layout.addWidget(self.filemanager_tabs)

        return self.spr_file_group

    def ui_build_art_tab(self):
        art_tab = QtW.QWidget()
        art_layout = QtW.QHBoxLayout(art_tab)

        # File buttons
        art_btn_layout = QtW.QVBoxLayout()
        art_btn_layout.setSpacing(12)
        art_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_art_add = create_pushbutton("Add", tooltip="Add art tiles",
            width=60, on_clicked=self.art_entry_new, layout=art_btn_layout)
        self.btn_art_load = create_pushbutton("Load", tooltip="Load added art tiles",
            width=60, on_clicked=self.art_entry_load, enabled=False, layout=art_btn_layout)
        self.btn_art_save = create_pushbutton("Save", tooltip="Save art tile data",
            width=60, on_clicked=self.art_entry_save, enabled=False, layout=art_btn_layout)

        # Load/Save are disabled by default until palettes are added
        self.btn_art_load.setEnabled(False)
        self.btn_art_save.setEnabled(False)

        art_layout.addLayout(art_btn_layout)

        # Art entry container
        self.art_entries_widget = QtW.QWidget()
        self.art_entries_layout = QtW.QVBoxLayout(self.art_entries_widget)
        self.art_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        art_entries_scroll = create_scrollarea(self.art_entries_widget)
        art_layout.addWidget(art_entries_scroll, stretch=1)

        return art_tab

    def ui_build_mappings_tab(self):
        mappings_tab = QtW.QWidget()
        mappings_layout = QtW.QHBoxLayout(mappings_tab)

        # File buttons
        map_btn_layout = QtW.QVBoxLayout()
        map_btn_layout.setSpacing(12)
        map_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_map_add = create_pushbutton("Add", tooltip="Add sprite mappings",
            width=60, on_clicked=self.mapping_entry_new, layout=map_btn_layout)
        self.btn_map_load = create_pushbutton("Load", tooltip="Load added mappings",
            width=60, on_clicked=self.mapping_entry_load, enabled=False, layout=map_btn_layout)
        self.btn_map_save = create_pushbutton("Save", tooltip="Save mappings data",
            width=60, on_clicked=self.mapping_entry_save, enabled=False, layout=map_btn_layout)

        mappings_layout.addLayout(map_btn_layout)

        # Mapping/DPLC entry container (No vertical scrollbar)
        self.map_entries_widget = QtW.QWidget()
        self.map_entries_layout = QtW.QVBoxLayout(self.map_entries_widget)
        self.map_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        map_entries_scroll = create_scrollarea(
            self.map_entries_widget,
            vertical_policy=Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        mappings_layout.addWidget(map_entries_scroll, stretch=1)

        return mappings_tab

    def ui_build_palettes_tab(self):
        palettes_tab = QtW.QWidget()
        palettes_layout = QtW.QHBoxLayout(palettes_tab)

        # File buttons
        pal_btn_layout = QtW.QVBoxLayout()
        pal_btn_layout.setSpacing(12)
        pal_btn_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_pal_add = create_pushbutton("Add", tooltip="Add color palettes",
            width=60, on_clicked=self.palette_entry_new, layout=pal_btn_layout)
        self.btn_pal_load = create_pushbutton("Load", tooltip="Load added palettes",
            width=60, on_clicked=self.palette_entry_load, enabled=False, layout=pal_btn_layout)
        self.btn_pal_save = create_pushbutton("Save", tooltip="Save palette data",
            width=60, on_clicked=self.palette_entry_save, enabled=False, layout=pal_btn_layout)

        palettes_layout.addLayout(pal_btn_layout)

        # Palette entry container
        self.pal_entries_widget = QtW.QWidget()
        self.pal_entries_layout = QtW.QVBoxLayout(self.pal_entries_widget)
        self.pal_entries_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        pal_entries_scroll = create_scrollarea(self.pal_entries_widget)
        palettes_layout.addWidget(pal_entries_scroll, stretch=1)

        return palettes_tab

    def ui_build_editing_panel(self):
        editing_panel = QtW.QWidget()
        editing_layout = QtW.QVBoxLayout(editing_panel)
        editing_layout.setContentsMargins(0, 0, 0, 0)

        editing_layout.addWidget(self.ui_build_palette_preview())
        editing_layout.addWidget(self.ui_build_art_viewer(), stretch=2)
        return editing_panel

    def ui_build_palette_preview(self):
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
            box.clicked.connect(lambda _idx = _i: self.palette_open_color_library(_idx))
            pal_grid_layout.addWidget(box, row, col)
            self.palette_boxes.append(box)

        spr_palette_layout.addWidget(pal_grid_container,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        spr_palette_layout.addStretch()

        return spr_palette_group

    def ui_build_art_viewer(self):
        self.vram_box = QtW.QGroupBox("Art Tile Viewer")
        art_viewer_layout = QtW.QVBoxLayout(self.vram_box)

        # Active Palette Line Selector for the Viewer
        viewer_controls = QtW.QHBoxLayout()
        viewer_controls.addWidget(QtW.QLabel("Preview Palette Line:"))

        items = ["Line 0", "Line 1", "Line 2", "Line 3"]
        self.viewer_line_combo = create_combobox(
            tooltip="Choose a palette line to view art tiles with",
            on_index_changed=self.render_art_tiles, items=items, layout=viewer_controls)
        viewer_controls.addStretch()
        art_viewer_layout.addLayout(viewer_controls)

        # Scrollable Canvas
        self.vram_label = QtW.QLabel()
        self.vram_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.vram_scroll = create_scrollarea(self.vram_label, layout=art_viewer_layout)
        self.vram_scroll.setAlignment(Qt.AlignmentFlag.AlignRight)

        return self.vram_box


    # --------------------------------------------------
    # File Operations
    # --------------------------------------------------
    def file_sprite_new(self):
        # Get top-level window to access project file
        main_win = self.window()

        # We are not actually going to create new files here.
        # Instead, we're just creating a new sprite build definition.
        # Verify a project is loaded (To-Do: Palette Editor SHOULD do this also)
        if not hasattr(main_win, "active_project_data") or main_win.active_project_data is None:
            QtW.QMessageBox.warning(self, "No Project", "Please load a project file first.")
            return

        # Prompt user for a new sprite build name (To-Do: Append a number to 'New Sprite' with repeated use)
        sprite_name, ok = QtW.QInputDialog.getText(
            self, "New Sprite Build", "Enter a name for the new sprite build:", text="New Sprite"
        )

        if not ok or not sprite_name.strip():
            return

        # Can this be done before the OK check?
        sprite_name = sprite_name.strip()

        # Ensure 'sprites' dictionary exists in project data
        sprites_dict = main_win.active_project_data.setdefault("sprites", {})

        # Prevent duplicate definitions
        if sprite_name in sprites_dict:
            QtW.QMessageBox.warning(self, "Duplicate Name", f"A sprite named '{sprite_name}' already exists.")
            return

        # Create an empty template for the sprite build
        sprites_dict[sprite_name] = {
            "format": 1,        # Sonic 1 by default
            "vram_index": 0,    # Global starting VRAM index
            "palettes": [],
            "art": [],
            "mappings": {},
            "dplcs": {}
        }

        # Persist project JSON changes back to disk
        project_json_path = getattr(main_win, "active_project_json_path", None)
        if project_json_path and Path(project_json_path).exists():
            try:
                with open(project_json_path, "w", encoding="utf-8") as f:
                    json.dump(main_win.active_project_data, f, indent=2)
            except Exception as e:
                QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

        # Add to the UI dropdown and make it the active selection
        self.spr_dropdown.addItem(sprite_name)
        self.spr_dropdown.setCurrentText(sprite_name)

        # Clear out everything

    def file_sprite_load(self):
        # Get top-level window to access project file
        main_win = self.window()

        # Verify a project is loaded (To-Do: Palette Editor SHOULD do this also)
        if not hasattr(main_win, "active_project_data") or main_win.active_project_data is None:
            return

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return

        # Ensure 'sprites' dictionary exists and contains our sprite
        sprites_dict = main_win.active_project_data.get("sprites", {})
        if sprite_name not in sprites_dict:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Get sprite data so we can load the global VRAM index
        sprite_data = sprites_dict[sprite_name]
        if not sprite_data:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Set global VRAM index and reset frame counter
        self.vram_spinbox.setValue(sprite_data.get("vram_index", 0))
        self.sprpal_spinbox.setValue(sprite_data.get("palette_line", 0))
        self.frame_spinbox.setValue(0)

        # File data is no longer filled out here (now done upon dropdown change)
        # Now the data is just loaded in when the button is pressed
        if self.pal_rows:
            self.palette_entry_load()

        if self.art_rows:
            self.art_entry_load()

        if self.map_widget:
            self.mapping_entry_load()

    def file_sprite_save(self):
        """Saves all loaded sprite assets and saves build to the project"""
        # Get top-level window to access project file
        main_win = self.window()

        # Verify a project is loaded (To-Do: Palette Editor SHOULD do this also)
        if not hasattr(main_win, "active_project_data") or main_win.active_project_data is None:
            QtW.QMessageBox.warning(self, "No Project", "Please load a project file first.")
            return

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return

        # Ensure 'sprites' dictionary exists and contains our sprite
        sprites_dict = main_win.active_project_data.get("sprites", {})
        if sprite_name not in sprites_dict:
            QtW.QMessageBox.warning(self, "Save Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        sprite_data = sprites_dict[sprite_name]
        if not sprite_data:
            QtW.QMessageBox.warning(self, "Save Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Save sprite assets
        self.palette_entry_save()
        self.art_entry_save()
        self.mapping_entry_save()

        # JSON SAVING
        project_dir = getattr(main_win, "project_root_dir", None)

        # Helper to attempt to save paths relative to the project directory
        def make_relative(path_str):
            if not path_str or not project_dir:
                return path_str
            try:
                # Returns relative path if it's within the project root
                return str(Path(path_str).relative_to(project_dir))
            except ValueError:
                # Fallback to absolute path if it resides outside the project root
                return str(path_str)

        # Store Sprite Build data (First, the sprite's art_tile OST value)
        sprite_data["vram_index"] = self.vram_spinbox.value()
        sprite_data["palette_line"] = self.sprpal_spinbox.value()

        # If a mapping file hasn't been added, this widget will not be present
        if self.map_dropdown is not None:
            sprite_data["format"] = self.map_dropdown.currentIndex() + 1
        else:
            sprite_data["format"] = sprite_data.get("format", 1)  # Default to S1

        # Save Palettes as they are stored in the File Manager
        if self.pal_rows:
            new_palettes = []
            for path_input, line_combo in self.pal_rows:
                p_text = path_input.text().strip()
                if p_text:
                    new_palettes.append({
                        "path": make_relative(p_text),
                        "length": int(line_combo.currentText() or "1")
                    })
            sprite_data["palettes"] = new_palettes

        # Save Art files as they are stored in the File Manager
        if self.art_rows:
            new_art = []
            for path_input, offset_spin, comp_combo, count_spin in self.art_rows:
                p_text = path_input.text().strip()
                if p_text:
                    new_art.append({
                        "path": make_relative(p_text),
                        "compression": comp_combo.currentText(),
                        "offset": offset_spin.value()
                    })
            sprite_data["art"] = new_art

        # Save Mappings & DPLCs (DPLCs not used yet)
        new_mappings = {}
        new_dplcs = {"enabled": False, "path": "", "label": ""}

        if self.map_widget:
            if self.map_path_input:
                new_mappings["path"] = make_relative(self.map_path_input.text().strip())

            # Access layout widgets to get map/DPLC info
            line_edits = self.map_widget.findChildren(QtW.QLineEdit)
            checkboxes = self.map_widget.findChildren(QtW.QCheckBox)

            for _l in line_edits:
                if _l.placeholderText() == "Map_":
                    new_mappings["label"] = _l.text().strip()
                elif _l.placeholderText() == "DPLC Filepath...":
                    new_dplcs["path"] = make_relative(_l.text().strip())
                elif _l.placeholderText() == "DPLC_":
                    new_dplcs["label"] = _l.text().strip()

            dplc_cb = next((cb for cb in checkboxes if cb.text() == "Enable DPLCs"), None)
            if dplc_cb:
                new_dplcs["enabled"] = dplc_cb.isChecked()

        sprite_data["mappings"] = new_mappings
        sprite_data["dplcs"] = new_dplcs

        # Save JSON changes
        project_json_path = getattr(main_win, "active_project_json_path", None)
        if project_json_path and Path(project_json_path).exists():
            try:
                with open(project_json_path, "w", encoding="utf-8") as f:
                    json.dump(main_win.active_project_data, f, indent=2)

                QtW.QMessageBox.information(
                    self, "Project Saved",
                    f"Sprite '{sprite_name}' configuration saved to project JSON."
                )
            except Exception as e:
                QtW.QMessageBox.warning(self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}")

    def file_sprite_remove(self):
        # Get the currently selected sprite name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return

        # Prompt user before clearing out File Manager widgets and data
        if QtW.QMessageBox.question(
            self,
            "Remove Sprite Build",
            f"Are you sure you want to remove '{sprite_name}' from the project?\n\n"
            "Note: The actual files will NOT be deleted from your disassembly.",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.No
        ) == QtW.QMessageBox.StandardButton.Yes:
            self.sprite_clear_data()
            self.filemanager_clear()

            main_win = self.window()
            project_dir = getattr(main_win, "project_root_dir", None)

            # Remove the palette from the JSON project file
            if hasattr(main_win, "active_project_data") and main_win.active_project_data is not None:
                sprites_dict = main_win.active_project_data.get("sprites", {})

                # Remove from JSON
                if sprite_name in sprites_dict:
                    del sprites_dict[sprite_name]

                    # Save JSON changes to disk
                    project_json_path = getattr(main_win, "active_project_json_path", None)
                    if project_json_path and Path(project_json_path).exists():
                        try:
                            with open(project_json_path, "w", encoding="utf-8") as f:
                                json.dump(main_win.active_project_data, f, indent=2)
                        except Exception as e:
                            QtW.QMessageBox.warning(
                                self, "Project Update Warning", f"Could not save project JSON:\n{str(e)}"
                            )

            # Remove dict entry and refresh dropdown
            if sprite_name in self.project_sprite_builds:
                del self.project_sprite_builds[sprite_name]

            self.active_sprite_build = None
            self.proj_populate_sprite_list(self.project_sprite_builds)

    def file_sprite_clear(self):
        # Clear out all sprite data
        self.sprite_clear_data()

        # Prompt user before clearing out File Manager widgets
        if QtW.QMessageBox.question(
            self,"Clear File Manager","Clear out File Manager entries as well?",
            QtW.QMessageBox.StandardButton.Yes | QtW.QMessageBox.StandardButton.No,
            QtW.QMessageBox.StandardButton.Yes
        ) == QtW.QMessageBox.StandardButton.Yes:
            self.filemanager_clear()


    # --------------------------------------------------
    # Project File Selection
    # --------------------------------------------------
    def proj_populate_sprite_list(self, sprite_builds):
        self.project_sprite_builds = sprite_builds

        self.spr_dropdown.blockSignals(True)
        self.spr_dropdown.clear()

        if not sprite_builds:
            self.spr_dropdown.addItem("No Sprites Found", userData=None)
            self.spr_dropdown.setEnabled(False)
            self.spr_dropdown.blockSignals(False)
            return

        self.spr_dropdown.setEnabled(True)
        for sprite_name, config in sprite_builds.items():
            # Display key name in dropdown
            self.spr_dropdown.addItem(sprite_name, userData=config)

        # Silently reset the selection
        self.spr_dropdown.setCurrentIndex(-1)
        self.spr_dropdown.blockSignals(False)

        # Only auto-load index 0 if we aren't currently targeting a specific sprite build
        if not self.active_sprite_build and self.spr_dropdown.count() > 0:
            self.spr_dropdown.setCurrentIndex(0)

    # File Toolbar Dropdown function
    def on_sprite_dropdown_changed(self):
        # Get top-level window to access project file
        main_win = self.window()

        # Verify a project is loaded (To-Do: Palette Editor SHOULD do this also)
        if not hasattr(main_win, "active_project_data") or main_win.active_project_data is None:
            return

        # Get the selected sprite build name
        sprite_name = self.spr_dropdown.currentText()
        if not sprite_name or sprite_name == "No Sprites Found":
            return

        # Ensure 'sprites' dictionary exists and contains our sprite
        sprites_dict = main_win.active_project_data.get("sprites", {})
        if sprite_name not in sprites_dict:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return

        # Get data for the newly selected sprite build
        sprite_data = sprites_dict[sprite_name]
        if not sprite_data:
            QtW.QMessageBox.warning(self, "Load Error", f"Sprite '{sprite_name}' not found in project data.")
            return
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Helper to convert relative paths/Path objects to full absolute path strings
        def resolve_path_str(raw_path):
            if not raw_path:
                return ""
            p_obj = Path(raw_path)
            if project_dir and not p_obj.is_absolute():
                return str((Path(start_dir) / p_obj).resolve())
            return str(p_obj)

        # Clean out File Manager ONLY (Leaves loaded data untouched)
        self.filemanager_clear()

        # Fill out palette data
        for pal in sprite_data.get("palettes", []):
            raw_path = pal.get("path", "") if isinstance(pal, dict) else pal
            self.palette_add_entry(resolve_path_str(raw_path))

            # New row at the end of the list
            path_input, line_combo = self.pal_rows[-1]
            line_combo.setCurrentText(str(pal.get("length", 1)))

        # Fill out art data
        for art in sprite_data.get("art", []):
            raw_path = art.get("path", "") if isinstance(art, dict) else art
            self.art_add_entry(resolve_path_str(raw_path))

            # New row at the end of the list
            path_input, offset_spin, comp_combo, count_spin = self.art_rows[-1]
            offset_spin.setValue(art.get("offset", 0))
            comp_combo.setCurrentText(art.get("compression", "Uncompressed"))
            count_spin.setValue(0)  # Load all tiles by default

        # Fill out mapping data
        mappings = sprite_data.get("mappings", {})
        dplcs = sprite_data.get("dplcs", {})

        map_path = mappings.get("path", "") if isinstance(mappings, dict) else mappings
        if map_path or mappings:
            self.mapping_add_entry(resolve_path_str(map_path))

            # Sync format dropdown based on integer (1=Sonic 1, 2=Sonic 2, 3=Sonic 3K)
            spr_format = sprite_data.get("format", 1)
            self.map_dropdown.setCurrentIndex(spr_format - 1)

            # Access layout widgets with findChildren to fill in information
            if self.map_widget:
                line_edits = self.map_widget.findChildren(QtW.QLineEdit)
                checkboxes = self.map_widget.findChildren(QtW.QCheckBox)

                for _l in line_edits:
                    if _l.placeholderText() == "Map_":
                        _l.setText(mappings.get("label", "") if isinstance(mappings, dict) else "")

                # Toggle and populate DPLCs if enabled
                dplc_cb = next((cb for cb in checkboxes if cb.text() == "Enable DPLCs"), None)
                if dplc_cb and isinstance(dplcs, dict) and dplcs.get("enabled", False):
                    dplc_cb.setChecked(True)  # Triggers the widget visibility toggle
                    for _l in line_edits:
                        if _l.placeholderText() == "DPLC Filepath...":
                            _l.setText(resolve_path_str(dplcs.get("path", "")))
                        elif _l.placeholderText() == "DPLC_":
                            _l.setText(dplcs.get("label", ""))


    # --------------------------------------------------
    # File Manager
    # --------------------------------------------------
    def filemanager_clear(self):
        """Remove file-manager entries without clearing loaded data or deleting files."""
        # Clean out Palette rows
        while self.pal_rows:
            path_input, line_combo = self.pal_rows[0]
            self.palette_remove_entry(path_input.parentWidget(), line_combo, path_input)

        # Clean out Art rows
        while self.art_rows:
            path_input, _, _, _ = self.art_rows[0]
            top_widget = path_input.parentWidget().parentWidget()
            self.art_remove_entry(top_widget, self.art_rows[0])

        # Clean out Mapping rows
        if self.map_widget:
            self.mapping_remove_entry()

    def filemanager_toggle(self, expanded):
        # Collapse handler
        if expanded:
            # Allow the file manager panel to grow again
            self.spr_file_group.setMinimumHeight(0)
            self.spr_file_group.setMaximumHeight(16777215)
            self.filemanager_tabs.show()
            self.spr_file_group.layout().activate()

            self.btn_toggle_filemanager.setArrowType(Qt.ArrowType.DownArrow)
            self.spr_file_group.layout().activate()

        else:
            self.filemanager_tabs.hide()
            self.btn_toggle_filemanager.setArrowType(Qt.ArrowType.RightArrow)

            # Shrink the panel to its header
            self.spr_file_group.layout().activate()
            self.spr_file_group.setFixedHeight(self.spr_file_group.sizeHint().height())


    # --------------------------------------------------
    # Sprite Functions
    # --------------------------------------------------
    def sprite_clear_data(self):
        """Clear loaded assets and reset previews, keeping file-manager entries."""
        # Clear sprite piece selection
        self.sprite_clear_selection()

        # Clear palette to black
        black = QColor(0, 0, 0)
        self.palette_colors = [black for _i in range(64)]
        for box in self.palette_boxes:
            box.set_color(black)

        # Flush out VRAM (art tiles)
        self.vram_tiles.clear()

        # Clear Sprite mappings
        self.map_frames.clear()
        self.frame_labels.clear()

        # Reset UI widgets in the Sprite Viewer
        self.vram_spinbox.setValue(0)
        self.sprpal_spinbox.setValue(0)
        self.frame_spinbox.setValue(0)
        self.frame_spinbox.setRange(0, 0)

        # Refresh (clear) tile and sprite views
        self.render_art_tiles()
        self.render_sprite_frame()

    def sprite_begin_box_select(self, position, additive):
        frame_index = self.frame_spinbox.value()
        if not 0 <= frame_index < len(self.map_frames):
            return

        self.hovered_piece = None

        self.selection_drag = {
            "frame": frame_index,
            "origin": position.toPoint(),
            "initial_selection": (self.selected_pieces.copy() if additive else set()),
            "started": False
        }

    def sprite_update_box_select(self, position):
        drag = self.selection_drag
        if drag is None:
            return

        frame_index = drag["frame"]

        if frame_index != self.frame_spinbox.value() or not 0 <= frame_index < len(self.map_frames):
            self.sprite_end_box_select()
            return

        point = position.toPoint()

        # Keep the rectangle within the sprite canvas
        point = QPoint(
            max(0, min(self.sprite_label.width() - 1, point.x())),
            max(0, min(self.sprite_label.height() - 1, point.y())),
        )

        if not drag["started"]:
            distance = (point - drag["origin"]).manhattanLength()

            if distance < QtW.QApplication.startDragDistance():
                return

            drag["started"] = True

        # Normalization allows dragging in any direction
        selection_rect = QRect(drag["origin"], point).normalized()

        self.selection_box.setGeometry(selection_rect)
        self.selection_box.show()
        self.selection_box.raise_()

        center_x = self.sprite_canvas_width // 2
        center_y = self.sprite_canvas_height // 2
        zoom = self.sprite_zoom

        intersecting = set()

        for index, piece in enumerate(self.map_frames[frame_index]):
            # Convert mapping bounds to displayed canvas coordinates
            piece_rect = QRect(
                (center_x + piece["x"]) * zoom,
                (center_y + piece["y"]) * zoom,
                piece["width"] * 8 * zoom,
                piece["height"] * 8 * zoom,
            )

            if selection_rect.intersects(piece_rect):
                intersecting.add(index)

        selection = drag["initial_selection"] | intersecting

        if selection != self.selected_pieces:
            self.selected_pieces = selection
            self.render_sprite_frame()

    def sprite_end_box_select(self):
        self.selection_drag = None
        self.selection_box.hide()

    def sprite_mouse_to_mapping(self, position):
        x = int(position.x() // self.sprite_zoom)
        x -= self.sprite_canvas_width // 2

        y = int(position.y() // self.sprite_zoom)
        y -= self.sprite_canvas_height // 2

        return x, y

    def sprite_piece_at(self, x, y):
        frame_index = self.frame_spinbox.value()
        if not 0 <= frame_index < len(self.map_frames):
            return None

        pieces = self.map_frames[frame_index]

        # Renderer draws later pieces overtop earlier pieces
        # Search backward to select the last-drawn matching piece
        for index in range(len(pieces) - 1, -1, -1):
            piece = pieces[index]

            left = piece["x"]
            top = piece["y"]
            width = piece["width"] * 8
            height = piece["height"] * 8

            if left <= x < left + width and top <= y < top + height:
                return index

        return None

    def sprite_clear_selection(self):
        self.selected_pieces.clear()
        self.piece_drag = None
        self.hovered_piece = None
        self.sprite_end_box_select()

    def on_sprite_frame_changed(self):
        self.sprite_clear_selection()
        self.render_sprite_frame()

    def sprite_update_hover(self, position=None, *, redraw=True):
        piece_index = None

        if position is not None:
            inside_canvas = (
                    0 <= position.x() < self.sprite_label.width()
                    and 0 <= position.y() < self.sprite_label.height()
            )

            if inside_canvas:
                x, y = self.sprite_mouse_to_mapping(position)
                piece_index = self.sprite_piece_at(x, y)

        if piece_index != self.hovered_piece:
            self.hovered_piece = piece_index

            if redraw:
                self.render_sprite_frame()

    def sprite_begin_drag(self, position, modifiers):
        x, y = self.sprite_mouse_to_mapping(position)
        piece_index = self.sprite_piece_at(x, y)
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        # Clear everything pertaining to click/drag
        self.piece_drag = None
        self.sprite_end_box_select()

        # Clicking empty space clears selection without Ctrl
        # Also starts a potential box-selection gesture
        if piece_index is None:
            if not ctrl:
                self.selected_pieces.clear()

            self.sprite_begin_box_select(position, additive=ctrl)
            self.render_sprite_frame()
            return

        # Multi-select pieces
        if ctrl:
            if piece_index in self.selected_pieces:
                # Ctrl-click removes this piece without starting a drag
                self.selected_pieces.remove(piece_index)
                self.render_sprite_frame()
                return

            self.selected_pieces.add(piece_index)

        elif piece_index not in self.selected_pieces:
            # Clicking a new piece replaces the selection
            self.selected_pieces = {piece_index}

        # Clicking an already-selected piece preserves the group
        frame_index = self.frame_spinbox.value()
        pieces = self.map_frames[frame_index]

        start_positions = {
            index: (pieces[index]["x"], pieces[index]["y"])
            for index in self.selected_pieces
        }

        # Contains the original position of every selected piece
        self.piece_drag = (frame_index, x, y, start_positions)

        self.render_sprite_frame()

    def sprite_drag_piece(self, position):
        if self.piece_drag is None:
            return

        frame_index, mouse_x, mouse_y, start_positions = self.piece_drag

        # Cancel if the current frame changed
        if (
            frame_index != self.frame_spinbox.value()
            or not 0 <= frame_index < len(self.map_frames)
        ):
            self.sprite_clear_selection()
            return

        pieces = self.map_frames[frame_index]

        # Cancel if the current frame's piece data has changed
        if not start_positions or any(
            not 0 <= index < len(pieces) for index in start_positions
        ):
            self.sprite_clear_selection()
            return

        x, y = self.sprite_mouse_to_mapping(position)
        dx = x - mouse_x
        dy = y - mouse_y

        # Find the movement range that keeps every selected piece's
        # position within our current -128..127 editing limits
        min_dx = max(-128 - start_x for start_x, _ in start_positions.values())
        max_dx = min(127 - start_x for start_x, _ in start_positions.values())
        min_dy = max(-128 - start_y for _, start_y in start_positions.values())
        max_dy = min(127 - start_y for _, start_y in start_positions.values())

        if dx:
            dx = max(min_dx, min(max_dx, dx)) if min_dx <= max_dx else 0
        if dy:
            dy = max(min_dy, min(max_dy, dy)) if min_dy <= max_dy else 0

        changed = False     # re-render flag

        for index, (start_x, start_y) in start_positions.items():
            piece = pieces[index]
            new_x = start_x + dx
            new_y = start_y + dy

            if (piece["x"], piece["y"]) != (new_x, new_y):
                piece["x"] = new_x
                piece["y"] = new_y
                changed = True

        if changed:
            self.render_sprite_frame()

    def eventFilter(self, a0, a1):
        if a0 is self.sprite_label:
            event_type = a1.type()

            if event_type in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick
            ):
                if a1.button() == Qt.MouseButton.LeftButton:
                    # sprite_begin_drag redraws after changing selection
                    self.sprite_update_hover(a1.position(), redraw=False)
                    self.sprite_begin_drag(a1.position(), a1.modifiers())
                    return True

            elif event_type == QEvent.Type.MouseMove:
                left_held = bool(
                    a1.buttons() & Qt.MouseButton.LeftButton)

                if left_held and self.selection_drag is not None:
                    self.sprite_update_box_select(a1.position())

                elif left_held and self.piece_drag is not None:
                    self.sprite_drag_piece(a1.position())

                else:
                    self.piece_drag = None
                    self.sprite_end_box_select()
                    self.sprite_update_hover(a1.position())

                return True

            elif event_type == QEvent.Type.MouseButtonRelease:
                if a1.button() == Qt.MouseButton.LeftButton:
                    if self.selection_drag is not None:
                        self.sprite_update_box_select(a1.position())
                        self.sprite_end_box_select()
                    else:
                        # Apply the final position before ending the drag
                        self.sprite_drag_piece(a1.position())

                    self.piece_drag = None
                    self.sprite_update_hover(a1.position())
                    return True

            elif event_type == QEvent.Type.Leave:
                # Clear hover, but let an active drag continue
                self.sprite_update_hover()

        return super().eventFilter(a0, a1)


    # --------------------------------------------------
    # Art File Entries
    # --------------------------------------------------
    def art_entry_new(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Filetype filter (To-Do: Move this to a global file and have each load instance pick and choose)
        art_file_filter = (
            "Uncompressed Art (*.bin *.unc);;"
            "Nemesis Art (*.nem *.unc);;"
            "Kosinski Art (*.kos *.unc);;"
            "Moduled Kosinski Art (*.kosm *.unc);;"
            "All Files (*)"
        )

        # Open dialog for new art file
        file_path, _ = QtW.QFileDialog.getOpenFileName(self, "New Art Tile File", start_dir, art_file_filter)

        # If successful, create a new row under the art tab
        if file_path:
            self.art_add_entry(file_path)

    def art_entry_load(self):
        """Loads art tile data from the filepath(s) specified into virtual VRAM storage"""
        # Flush out VRAM
        self.vram_tiles.clear()

        # Loop for each filepath added
        for path_input, offset_spin, comp_combo, count_spin in self.art_rows:
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

                compression = comp_combo.currentText()

                # Decompress (Need to add Kos+ and Comper)
                if compression != "Uncompressed":
                    if compression == "Nemesis":
                        raw_data = decompress.nemesis(raw_data)
                    elif compression == "Kosinski":
                        raw_data = decompress.kosinski(raw_data)
                    elif compression == "Kosinski-M":
                        raw_data = decompress.kosinski_mod(raw_data)
                    elif compression != "Uncompressed":
                        raise ValueError(f"Unsupported art compression format: {compression}")

                # Each 8x8 tile is 32 bytes (64 pixels at 4 bits per pixel)
                tile_count = len(raw_data) // 32
                user_count = count_spin.value()

                # Set load count (if 0, all tiles will be loaded)
                if user_count == 0:
                    tiles_to_load = tile_count
                    # Move this to after the loading. If we hit 2048, we must truncate this count
                    count_spin.blockSignals(True)
                    count_spin.setValue(tile_count)
                    count_spin.blockSignals(False)
                else:
                    tiles_to_load = min(user_count, tile_count)     # User-defined load count

                for _t in range(tiles_to_load):
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
        self.render_art_tiles()
        # Refresh frame window
        self.render_sprite_frame()

    def art_entry_save(self):
        for path_input, offset_spin, comp_combo, count_spin in self.art_rows:
            file_path_str = path_input.text().strip()
            if not file_path_str:
                continue

            user_count = count_spin.value()
            # If count is 0, don't save and check the next art file
            if user_count == 0:
                continue

            path = Path(file_path_str)
            current_tile_idx = offset_spin.value()
            max_limit = 2048

            art_data = bytearray()
            tile_idx = current_tile_idx
            tiles_saved = 0

            # Collect tiles for this entry, up to requested tile count
            while tile_idx < max_limit and tile_idx in self.vram_tiles and tiles_saved < user_count:
                pixels = self.vram_tiles[tile_idx]

                # Pack 64 pixel indices into 32 bytes
                for i in range(0, 64, 2):
                    left_pixel = pixels[i] & 0x0F
                    right_pixel = pixels[i + 1] & 0x0F
                    byte_val = (left_pixel << 4) | right_pixel
                    art_data.append(byte_val)

                # Increment tile
                tile_idx += 1
                tiles_saved += 1

            # If there is no art data to save, move on to the next file
            if not art_data:
                continue

            try:
                compression = comp_combo.currentText()

                # Compress (Need to add Kos formats and Comper)
                if compression != "Uncompressed":
                    if compression == "Nemesis":
                        art_data = bytes(compress.nemesis(art_data))
                    else:
                        raise ValueError(
                            f"Unsupported art compression format for saving: {compression}"
                        )

                # Create directory structure if saving to a new path
                path.parent.mkdir(parents=True, exist_ok=True)

                with open(path, "wb") as f:
                    f.write(art_data)

            except Exception as e:
                print(f"Error saving art tile file {path.name}: {e}")
                QtW.QMessageBox.warning(
                    self, "Art Save Error", f"Could not save art file {path.name}:\n{str(e)}"
                )

    def art_add_entry(self, file_path):
        # Cap sprite build at 3 art files
        if len(self.art_rows) >= 3:
            return

        artfile_widget = QtW.QWidget()

        # Appends a file row and edit row to the right-hand panel for art editing
        layout = QtW.QVBoxLayout(artfile_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Primary Art Row (Filepath and Compression)
        art_row_widget = QtW.QWidget()
        art_row = QtW.QHBoxLayout(art_row_widget)
        art_row.setContentsMargins(0, 0, 0, 0)

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # Compression Dropdown
        comp_combo = QtW.QComboBox()
        comp_combo.addItems(["Uncompressed", "Nemesis", "Kosinski", "Kosinski-M"])
        comp_combo.setToolTip("Compression Format")
        comp_combo.setFixedWidth(110)

        # Set compression dropdown based on file extension (if not .bin)
        if file_path.endswith(".unc"):
            comp_combo.setCurrentText("Uncompressed")
        if file_path.endswith(".nem"):
            comp_combo.setCurrentText("Nemesis")
        elif file_path.endswith(".kos"):
            comp_combo.setCurrentText("Kosinski")
        elif file_path.endswith(".kosm"):
            comp_combo.setCurrentText("Kosinski-M")

        art_row.addWidget(path_input, stretch=1)
        art_row.addWidget(comp_combo)

        # Secondary Art Row (Location, Tile Count, Remove Button)
        art_row2_widget = QtW.QWidget()
        art_row2 = QtW.QHBoxLayout(art_row2_widget)
        art_row2.setContentsMargins(0, 0, 0, 0)

        # VRAM Location Input (Hexadecimal)
        art_row2.addWidget(QtW.QLabel("VRAM Location:"))
        artloc_spin = QtW.QSpinBox()
        artloc_spin.setRange(0, 2047)  # Cap at 2048 tiles (I'll worry about specifics later)
        artloc_spin.setDisplayIntegerBase(16)  # Display in hex
        artloc_spin.setPrefix("$")
        artloc_spin.setToolTip("Starting VRAM Location (Hex)")
        artloc_spin.setFixedWidth(70)
        art_row2.addWidget(artloc_spin)

        # Art Tile Count Input (Decimal)
        art_row2.addWidget(QtW.QLabel("Tile Count:"))
        count_spin = QtW.QSpinBox()
        count_spin.setRange(0, 2047)  # Cap at 2048 tiles
        count_spin.setToolTip("Number of Tiles" +
                              "Load: Number to load (0 to load all).\n" +
                              "Save: Number to save.")
        count_spin.setFixedWidth(70)
        art_row2.addWidget(count_spin)

        # Store elements in the tracking array
        row_data = (path_input, artloc_spin, comp_combo, count_spin)
        self.art_rows.append(row_data)

        # Remove button
        btn_remove = QtW.QPushButton("Remove")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(
            lambda checked=False, _r=artfile_widget, _data=row_data: self.art_remove_entry(_r, _data)
        )
        # Spacer absorbs all extra space before the Remove button
        art_row2.addStretch()
        art_row2.addWidget(btn_remove)

        # Assembly
        layout.addWidget(art_row_widget)
        layout.addWidget(art_row2_widget)

        self.art_entries_layout.addWidget(artfile_widget)

        # Initial evaluation
        self.art_update_file_controls()

    def art_remove_entry(self, row_widget, row_data):
        # Removes an art widget row and re-evaluate capacity
        if row_data in self.art_rows:
            self.art_rows.remove(row_data)

        self.art_entries_layout.removeWidget(row_widget)
        row_widget.deleteLater()

        self.art_update_file_controls()

    def art_update_file_controls(self):
        # Disable Add button if we reach the 3-file limit
        is_full = (len(self.art_rows) >= 3)
        self.btn_art_add.setDisabled(is_full)

        # Load/Save are only enabled when art filepaths are present
        has_rows = len(self.art_rows) > 0
        self.btn_art_load.setEnabled(has_rows)
        self.btn_art_save.setEnabled(has_rows)


    # --------------------------------------------------
    # Mapping File Entries
    # --------------------------------------------------
    def mapping_entry_new(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new mapping file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "New Mapping File", start_dir, "Mapping Files (*.asm *.bin);;All Files (*)"
        )

        # If successful, create new widgets under the mappings tab
        if file_path:
            self.mapping_add_entry(file_path)

    def mapping_entry_load(self):
        if not self.map_path_input:
            return

        # If a filepath is empty, don't load
        file_path_str = self.map_path_input.text().strip()
        if not file_path_str:
            return

        # If the file doesn't exist, don't load
        path = Path(file_path_str)
        if not path.exists():
            QtW.QMessageBox.warning(self, "File Not Found", f"Cannot find mapping file:\n{path}")
            return

        # Clear selection and flush out frame data
        self.sprite_clear_selection()
        self.map_frames.clear()

        try:
            # Load sprite mappings based on selected version
            map_version = self.map_dropdown.currentIndex() + 1
            load_mappings(self, path, map_version)

            # Refresh frame window
            self.render_sprite_frame()

            QtW.QMessageBox.information(
                self, "Mappings Loaded",
                f"Successfully loaded {len(self.map_frames)} frames from {path.name}.\n\n(DPLCs unavailable.)"
            )

        except Exception as e:
            print(f"Error loading mappings {path.name}: {e}")
            QtW.QMessageBox.warning(
                self, "Mapping Load Error", f"Could not load mappings {path.name}:\n{str(e)}"
            )

    def mapping_entry_save(self):
        if not self.map_path_input or not self.map_path_input:
            QtW.QMessageBox.warning(self, "Save Error", "No mapping asset configured.")
            return

        # If a filepath is empty, don't load
        file_path_str = self.map_path_input.text().strip()
        if not file_path_str:
            QtW.QMessageBox.warning(self, "Save Error", "Please specify a valid mapping filepath.")
            return

        path = Path(file_path_str)

        try:
            # Load sprite mappings
            save_mappings(self, path)

            QtW.QMessageBox.information(
                self, "Mappings Saved",
                f"Successfully saved {len(self.map_frames)} frames to {path.name}."
            )

        except Exception as e:
            print(f"Error loading mappings {path.name}: {e}")
            QtW.QMessageBox.warning(
                self, "Mapping Save Error", f"Could not save mappings to {path.name}:\n{str(e)}"
            )

    def mapping_add_entry(self, file_path):
        # Prevent adding multiple mapping assets
        if self.map_widget is not None:
            return

        self.map_widget = QtW.QWidget()
        layout = QtW.QVBoxLayout(self.map_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Primary Mapping Row
        map_row_widget = QtW.QWidget()
        map_row = QtW.QHBoxLayout(map_row_widget)
        map_row.setContentsMargins(0, 0, 0, 0)

        self.map_path_input = QtW.QLineEdit(file_path)

        self.map_name_input = QtW.QLineEdit()
        self.map_name_input.setPlaceholderText("Map_")
        self.map_name_input.setFixedWidth(100)

        btn_remove = QtW.QPushButton("Remove")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(self.mapping_remove_entry)

        map_row.addWidget(self.map_path_input, stretch=1)
        map_row.addWidget(self.map_name_input)
        map_row.addWidget(btn_remove)

        # Second row (Map Version, Macro save option, DPLC option)
        map_row2_widget = QtW.QWidget()
        map_row2 = QtW.QHBoxLayout(map_row2_widget)
        map_row2.setContentsMargins(0, 0, 0, 0)

        # Map Version Dropdown
        self.map_dropdown = QtW.QComboBox()
        self.map_dropdown.setToolTip("Select Spritemap Version (Based on game)")
        # self.map_dropdown.currentIndexChanged.connect(self.on_map_dropdown_changed)

        # Later, I will add a second Sonic 3K version (for Object DPLCs)
        # An additional option will be included for user-defined formats
        self.map_dropdown.addItem("Sonic 1", userData=None)
        self.map_dropdown.addItem("Sonic 2", userData=None)
        self.map_dropdown.addItem("Sonic 3K", userData=None)
        map_row2.addWidget(self.map_dropdown, stretch=1)

        # Spacer to separate the dropdown with the checkboxes
        # Invisible spacer to keep textboxes aligned with the row above
        spacer = QtW.QWidget()
        spacer.setFixedWidth(60)
        map_row2.addWidget(spacer)

        # Save with Macros Checkbox (only affects saving to .asm)
        self.macro_cb = QtW.QCheckBox("Save with MapMacros")
        map_row2.addWidget(self.macro_cb)

        # DPLC Checkbox
        dplc_cb = QtW.QCheckBox("Enable DPLCs")
        map_row2.addWidget(dplc_cb)

        # DPLC Row (Hidden by default)
        dplc_row_widget = QtW.QWidget()
        dplc_row = QtW.QHBoxLayout(dplc_row_widget)
        dplc_row.setContentsMargins(0, 0, 0, 0)

        dplc_path_input = QtW.QLineEdit()
        dplc_path_input.setPlaceholderText("DPLC Filepath...")

        # Browse button to grab the DPLC file
        btn_dplc_browse = QtW.QPushButton("...")
        btn_dplc_browse.setFixedWidth(30)
        btn_dplc_browse.clicked.connect(lambda: self.mapping_dplc_browse(dplc_path_input))

        dplc_name_input = QtW.QLineEdit()
        dplc_name_input.setPlaceholderText("DPLC_")
        dplc_name_input.setFixedWidth(100)

        # Invisible spacer to keep textboxes aligned with the row above
        spacer2 = QtW.QWidget()
        spacer2.setFixedWidth(50)

        dplc_row.addWidget(dplc_path_input, stretch=1)
        dplc_row.addWidget(btn_dplc_browse)
        dplc_row.addWidget(dplc_name_input)
        dplc_row.addWidget(spacer2)

        # Connect checkbox to visibility toggle
        dplc_row_widget.setVisible(False)
        dplc_cb.toggled.connect(dplc_row_widget.setVisible)

        # Assembly
        layout.addWidget(map_row_widget)
        layout.addWidget(map_row2_widget)
        layout.addWidget(dplc_row_widget)

        self.map_entries_layout.addWidget(self.map_widget)
        self.mapping_update_file_controls()

    def mapping_remove_entry(self):
        # Removes the mapping/DPLC widget block and re-enables the Add button
        if self.map_widget:
            # Remove widget group from the layout
            self.map_entries_layout.removeWidget(self.map_widget)
            # Schedule widget group for deletion
            self.map_widget.deleteLater()

            # Dereference stale widget group
            self.map_widget = None
            self.map_path_input = None
            self.map_dropdown = None
            self.map_name_input = None
            self.macro_cb = None

        # This re-enables the Add button
        self.mapping_update_file_controls()

    def mapping_update_file_controls(self):
        # Disable Add and Enable Load/Save if map asset is loaded
        has_asset = self.map_widget is not None

        self.btn_map_add.setDisabled(has_asset)
        self.btn_map_load.setEnabled(has_asset)
        self.btn_map_save.setEnabled(has_asset)

    def mapping_dplc_browse(self, line_edit):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # Save dialog for new DPLC file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(
            self, "Select DPLC File", start_dir, "DPLC Files (*.asm *.bin);;All Files (*)"
        )

        # If successful, store DPLC filepath
        if file_path:
            line_edit.setText(file_path)


    # --------------------------------------------------
    # Palette File Entries
    # --------------------------------------------------
    def palette_entry_new(self):
        # Get top-level window to access project file
        main_win = self.window()
        project_dir = getattr(main_win, "project_root_dir", None)
        start_dir = str(project_dir) if project_dir else ""

        # # Save dialog for new palette file, WITHOUT creating the file
        file_path, _ = QtW.QFileDialog.getSaveFileName(self,
            "New Palette File", start_dir, "Palette Files (*.pal *.bin);;All Files (*)")

        # If successful, create a new row under the palette tab
        if file_path:
            self.palette_add_entry(file_path)

    def palette_entry_load(self):
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
                    data = f.read(num_colors * 2)  # Read 2 bytes for every color loaded
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

        # Refresh VRAM after loading new palette
        self.render_art_tiles()
        # Refresh frame window
        self.render_sprite_frame()

    def palette_entry_save(self):
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
                QtW.QMessageBox.warning(self,
                    "Save Error", f"Could not save palette file {path.name}:\n{str(e)}")

            # Advance color index for the next row file
            current_index += num_colors

    def palette_add_entry(self, file_path):
        # Appends a 3-widget row to the right-hand panel for palette editing
        row_widget = QtW.QWidget()
        row_layout = QtW.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Filepath text box
        path_input = QtW.QLineEdit(file_path)

        # Line count dropdown (1-4)
        line_combo = QtW.QComboBox()
        line_combo.addItem("1")    # Prime it with 1 for palette_update_file_controls
        line_combo.setFixedWidth(50)

        # Track the combo boxes in a list for evaluation
        self.pal_line_combos.append(line_combo)
        self.pal_rows.append((path_input, line_combo))

        # Remove button
        btn_remove = QtW.QPushButton("Remove")
        btn_remove.setFixedWidth(50)
        btn_remove.clicked.connect(
            lambda checked=False, _r=row_widget, _c=line_combo,
                   _p=path_input: self.palette_remove_entry(_r, _c, _p)
        )

        # Re-evaluate capacity whenever a dropdown value is changed
        line_combo.currentIndexChanged.connect(self.palette_update_file_controls)

        row_layout.addWidget(path_input, stretch=1)
        row_layout.addWidget(line_combo)
        row_layout.addWidget(btn_remove)

        self.pal_entries_layout.addWidget(row_widget)

        # Seems redundant, but we need an initial evaluation
        self.palette_update_file_controls()

    def palette_remove_entry(self, row_widget, line_combo, path_input):
        # Removes a palette widget row and re-evaluate capacity
        if line_combo in self.pal_line_combos:
            self.pal_line_combos.remove(line_combo)

        row = (path_input, line_combo)
        if row in self.pal_rows:
            self.pal_rows.remove(row)

        self.pal_entries_layout.removeWidget(row_widget)
        row_widget.deleteLater()

        self.palette_update_file_controls()

    def palette_update_file_controls(self):
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

    def palette_open_color_library(self, col_idx):
        # Get active color from the clicked box
        active_color = self.palette_colors[col_idx]

        # Run color picker window
        dialog = ColorLibraryDialog(active_color, self)
        if dialog.exec():
            # Apply picked color to active index
            new_color = dialog.get_color()
            self.palette_colors[col_idx] = new_color

            # Update color box
            self.palette_boxes[col_idx].set_color(new_color)
            # Refresh VRAM after loading new palette
            self.render_art_tiles()
            # Refresh frame window
            self.render_sprite_frame()


    # --------------------------------------------------
    # Rendering
    # --------------------------------------------------
    def render_art_tiles(self):
        """Renders the virtual VRAM contents into an image and refreshes the viewer canvas."""
        # Size: 16 x 128 tiles
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
            tile_x = (tile_idx % 16) * 8
            tile_y = (tile_idx // 16) * 8

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

    def render_sprite_frame(self):
        # 256x256 canvas with the center representing the sprite's X/Y origin pivot
        canvas_w, canvas_h = self.sprite_canvas_width, self.sprite_canvas_height
        center_x, center_y = canvas_w // 2, canvas_h // 2

        image = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)

        # Draw an origin crosshair to easily see the sprite's anchor pivot
        crosshair_color = QColor(255, 0, 255, 100)      # Make this an option (ColorPicker)
        for _x in range(canvas_w): image.setPixelColor(_x, center_y, crosshair_color)
        for _y in range(canvas_h): image.setPixelColor(center_x, _y, crosshair_color)

        if not self.map_frames:
            self.sprite_clear_selection()
            self.frame_spinbox.setRange(0, 0)
            self.render_sprite_image(image)
            return

        # Cap the spinbox to the number of loaded frames
        self.frame_spinbox.setMaximum(len(self.map_frames) - 1)
        frame_idx = self.frame_spinbox.value()

        # Get starting VRAM tile location (base location that start_tile + tile_offset will go off from)
        tile_idx = self.vram_spinbox.value()
        # Get base palette line (sprite mappings offset this, and the value wraps (0 to 3)
        pal_idx = self.sprpal_spinbox.value()

        if frame_idx >= len(self.map_frames):
            return

        frame_data = self.map_frames[frame_idx]

        # Iterate over every piece in this frame
        for piece_index, piece in enumerate(frame_data):
            start_tile = (tile_idx + piece['tile']) & 2047
            wid = piece['width']
            hgt = piece['height']
            px_offset = piece['x']
            py_offset = piece['y']
            pal_line = (pal_idx + piece['palette']) & 3
            x_flip = piece['x_flip']
            y_flip = piece['y_flip']

            # Selected pieces never receive the hover effect
            hovered = piece_index == self.hovered_piece and piece_index not in self.selected_pieces

            if hovered:
                target_image = QImage(canvas_w, canvas_h, QImage.Format.Format_ARGB32)
                target_image.fill(Qt.GlobalColor.transparent)
            else:
                target_image = image

            # Process tiles Top-to-Bottom, then Left-to-Right
            for tx in range(wid):
                for ty in range(hgt):
                    tile_offset = (tx * hgt) + ty
                    actual_tile_idx = start_tile + tile_offset

                    # If flipped, the placement of the 8x8 blocks mirrors
                    draw_tx = (wid - 1 - tx) if x_flip else tx
                    draw_ty = (hgt - 1 - ty) if y_flip else ty

                    if actual_tile_idx not in self.vram_tiles:
                        continue

                    pixel_indices = self.vram_tiles[actual_tile_idx]

                    # Draw the 8x8 pixels for this specific tile (Should I pull from viewer instead?)
                    for _py in range(8):
                        for _px in range(8):
                            p_val = pixel_indices[_py * 8 + _px]

                            # 0 is always transparent (Make optional)
                            if p_val == 0:
                                continue

                            # Flip the pixels within the 8x8 tile itself
                            flip_px = (7 - _px) if x_flip else _px
                            flip_py = (7 - _py) if y_flip else _py

                            # Calculate absolute pixel coordinates on the canvas
                            final_x = center_x + px_offset + (draw_tx * 8) + flip_px
                            final_y = center_y + py_offset + (draw_ty * 8) + flip_py

                            # Only draw if within bounds
                            if 0 <= final_x < canvas_w and 0 <= final_y < canvas_h:
                                color_idx = (pal_line * 16) + p_val
                                if color_idx < len(self.palette_colors):
                                    target_image.setPixelColor(final_x, final_y, self.palette_colors[color_idx])

            # Composite this piece before rendering the next piece
            if hovered:
                painter = QPainter(image)

                # Barely visible yellow background across the piece bounds
                painter.fillRect(center_x + px_offset, center_y + py_offset,
                    wid * 8, hgt * 8, QColor(255, 255, 0, 18))  # 18 = yellow BG alpha

                # Render piece partially transparent
                painter.setOpacity(0.45)    # overall piece transparency
                painter.drawImage(0, 0, target_image)
                painter.end()

        # Draw selection outlines after all sprite pieces
        if self.selected_pieces:
            painter = QPainter(image)
            painter.setPen(QColor(255, 255, 0))
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for index in sorted(self.selected_pieces):
                if not 0 <= index < len(frame_data):
                    continue

                piece = frame_data[index]

                painter.drawRect(
                    center_x + piece["x"],
                    center_y + piece["y"],
                    piece["width"] * 8 - 1,
                    piece["height"] * 8 - 1,
                )

            painter.end()

        self.render_sprite_image(image)

    def render_sprite_image(self, image):
        pixmap = QPixmap.fromImage(image)
        scaled_pixmap = pixmap.scaled(
            image.width() * self.sprite_zoom,
            image.height() * self.sprite_zoom,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self.sprite_label.setPixmap(scaled_pixmap)
