import json

import PyQt6.QtWidgets as QtW
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QMimeData
from PyQt6.QtGui import QColor, QDrag

from UI.themes import THEMES
from Constants import PALEDIT_MAXCOLORS

""" Color Box (PaletteEditor)
    Used within the main palette editor
    Has drag-and-drop mechanics and changes style upon selection
"""
class ColorBox(QtW.QFrame):
    clicked = pyqtSignal(int, QColor)

    def __init__(self, index, color=QColor(0, 0, 0)):
        super().__init__()
        self.index = index
        self.color = color
        self.editor = None
        self.is_selected = False
        self.is_updating = False
        self.pending_single_select = False  # To differentiate selection clicks and dragging clicks

        self.setFixedSize(32, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Drag and Drop
        self.setAcceptDrops(True)
        self.drag_start_pos = None

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

    def changeEvent(self, a0):
        # Trigger update_style whenever app theme changes
        if a0.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not self.is_updating:
                self.update_style()
        super().changeEvent(a0)

    def update_style(self):
        app = QtW.QApplication.instance()
        theme = getattr(app, "active_theme", THEMES["dark"])
        self.is_updating = True

        if self.is_selected:
            border_color = theme.get("box_selected", "#FFFFFF")
            border_width = "3px"
        else:
            border_color = theme.get("border", "#444444")
            border_width = "1px"

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color.name()};
                border: {border_width} solid {border_color};
                border-radius: 4px;
            }}
        """)

        self.is_updating = False

    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            # Get starting position for drag-and-drop
            self.drag_start_pos = a0.pos()
            modifiers = a0.modifiers()

            if self.editor:
                has_modifier = modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)

                # Defer single selection if clicking an item already inside a multi-selection
                if (
                    not has_modifier and self.index in self.editor.selected_indices
                    and len(self.editor.selected_indices) > 1
                ):
                    self.pending_single_select = True
                else:
                    self.pending_single_select = False
                    self.editor.select_colors(self.index, modifiers)

    def mouseReleaseEvent(self, a0):
        # If clicked and released without dragging, apply single selection
        if a0.button() == Qt.MouseButton.LeftButton and self.pending_single_select:
            self.pending_single_select = False
            if self.editor:
                self.editor.select_colors(self.index, a0.modifiers())

        super().mouseReleaseEvent(a0)

    def mouseMoveEvent(self, a0):
        if not (a0.buttons() & Qt.MouseButton.LeftButton) or not self.drag_start_pos:
            return

        # Check if drag threshold reached
        if (a0.pos() - self.drag_start_pos).manhattanLength() < QtW.QApplication.startDragDistance():
            return

        # Cancel deferred selection update when dragging starts
        self.pending_single_select = False

        # Determine indices to drag
        selected = sorted(self.editor.selected_indices) if self.editor else [self.index]

        # Check if selected indices form a contiguous block
        is_contiguous = len(selected) > 0 and (selected[-1] - selected[0] == len(selected) - 1)

        if is_contiguous and self.index in selected:
            # Drag the whole contiguous block (Pal size will NOT extend)
            drag_indices = selected
        else:
            # Fallback to single dragged index if non-contiguous
            drag_indices = [self.index]

        # Store source index list
        # We need to dump to JSON because Qt's drag-and-drop system does not understand
        # Python structures (such as the lists that store palette data)!
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-palette-indices", json.dumps(drag_indices).encode("utf-8"))
        drag.setMimeData(mime)

        # Visual drag preview
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(a0.pos())

        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, a0):
        if a0.mimeData().hasFormat("application/x-palette-indices"):
            a0.acceptProposedAction()

    def dropEvent(self, a0):
        if not a0.mimeData().hasFormat("application/x-palette-indices"):
            return

        # Reconstruct Python index data
        data = a0.mimeData().data("application/x-palette-indices").data().decode("utf-8")
        src_indices = json.loads(data)
        target_start = self.index

        # Swap colors through the editor
        if self.editor:
            self.editor.swap_colors(src_indices, target_start)

        a0.acceptProposedAction()

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
        self.editor.refresh_clipboard()

        # If only Copying, stop here. Otherwise, remove copied colors
        if cut:
            # Delete in reverse order to avoid issues with index shifting
            sorted_indices.reverse()
            # Unsaved flag and undo state recording handled here
            self.editor.remove_colors(sorted_indices)

    def paste_colors(self, mode, target_index):
        if not self.editor.clipboard_colors:
            return

        self.editor.push_undo_state()  # Record state before pasting colors

        clipboard_length = len(self.editor.clipboard_colors)

        if mode == "over":
            # Overwrite existing slots
            start = target_index

            if max(len(self.editor.palette_colors), start + clipboard_length) > PALEDIT_MAXCOLORS:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction",
                    f"Pasting {clipboard_length} colors here exceeds the color limit. " +
                    "Some colors will not be pasted."
                )

            # Paste over, and clamp palette at max length.
            for _i, color in enumerate(self.editor.clipboard_colors):
                idx = start + _i
                if idx < len(self.editor.palette_colors):
                    self.editor.palette_colors[idx] = QColor(color)
                elif idx < PALEDIT_MAXCOLORS:
                    self.editor.palette_colors.append(QColor(color))
                else:
                    break

        else:
            # Paste before or after the current index, shifting other colors accordingly
            start = target_index if mode == "before" else target_index + 1

            if len(self.editor.palette_colors) + clipboard_length > PALEDIT_MAXCOLORS:
                QtW.QMessageBox.warning(
                    self, "Palette Size Restriction",
                    f"Pasting {clipboard_length} colors here exceeds the color limit. " +
                    "Some colors will not be pasted."
                )

            # Paste and shift, and clamp palette length.
            for i, color in enumerate(self.editor.clipboard_colors):
                self.editor.palette_colors.insert(start + i, QColor(color))

        # Rebuild from the start index onward
        self.editor.rebuild_grid(start)

        end = min(start + clipboard_length, len(self.editor.palette_colors))

        # Automatically select the newly pasted colors
        self.editor.active_index = start
        self.editor.selected_indices = list(range(start, end))
        self.editor.refresh_selection_ui()

        self.editor.unsaved_changes = True

    def insert_color(self, mode, target_index):
        if len(self.editor.palette_colors) >= PALEDIT_MAXCOLORS:
            QtW.QMessageBox.warning(
                self, "Palette Size Restriction", f"Palette cannot have more than {PALEDIT_MAXCOLORS} colors."
            )
            return

        self.editor.push_undo_state()  # Record state before inserting colors

        index = target_index if mode == "before" else target_index + 1
        self.editor.palette_colors.insert(index, QColor(0, 0, 0))
        self.editor.rebuild_grid(index)
        self.editor.selected_indices = [index]
        self.editor.active_index = index
        self.editor.refresh_selection_ui()

        self.editor.unsaved_changes = True

    def clear_color(self, index):
        if not self.editor.selected_indices:
            return

        self.editor.push_undo_state()  # Record state before clearing colors

        black = QColor(0, 0, 0)
        for idx in self.editor.selected_indices:
            self.editor.palette_colors[idx] = black
            self.editor.boxes[idx].set_color(black)

        self.editor.update_preview_box(black)

        self.editor.unsaved_changes = True

    def delete_color(self, index):
        if not self.editor.selected_indices:
            return

        # Delete in reverse order to avoid issues with index shifting
        sorted_indices = sorted(self.editor.selected_indices, reverse=True)
        # Unsaved flag and undo state recording handled here
        self.editor.remove_colors(sorted_indices)


""" Preview Color Box (PaletteEditor)
    Used along with the main palette editor
    Previews the actively selected color and open color library
"""
class PreviewColorBox(QtW.QFrame):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(60, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


    def mousePressEvent(self, a0):
        if a0.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(a0)


""" Mini Color Box (PaletteEditor)
    Used along with the sprite editor
    Mini version of the standard box, with less functionality
"""
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
