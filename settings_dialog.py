from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None, current_peak=0.0):
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setFixedSize(300, 150)
        self.current_peak = current_peak
        
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; }
            QLabel { color: #e0e0e0; font-size: 13px; }
            QLineEdit { 
                background-color: #353535; color: white; border: 1px solid #555; 
                padding: 5px; border-radius: 3px;
            }
            QPushButton { background-color: #1976D2; color: white; padding: 6px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1565C0; }
        """)

        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("전고점 (Peak / Max Value) 수정:"))
        self.le_peak = QLineEdit()
        self.le_peak.setValidator(QDoubleValidator())
        self.le_peak.setText(str(current_peak))
        layout.addWidget(self.le_peak)
        
        layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_save = QPushButton("저장")
        btn_save.clicked.connect(self.accept)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def get_value(self):
        try:
            val_str = self.le_peak.text().replace(",", "").replace(" ", "")
            return float(val_str)
        except ValueError:
            return self.current_peak