from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QPen

from Editors import PaletteEditor
from PaletteEditor.colorbox import *

from Constants import *

""" Color Library
    These classes are used for the Color Library (Click on the preview box)
"""
class ColorLibraryMap(QtW.QLabel):
    # Emits RGB step values
    color_picked = pyqtSignal(int, int, int)

    def __init__(self, image_path="Editors/color_library.png"):
        super().__init__()
        # Load and scale color library
        pixmap = QPixmap(image_path)
        self.scaled_pixmap = pixmap.scaled(
            512, 64,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self.setPixmap(self.scaled_pixmap)
        self.setFixedSize(512, 64)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            x = ev.pos().x()
            y = ev.pos().y()
            wid = self.width() / 64.0
            hgt = self.height() / 8.0

            # Determine column/row using cell size and click coords
            col = int(x // wid)
            row = int(y // hgt)
            col = max(0, min(63, col))
            row = max(0, min(7, row))

            # Decode into 3-bit RGB steps based on the image's layout
            r_step = col // 8
            g_step = row
            b_step = col % 8

            self.color_picked.emit(r_step, g_step, b_step)


class ColorLibraryDialog(QtW.QDialog):
    def __init__(self, current_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Color Library")
        self.setFixedSize(540, 160)
        self.selected_color = current_color

        self.init_ui()

    def init_ui(self):
        layout = QtW.QVBoxLayout(self)

        self.palette_map = ColorLibraryMap("Editors/color_library.png")
        self.palette_map.color_picked.connect(self.on_color_picked)

        # Center the color library
        map_layout = QtW.QHBoxLayout()
        map_layout.addStretch()
        map_layout.addWidget(self.palette_map)
        map_layout.addStretch()
        layout.addLayout(map_layout)

        # -----------------------------
        # BOTTOM PANEL: Preview and Buttons
        # -----------------------------
        bottom_layout = QtW.QHBoxLayout()

        self.preview_box = QtW.QFrame()
        self.preview_box.setFixedSize(32, 32)
        bottom_layout.addWidget(self.preview_box)

        self.hex_label = QtW.QLabel()
        self.hex_label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        bottom_layout.addWidget(self.hex_label)

        self.update_preview(self.selected_color)

        bottom_layout.addStretch()

        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)

        btn_apply = btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok)
        btn_apply.setText("Apply")

        btn_apply.clicked.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        bottom_layout.addWidget(btn_box)

        layout.addLayout(bottom_layout)

    def on_color_picked(self, r_step, g_step, b_step):
        _r = MDCOLOR_VALUES[r_step]
        _g = MDCOLOR_VALUES[g_step]
        _b = MDCOLOR_VALUES[b_step]

        self.selected_color = QColor(_r, _g, _b)
        self.update_preview(self.selected_color)

    def update_preview(self, color):
        self.preview_box.setStyleSheet(
            f"background-color: {color.name()}; border: 1px solid #444;"
        )
        self.hex_label.setText(color.name().upper())

    def get_color(self):
        return self.selected_color


""" The following classes are subtypes for the AdvancedEditDialog class.
    They contain their own functions that edit facets of the main editor.
"""
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

        self.opt_all = QtW.QRadioButton("Entire Palette")
        self.opt_selected = QtW.QRadioButton("Selected Colors Only")

        # Default scope selection based on active selection count
        if len(self.editor.selected_indices) > 1:
            self.opt_selected.setChecked(True)
        else:
            self.opt_all.setChecked(True)

        self.opt_all.toggled.connect(self.update_preview)
        self.opt_selected.toggled.connect(self.update_preview)

        scope_layout.addWidget(self.opt_all)
        scope_layout.addWidget(self.opt_selected)
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


class ColorBlendDialog(AdvancedEditDialog):
    def __init__(self, editor):
        super().__init__(editor, title="Bland Colors")

    def setup_custom_options(self, layout):
        # -----------------------------
        # LEFT PANEL MOD: Color Blend Options
        # -----------------------------
        blend_group = QtW.QGroupBox("Blend Options")
        blend_layout = QtW.QVBoxLayout(blend_group)

        # Color Picker
        color_layout = QtW.QHBoxLayout()
        self.color_picker = QtW.QPushButton("Select Blend Color")
        self.blend_color = QColor(0, 0, 0)

        self.color_preview = QtW.QFrame()
        self.color_preview.setFixedSize(20, 20)
        self.color_preview.setStyleSheet(f"background-color: {self.blend_color.name()}; border: 1px solid #444;")

        self.color_picker.clicked.connect(self.choose_color)

        color_layout.addWidget(self.color_picker)
        color_layout.addWidget(self.color_preview)
        blend_layout.addLayout(color_layout)

        # Percentage Selector
        pct_layout = QtW.QHBoxLayout()
        pct_layout.addWidget(QtW.QLabel("Blend Amount:"))

        self.combo_pct = QtW.QComboBox()
        # 10% to 100% in increments of 10, Default: 50%
        self.combo_pct.addItems([f"{i}%" for i in range(10, 101, 10)])
        self.combo_pct.setCurrentText("50%")
        self.combo_pct.currentIndexChanged.connect(self.update_preview)

        pct_layout.addWidget(self.combo_pct)
        blend_layout.addLayout(pct_layout)

        layout.addWidget(blend_group)

    def transform_color(self, original_color):
        pct_str = self.combo_pct.currentText().replace("%", "")
        blend_factor = int(pct_str) / 100.0     # Get percentage as a decimal
        inverse_factor = 1.0 - blend_factor

        # Calculate blended RGB color
        _r = int(original_color.red() * inverse_factor + self.blend_color.red() * blend_factor)
        _g = int(original_color.green() * inverse_factor + self.blend_color.green() * blend_factor)
        _b = int(original_color.blue() * inverse_factor + self.blend_color.blue() * blend_factor)

        # Convert to a compatible color
        step_r = self.editor.snap_to_md_colors(_r)
        step_g = self.editor.snap_to_md_colors(_g)
        step_b = self.editor.snap_to_md_colors(_b)

        return QColor(MDCOLOR_VALUES[step_r], MDCOLOR_VALUES[step_g], MDCOLOR_VALUES[step_b])

    def choose_color(self):
        color = QtW.QColorDialog.getColor(self.blend_color, self, "Choose Blend Color")
        if color.isValid():
            self.blend_color = color
            self.color_preview.setStyleSheet(f"background-color: {self.blend_color.name()}; border: 1px solid #444;")
            self.update_preview()


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


""" This window does not inherit AdvancedEditDialog
    I'll redo this later on.
"""
class GradientBuilderDialog(QtW.QDialog):
    gradient_applied = pyqtSignal(list)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle("Build Gradient")
        self.setMinimumSize(680, 260)

        # Initial source color is the currently active color
        active_color = self.editor.palette_colors[self.editor.active_index]
        self.color_src = QColor(active_color)
        self.color_dst = QColor(255, 255, 255)  # Default dest is white
        self.preview_boxes = []

        # Setup this window (Unlike the others, we don't need to live update)
        self.init_ui()
        self.update_gradient()

    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)
        content_layout = QtW.QHBoxLayout()

        # -----------------------------
        # LEFT PANEL: Options
        # -----------------------------
        options_layout = QtW.QVBoxLayout()

        control_group = QtW.QGroupBox("Gradient Options")
        control_layout = QtW.QGridLayout(control_group)

        # Source Color Picker
        self.btn_src = QtW.QPushButton("Select Source Color")
        self.btn_src.clicked.connect(lambda: self.choose_color('src'))
        self.lbl_src = QtW.QFrame()
        self.lbl_src.setFixedSize(20, 20)
        self.update_color_label('src')

        control_layout.addWidget(self.btn_src, 0, 0)
        control_layout.addWidget(self.lbl_src, 0, 1)

        # Dest Color Picker
        self.btn_dst = QtW.QPushButton("Select Dest Color")
        self.btn_dst.clicked.connect(lambda: self.choose_color('dst'))
        self.lbl_dst = QtW.QFrame()
        self.lbl_dst.setFixedSize(20, 20)
        self.update_color_label('dst')

        control_layout.addWidget(self.btn_dst, 1, 0)
        control_layout.addWidget(self.lbl_dst, 1, 1)

        # Length Configuration
        control_layout.addWidget(QtW.QLabel("Gradient Length:"), 2, 0)
        self.grad_length = QtW.QSpinBox()
        self.grad_length.setRange(2, PALEDIT_MAXCOLORS)
        self.grad_length.setValue(8)
        self.grad_length.valueChanged.connect(self.update_gradient)
        control_layout.addWidget(self.grad_length, 2, 1)

        # Loop Toggle
        self.chk_loop = QtW.QCheckBox("Loop Gradient")
        self.chk_loop.toggled.connect(self.update_gradient)
        control_layout.addWidget(self.chk_loop, 3, 0)

        options_layout.addWidget(control_group)
        options_layout.addStretch()
        content_layout.addLayout(options_layout, stretch=1)

        # -----------------------------
        # RIGHT PANEL: Gradient Preview
        # -----------------------------
        preview_group = QtW.QGroupBox("Gradient Preview")
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
        self.gradient_applied.emit(self.calc_gradient())
        self.accept()

    def update_gradient(self):
        # Rebuild gradient on change
        for box in self.preview_boxes:
            box.deleteLater()
        self.preview_boxes.clear()

        colors = self.calc_gradient()
        MAX_COLUMNS = 16
        for idx, color in enumerate(colors):
            row, col = idx // MAX_COLUMNS, idx % MAX_COLUMNS
            box = QtW.QFrame()
            box.setFixedSize(20, 20)
            box.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #444;")
            self.grid_layout.addWidget(box, row, col)
            self.preview_boxes.append(box)

    def choose_color(self, target):
        current = self.color_src if target == 'src' else self.color_dst
        color = QtW.QColorDialog.getColor(current, self, "Select Color")

        if color.isValid():
            if target == 'src':
                self.color_src = color
            else:
                self.color_dst = color

            self.update_color_label(target)
            self.update_gradient()

    def update_color_label(self, target):
        color = self.color_src if target == 'src' else self.color_dst
        lbl = self.lbl_src if target == 'src' else self.lbl_dst
        lbl.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #444;")

    def calc_gradient(self):
        length = self.grad_length.value()
        loop = self.chk_loop.isChecked()
        colors = []

        for _i in range(length):
            if loop:
                # Wave mapping (NEW): returns a blend factor (_t) that goes from 0 to 1 and back to >0
                _t = 1.0 - abs(1.0 - (2.0 * _i / length))
            else:
                # Linear mapping (Original Triad: merge_color(src, dest, ((i-pals[a])/(grad_length-1))) )
                _t = _i / (length - 1) if length > 1 else 0

            inv_t = 1.0 - _t
            _r = int(self.color_src.red() * inv_t + self.color_dst.red() * _t)
            _g = int(self.color_src.green() * inv_t + self.color_dst.green() * _t)
            _b = int(self.color_src.blue() * inv_t + self.color_dst.blue() * _t)

            # Convert to MD colors
            step_r = self.editor.snap_to_md_colors(_r)
            step_g = self.editor.snap_to_md_colors(_g)
            step_b = self.editor.snap_to_md_colors(_b)
            colors.append(QColor(MDCOLOR_VALUES[step_r], MDCOLOR_VALUES[step_g], MDCOLOR_VALUES[step_b]))

        return colors


""" Basic Palette Extractor
    To-Do: Add full palette generation from screenshot 
"""
class PaletteExtractDialog(QtW.QDialog):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setWindowTitle("Extract Palette")
        self.setMinimumSize(800, 600)

        self.init_ui()

    def init_ui(self):
        main_layout = QtW.QVBoxLayout(self)

        # Top Bar: Load Button & Status
        top_layout = QtW.QHBoxLayout()
        btn_load = QtW.QPushButton("Load Image...")
        btn_load.clicked.connect(self.browse_image)
        lbl_status = QtW.QLabel("Left-Click to Pick Color | Scroll to Zoom | Right-Click to Pan")

        top_layout.addWidget(btn_load)
        top_layout.addSpacing(15)
        top_layout.addWidget(lbl_status)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # Workspace: Picker View + Magnifier
        workspace_layout = QtW.QHBoxLayout()

        self.picker_view = ImagePickerView()
        self.picker_view.pixel_hovered.connect(self.on_pixel_hover)
        self.picker_view.pixel_clicked.connect(self.on_pixel_picked)

        self.magnifier = MagnifierWidget()

        # Right Side Panel
        side_panel = QtW.QVBoxLayout()
        side_panel.addWidget(self.magnifier)
        side_panel.addStretch()

        workspace_layout.addWidget(self.picker_view, stretch=1)
        workspace_layout.addLayout(side_panel)
        main_layout.addLayout(workspace_layout)

    def browse_image(self):
        file_path, _ = QtW.QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.bmp *.gif *.jpg)"
        )
        if file_path:
            self.picker_view.load_image(file_path)

    def on_pixel_hover(self, image, scene_pos):
        self.magnifier.update_view(image, scene_pos)

    def on_pixel_picked(self, raw_color):
        # Snaps picked color
        _r = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.red()))
        _g = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.green()))
        _b = min(MDCOLOR_VALUES, key=lambda x: abs(x - raw_color.blue()))
        snapped_color = QColor(_r, _g, _b)

        # # Record state before extracting color
        self.editor.push_undo_state()

        # Apply to current index in main editor
        self.editor.apply_color_change(snapped_color)
        self.editor.unsaved_changes = True

        # Advance selection sequentially, wrapping around if needed
        next_idx = (self.editor.active_index + 1) % len(self.editor.palette_colors)
        self.editor.active_index = next_idx
        self.editor.selected_indices = [next_idx]
        self.editor.refresh_selection_ui()


