from aqt.qt import *
from aqt import mw
from pathlib import Path
from .libaddon.platform import PATH_THIS_ADDON

class SessionTallyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.WindowDoesNotAcceptFocus |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150); color: white; border-radius: 5px;")
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)
        
        self.header_layout = QHBoxLayout()
        self.header_layout.setContentsMargins(5, 5, 5, 0)
        self.header_layout.addStretch()
        
        self.close_btn = QPushButton("X")
        self.close_btn.setFixedSize(16, 16)
        self.close_btn.setStyleSheet("background-color: transparent; color: #ff6666; border: none; font-weight: bold; font-family: sans-serif;")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.hide)
        
        self.header_layout.addWidget(self.close_btn)
        self.main_layout.addLayout(self.header_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background-color: transparent;") 
        
        self.items_container = QWidget()
        self.items_container.setStyleSheet("background-color: transparent;")
        
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(10, 0, 10, 10)
        self.items_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.items_container)
        self.main_layout.addWidget(self.scroll_area)
        
        self.setFixedSize(250, 900)
        
        self.item_labels = {}
        self.drag_position = None
        self.has_been_positioned = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def update_tally(self, item_name, count, image_path):
        if item_name not in self.item_labels:
            label = QLabel()
            label.setStyleSheet("background-color: transparent;")
            
            self.items_layout.addWidget(label) 
            self.item_labels[item_name] = {"label": label, "image": image_path}
            self.show()
            
        full_image_path = Path(PATH_THIS_ADDON) / image_path
        html = f'<img src="{full_image_path}" width="24" height="24"> {item_name}: {count}'
        self.item_labels[item_name]["label"].setText(html)
    
        
        if not self.has_been_positioned and self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.right() - self.width() - 20, parent_rect.top() + 50)
            self.has_been_positioned = True
        
        if self.isHidden():
            self.show()