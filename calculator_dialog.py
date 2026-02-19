from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QWidget, QGridLayout, 
    QLineEdit, QGroupBox, QHBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator

class CalculatorDialog(QDialog):
    def __init__(self, parent=None, usd_rate=0.0, gold_info=None, iau_price=0.0):
        super().__init__(parent)
        self.setWindowTitle("금 차익거래 (IAU vs KRX)")
        self.setFixedSize(400, 450)
        self.usd_rate = usd_rate
        self.gold_info = gold_info or {}
        self.iau_price = iau_price
        
        # 다이얼로그 자체 스타일 (다크 테마)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: #e0e0e0; }
            QLabel { color: #e0e0e0; font-size: 14px; }
            QLineEdit { 
                background-color: #353535; color: white; border: 1px solid #555; 
                padding: 5px; border-radius: 3px; font-size: 14px;
            }
            QGroupBox { 
                border: 1px solid #555; border-radius: 5px; margin-top: 10px; 
                font-weight: bold; color: #bbb; 
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QPushButton { background-color: #1976D2; color: white; padding: 8px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1565C0; }
        """)

        layout = QVBoxLayout(self)
        
        # 1. 입력 영역
        input_group = QGroupBox("시세 입력")
        grid = QGridLayout(input_group)
        
        # 환율
        grid.addWidget(QLabel("환율 (USD/KRW):"), 0, 0)
        self.le_rate = QLineEdit()
        self.le_rate.setText(f"{self.usd_rate:.2f}")
        grid.addWidget(self.le_rate, 0, 1)

        # IAU 현재가
        grid.addWidget(QLabel("IAU 현재가 ($):"), 1, 0)
        self.le_iau = QLineEdit()
        self.le_iau.setText(f"{self.iau_price:.2f}")
        grid.addWidget(self.le_iau, 1, 1)
        
        # KRX 금
        grid.addWidget(QLabel("KRX 금 (₩/g):"), 2, 0)
        self.le_krx_spot = QLineEdit()
        krx_spot = self.gold_info.get('krx_spot', 0)
        self.le_krx_spot.setText(f"{krx_spot:.0f}")
        grid.addWidget(self.le_krx_spot, 2, 1)

        layout.addWidget(input_group)

        # 2. 계산 결과 영역
        result_group = QGroupBox("계산 결과")
        res_layout = QVBoxLayout(result_group)
        
        self.lbl_iau_krw = QLabel("IAU 환산가: - 원/g")
        self.lbl_iau_krw.setStyleSheet("font-size: 13px; color: #aaa;")
        res_layout.addWidget(self.lbl_iau_krw)
        
        self.lbl_spread = QLabel("괴리율(Premium): -")
        self.lbl_spread.setStyleSheet("font-size: 18px; font-weight: bold; color: #4DABF7; margin-top: 5px;")
        self.lbl_spread.setAlignment(Qt.AlignmentFlag.AlignCenter)
        res_layout.addWidget(self.lbl_spread)
        
        self.lbl_desc = QLabel("-")
        self.lbl_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_desc.setStyleSheet("font-size: 12px; color: #888;")
        res_layout.addWidget(self.lbl_desc)

        layout.addWidget(result_group)
        
        # 이벤트 연결
        self.le_rate.textChanged.connect(self.calculate)
        self.le_iau.textChanged.connect(self.calculate)
        self.le_krx_spot.textChanged.connect(self.calculate)
        
        # 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)
        
        # 초기 계산 실행
        self.calculate()

    def calculate(self):
        try:
            rate = float(self.le_rate.text().replace(",", ""))
            iau_usd = float(self.le_iau.text().replace(",", ""))
            krx_krw = float(self.le_krx_spot.text().replace(",", ""))
            
            # IAU 1주 ≈ 0.5843g
            grams_per_share = 0.5843
            
            # IAU 환산가(원/g) = (IAU($) * 환율) / 0.5843
            iau_krw_g = (iau_usd * rate) / grams_per_share
            
            self.lbl_iau_krw.setText(f"IAU 환산가: {iau_krw_g:,.0f} 원/g")
            
            if iau_krw_g > 0:
                # 괴리율 = (KRX - IAU환산) / IAU환산
                spread = ((krx_krw - iau_krw_g) / iau_krw_g) * 100
                self.lbl_spread.setText(f"괴리율: {spread:+.2f}%")
                
                if spread > 0:
                    self.lbl_spread.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF6B6B;") # KRX가 비쌈 (김프)
                    self.lbl_desc.setText("KRX 금이 IAU보다 고평가 상태입니다.")
                else:
                    self.lbl_spread.setStyleSheet("font-size: 18px; font-weight: bold; color: #4DABF7;") # KRX가 저렴 (역프)
                    self.lbl_desc.setText("KRX 금이 IAU보다 저평가 상태입니다.")
            else:
                self.lbl_spread.setText("괴리율: 계산 불가")
                self.lbl_spread.setStyleSheet("font-size: 18px; font-weight: bold; color: #aaa;")
                self.lbl_desc.setText("IAU 가격 또는 환율을 확인해주세요.")

        except ValueError:
            self.lbl_iau_krw.setText("IAU 환산가: 계산 불가")
            self.lbl_spread.setText("-")
            self.lbl_desc.setText("숫자를 올바르게 입력해주세요.")