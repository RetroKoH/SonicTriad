import PyQt6.QtWidgets as QtW

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QDrag

class SpriteFrameList(QtW.QListWidget):
    frameMoveRequested = pyqtSignal(int, int)

    def startDrag(self, supportedActions):
        self._drag_row = self.currentRow()

        if self._drag_row < 0:
            return

        drag = QDrag(self)
        index = self.model().index(self._drag_row, 0)

        drag.setMimeData(self.model().mimeData([index]))
        drag.setPixmap(self.currentItem().icon().pixmap(QSize(96, 96)))

        try:
            drag.exec(Qt.DropAction.MoveAction)

        finally:
            self._drag_row = None

    def dragEnterEvent(self, e):
        if e.source() is not self:
            e.ignore()
            return

        super().dragEnterEvent(e)
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    def dragMoveEvent(self, e):
        if e.source() is not self:
            e.ignore()
            return

        super().dragMoveEvent(e)
        e.setDropAction(Qt.DropAction.MoveAction)
        e.accept()

    def dropEvent(self, event):
        old_row = getattr(self, "_drag_row", None)

        if event.source() is not self or old_row is None:
            event.ignore()
            return

        # Find the insertion point in the current list
        insertion_row = self.count()

        for row in range(self.count()):
            rect = self.visualItemRect(self.item(row))

            if event.position().y() < rect.center().y():
                insertion_row = row
                break

        # Removing the original row shifts later positions up
        new_row = insertion_row

        if insertion_row > old_row:
            new_row -= 1

        if new_row != old_row:
            self.frameMoveRequested.emit(old_row, new_row)

        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