class ImagePickerView(QtW.QGraphicsView):
    """Handles image display, zoom, pan, and click/hover events for PaletteExtractDialog"""
    pixel_hovered = pyqtSignal(QImage, QPointF)
    pixel_clicked = pyqtSignal(QColor)

    def __init__(self):
        super().__init__()
        self.scene = QtW.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QtW.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QtW.QGraphicsView.DragMode.NoDrag)

        # Optional: Hide scroll-bars
#        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
#        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.image = None
        self.image_map = None
        self.pan_start = None   # initial mouse position on right-click

    def load_image(self, file_path):
        self.image = QImage(file_path)
        pixmap = QPixmap.fromImage(self.image)
        self.scene.clear()
        self.image_map = self.scene.addPixmap(pixmap)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event):
        zoom_factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(zoom_factor, zoom_factor)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

        # Handle Right-Click Panning
        if (event.buttons() & Qt.MouseButton.RightButton) and self.pan_start is not None:
            delta = event.pos() - self.pan_start
            self.pan_start = event.pos()

            # Scroll canvas in reverse direction of mouse motion
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            return

        # Magnifier updates
        if self.image_map and self.image:
            scene_pos = self.mapToScene(event.pos())
            self.pixel_hovered.emit(self.image, scene_pos)

    def mousePressEvent(self, event):
        # Left-click: Extract color
        if event.button() == Qt.MouseButton.LeftButton and self.image_map and self.image:
            scene_pos = self.mapToScene(event.pos())
            x, y = int(scene_pos.x()), int(scene_pos.y())
            if 0 <= x < self.image.width() and 0 <= y < self.image.height():
                self.pixel_clicked.emit(self.image.pixelColor(x, y))

        # Right-click: Panning
        elif event.button() == Qt.MouseButton.RightButton:
            self.pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        # Right-click: Stop panning
        if event.button() == Qt.MouseButton.RightButton:
            self.pan_start = None
            self.unsetCursor()
            event.accept()
            return

        super().mouseReleaseEvent(event)


