from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QFont

class AssetView(QWidget):
    save_requested = pyqtSignal(str, dict)
    delete_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.sheet = QTreeWidget()
        self.columns = ["대분류", "소분류", "품명", "리밸런싱예정금액", "평가액(합계)", "금액(달러)", "금액(엔)", "금액(원)", "수량", "티커", "목표비중", "전일대비", "단가", "비고"]
        self.sheet.setHeaderLabels(self.columns)
        
        self.sheet.setAlternatingRowColors(True)
        self.sheet.setStyleSheet("""
            QTreeWidget {
                background-color: #2b2b2b;
                alternate-background-color: #353535;
                color: #e0e0e0;
                gridline-color: #404040;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
            }
        """)
        
        self.load_settings()
        
        header = self.sheet.header()
        header.setSectionsMovable(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter) 
        
        for i in range(self.sheet.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            
        self.sheet.itemDoubleClicked.connect(self.on_item_double_click)
        layout.addWidget(self.sheet)
        
        self.create_edit_area(layout)

    def create_edit_area(self, parent_layout):
        self.edit_group = QGroupBox("자산 상세 입력 (티커 입력 시 금액 자동 계산)")
        self.edit_group.setStyleSheet("color: white; font-weight: bold;")
        grid = QGridLayout()
        self.edit_group.setLayout(grid)
        
        self.asset_inputs = {}
        form_config = [
            ("품명", 0, 0, "품명"), ("대분류", 0, 2, "대분류"), ("소분류", 0, 4, "소분류"), ("티커", 0, 6, "티커"),
            ("수량", 1, 0, "수량"), ("금액(달러)", 1, 2, "금액(달러)"), ("금액(엔)", 1, 4, "금액(엔)"), ("금액(원)", 1, 6, "금액(원)"),
            ("목표비중", 2, 0, "목표비중"), ("비고", 2, 2, "비고")
        ]
        
        for label_text, r, c, key in form_config:
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #bbb;")
            grid.addWidget(lbl, r, c)
            le = QLineEdit()
            self.asset_inputs[key] = le
            if key == "비고":
                grid.addWidget(le, r, c+1, 1, 5)
            else:
                grid.addWidget(le, r, c+1)
                
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("💾 저장/업데이트")
        btn_save.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        btn_save.clicked.connect(self.emit_save)
        
        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.setStyleSheet("background-color: #C62828; color: white; font-weight: bold;")
        btn_delete.clicked.connect(self.emit_delete)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        
        grid.addLayout(btn_layout, 3, 0, 1, 8)
        parent_layout.addWidget(self.edit_group)

    def on_item_double_click(self, item, column):
        mapping = {
            "대분류": 0, "소분류": 1, "품명": 2, "금액(달러)": 5, "금액(엔)": 6, 
            "금액(원)": 7, "수량": 8, "티커": 9, "목표비중": 10, "비고": 13
        }
        for key, col_idx in mapping.items():
            val = item.text(col_idx).replace(",", "").replace("%", "")
            if key in self.asset_inputs:
                self.asset_inputs[key].setText(val)

    def emit_save(self):
        name = self.asset_inputs["품명"].text()
        if not name: return
        data = {k: v.text() for k, v in self.asset_inputs.items()}
        self.save_requested.emit(name, data)

    def emit_delete(self):
        name = self.asset_inputs["품명"].text()
        if name:
            self.delete_requested.emit(name)

    def save_settings(self):
        settings = QSettings("PortfolioManager", "AssetView")
        settings.setValue("headerState", self.sheet.header().saveState())

    def load_settings(self):
        settings = QSettings("PortfolioManager", "AssetView")
        state = settings.value("headerState")
        if state:
            self.sheet.header().restoreState(state)