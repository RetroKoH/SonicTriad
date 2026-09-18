from Constants import MDCOLOR_VALUES

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen

# Used across all editors for color handling
def snap_to_md_colors(val):
    # Snaps an RGB color value to its corresponding slider index (0-7)
    val = min(MDCOLOR_VALUES, key=lambda x: abs(x - val))
    return MDCOLOR_VALUES.index(val)

""" Color Library Classes
    These classes form Triad's native color picker
"""
class ColorLibraryBox(QtW.QToolButton):
    def __init__(self):
        super().__init__()
        self.color = QColor(0, 0, 0)
        self.selected = False
        self.setFixedSize(36, 36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def set_color(self, color, selected=False):
        self.color = QColor(color)
        self.selected = selected
        self.update()

    def paintEvent(self, a0):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color)
        if self.selected:
            painter.setPen(QPen(QColor("#666666"), 2))
            painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawRect(self.rect().adjusted(3, 3, -4, -4))


class ColorLibraryDialog(QtW.QDialog):
    def __init__(self, current_color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Color Library")

        self.current_color = QColor(current_color)
        self.r_step = snap_to_md_colors(current_color.red())
        self.g_step = snap_to_md_colors(current_color.green())
        self.b_step = snap_to_md_colors(current_color.blue())
        self.selected_color = QColor(current_color)

        self.grid_boxes = {}
        self.red_boxes = []
        self.channel_groups = {}

        self.init_ui()
        self.update_preview()

    def init_ui(self):
        layout = QtW.QVBoxLayout(self)
        layout.addWidget(QtW.QLabel("Choose a color to replace the existing color."))
        content_layout = QtW.QHBoxLayout()
        content_layout.setSpacing(16)

        # -----------------------------
        # LEFT SECTION: Blue / Green
        # -----------------------------
        grid_column = QtW.QVBoxLayout()
        grid_column.addWidget(QtW.QLabel("BLUE / GREEN"))
        grid_layout = QtW.QGridLayout()
        grid_layout.setSpacing(0)

        for row in range(8):
            g_step = 7 - row
            for b_step in range(8):
                box = ColorLibraryBox()
                box.setAccessibleName(f"Blue {b_step}, Green {g_step}")
                box.clicked.connect(lambda _, g=g_step, b=b_step: self.on_color_picked(self.r_step, g, b))
                grid_layout.addWidget(box, row, b_step)
                self.grid_boxes[g_step, b_step] = box

        grid_column.addLayout(grid_layout)
        grid_column.addStretch()
        content_layout.addLayout(grid_column)

        # -----------------------------
        # MIDDLE SECTION: Red
        # -----------------------------
        red_column = QtW.QVBoxLayout()
        red_column.addWidget(QtW.QLabel("RED"))
        red_layout = QtW.QVBoxLayout()
        red_layout.setSpacing(0)

        for row in range(8):
            r_step = 7 - row
            box = ColorLibraryBox()
            box.setAccessibleName(f"Red {r_step}")
            box.clicked.connect(lambda _, r=r_step: self.on_color_picked(r, self.g_step, self.b_step))
            red_layout.addWidget(box)
            self.red_boxes.append(box)

        red_column.addLayout(red_layout)
        red_column.addStretch()
        content_layout.addLayout(red_column)

        # Current stays unchanged while New follows the candidate color.
        details_layout = QtW.QVBoxLayout()
        previews = QtW.QHBoxLayout()

        self.current_preview = QtW.QFrame()
        self.preview_box = QtW.QFrame()

        for title, preview in (("Current", self.current_preview), ("New", self.preview_box)):
            column = QtW.QVBoxLayout()
            column.addWidget(QtW.QLabel(title))

            preview.setMinimumWidth(112)
            preview.setFixedHeight(56)

            column.addWidget(preview)
            previews.addLayout(column)

        self.current_preview.setStyleSheet(f"background-color: {self.current_color.name()}; border: 1px solid #666;")
        details_layout.addLayout(previews)
        details_layout.addSpacing(8)

        for channel in ('r', 'g', 'b'):
            row = QtW.QHBoxLayout()
            row.setSpacing(2)
            row.addWidget(QtW.QLabel(channel.upper()))
            group = QtW.QButtonGroup(self)
            group.setExclusive(True)

            for step in range(8):
                button = QtW.QPushButton(str(step))
                button.setCheckable(True)
                button.setAutoDefault(False)
                button.setFixedSize(28, 28)
                button.setAccessibleName(f"{channel.upper()} step {step}")
                group.addButton(button, step)
                row.addWidget(button)

            group.idClicked.connect(
                lambda step, ch=channel: self.on_channel_changed(ch, step)
            )
            self.channel_groups[channel] = group
            details_layout.addLayout(row)

        details_layout.addSpacing(8)
        self.cram_label = QtW.QLabel()
        self.hex_label = QtW.QLabel()

        for title, label in (("CRAM code (0B GR)", self.cram_label), ("Hex color (RR GG BB)", self.hex_label)):
            row = QtW.QHBoxLayout()
            row.addWidget(QtW.QLabel(title))
            row.addStretch()
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(label)
            details_layout.addLayout(row)

        details_layout.addStretch()
        content_layout.addLayout(details_layout)
        layout.addLayout(content_layout)

        buttons = QtW.QDialogButtonBox.StandardButton.Ok | QtW.QDialogButtonBox.StandardButton.Cancel
        btn_box = QtW.QDialogButtonBox(buttons)
        btn_box.button(QtW.QDialogButtonBox.StandardButton.Ok).setText("Apply")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def on_channel_changed(self, channel, step):
        setattr(self, f"{channel}_step", step)
        self.update_preview()

    def on_color_picked(self, r_step, g_step, b_step):
        self.r_step = r_step
        self.g_step = g_step
        self.b_step = b_step

        self.update_preview()

    def update_preview(self):
        _r = MDCOLOR_VALUES[self.r_step]
        _g = MDCOLOR_VALUES[self.g_step]
        _b = MDCOLOR_VALUES[self.b_step]
        self.selected_color = QColor(_r, _g, _b)

        for (g_step, b_step), box in self.grid_boxes.items():
            color = QColor(_r, MDCOLOR_VALUES[g_step], MDCOLOR_VALUES[b_step])
            box.set_color(color, g_step == self.g_step and b_step == self.b_step)
            box.setToolTip(f"B: {b_step}  G: {g_step}  {color.name().upper()}")
        for row, box in enumerate(self.red_boxes):
            r_step = 7 - row
            color = QColor(MDCOLOR_VALUES[r_step], _g, _b)
            box.set_color(color, r_step == self.r_step)
            box.setToolTip(f"R: {r_step}  {color.name().upper()}")

        for channel, group in self.channel_groups.items():
            group.button(getattr(self, f"{channel}_step")).setChecked(True)

        self.preview_box.setStyleSheet(f"background-color: {self.selected_color.name()}; border: 1px solid #666;")
        # Same 0BGR packing used by the palette writer (three bits per channel).
        cram_word = (self.b_step << 9) | (self.g_step << 5) | (self.r_step << 1)
        self.cram_label.setText(f"${cram_word:04X}")
        self.hex_label.setText(self.selected_color.name().upper())

    def get_color(self):
        return QColor(self.selected_color)