class MagnifierWidget(QtW.QWidget):
    """Displays a zoomed-in pixel grid and crosshair for PaletteExtractDialog"""
    def __init__(self):
        super().__init__()
        self.setFixedSize(140, 140)
        self.image = None
        self.hover_pos = QPointF(0, 0)
        self.zoom = 10  # Pixel scale factor

    def update_view(self, image, pos):
        self.image = image
        self.hover_pos = pos
        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.black)
        if not self.image:
            return

        src_x, src_y = int(self.hover_pos.x()), int(self.hover_pos.y())
        pixels_across = self.width() // self.zoom
        half_pixels = pixels_across // 2

        # Draw magnified pixels
        for dx in range(-half_pixels, half_pixels + 1):
            for dy in range(-half_pixels, half_pixels + 1):
                px, py = src_x + dx, src_y + dy
                if 0 <= px < self.image.width() and 0 <= py < self.image.height():
                    color = self.image.pixelColor(px, py)
                    rect = QRectF((dx + half_pixels) * self.zoom, (dy + half_pixels) * self.zoom, self.zoom, self.zoom)
                    painter.fillRect(rect, color)

        # Draw grid
        painter.setPen(QColor(80, 80, 80, 180))
        for i in range(pixels_across + 1):
            painter.drawLine(i * self.zoom, 0, i * self.zoom, self.height())
            painter.drawLine(0, i * self.zoom, self.width(), i * self.zoom)

        # Draw center crosshair
        center = half_pixels * self.zoom
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        painter.drawRect(center, center, self.zoom, self.zoom)
        painter.setPen(QPen(Qt.GlobalColor.black, 1, Qt.PenStyle.DotLine))
        painter.drawRect(center, center, self.zoom, self.zoom)
