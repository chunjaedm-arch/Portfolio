from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QGridLayout, QLabel, QLineEdit, QPushButton, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QColor, QFont
from datetime import datetime
from shared_utils import HARDCODED_YIELDS, calc_yearly_yield

class HistoryView(QWidget):
    save_snapshot_requested = pyqtSignal(str, float, float, float, str)
    delete_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.selected_history_id = None
        self.yearly_yield_data = []
        self.current_f_asset = 0
        self.current_t_asset = 0
        self._is_editing = False
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.history_sheet = QTreeWidget()
        self.h_columns = ["날짜", "금융자산", "총자산", "순입고", "투자손익", "투자수익률", "자산증감율", "비고"]
        self.history_sheet.setHeaderLabels(self.h_columns)
        
        self.history_sheet.setAlternatingRowColors(True)
        self.history_sheet.setStyleSheet("""
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

        header = self.history_sheet.header()
        header.setSectionsMovable(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter) 

        for i in range(self.history_sheet.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)


        self.history_sheet.itemSelectionChanged.connect(self.on_select)
        left_layout.addWidget(self.history_sheet)

        self.create_edit_area(left_layout)

        self.yield_panel = QWidget()
        self.yield_layout = QVBoxLayout(self.yield_panel)

        main_layout.addWidget(left_widget, 7)
        main_layout.addWidget(self.yield_panel, 3)

    def create_edit_area(self, parent_layout):
        edit_group = QGroupBox("📝 기록 관리")
        edit_group.setStyleSheet("color: white; font-weight: bold;")
        edit_layout = QGridLayout(edit_group)
        
        edit_layout.addWidget(QLabel("날짜:"), 0, 0)
        self.ent_h_date = QLineEdit()
        self.ent_h_date.setText(datetime.now().strftime("%Y-%m-%d"))
        edit_layout.addWidget(self.ent_h_date, 0, 1)
        
        edit_layout.addWidget(QLabel("금융자산:"), 0, 2)
        self.ent_h_f_asset = QLineEdit()
        edit_layout.addWidget(self.ent_h_f_asset, 0, 3)
        
        edit_layout.addWidget(QLabel("총자산:"), 0, 4)
        self.ent_h_t_asset = QLineEdit()
        edit_layout.addWidget(self.ent_h_t_asset, 0, 5)
        
        edit_layout.addWidget(QLabel("순입고:"), 1, 0)
        self.ent_h_deposit = QLineEdit()
        edit_layout.addWidget(self.ent_h_deposit, 1, 1)
        
        edit_layout.addWidget(QLabel("비고:"), 1, 2)
        self.ent_h_memo = QLineEdit()
        edit_layout.addWidget(self.ent_h_memo, 1, 3, 1, 3)
        
        self.btn_new = QPushButton("➕ 신규등록")
        self.btn_new.clicked.connect(self.emit_new_snapshot)
        self.btn_new.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        edit_layout.addWidget(self.btn_new, 0, 6)

        self.btn_update = QPushButton("✏️ 수정")
        self.btn_update.clicked.connect(self.emit_save_snapshot)
        self.btn_update.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold;")
        self.btn_update.setEnabled(False)
        edit_layout.addWidget(self.btn_update, 1, 6)

        btn_delete = QPushButton("🗑️ 삭제")
        btn_delete.clicked.connect(self.emit_delete)
        btn_delete.setStyleSheet("background-color: #C62828; color: white; font-weight: bold;")
        edit_layout.addWidget(btn_delete, 2, 6)

        parent_layout.addWidget(edit_group)

    def on_select(self):
        selected = self.history_sheet.selectedItems()
        if not selected: return
        item = selected[0]
        self.selected_history_id = item.text(0)
        self.ent_h_date.setText(item.text(0))
        self.ent_h_f_asset.setText(item.text(1).replace(",", ""))
        self.ent_h_t_asset.setText(item.text(2).replace(",", ""))
        self.ent_h_deposit.setText(item.text(3).replace(",", "").replace("+", ""))
        self.ent_h_memo.setText(item.text(7))
        self._is_editing = True
        self.btn_update.setEnabled(True)

    def emit_new_snapshot(self):
        """신규등록: 폼 데이터를 새 기록으로 저장하고 폼 초기화"""
        try:
            d = self.ent_h_date.text()
            f_text = self.ent_h_f_asset.text().replace(",", "")
            f = float(f_text) if f_text else self.current_f_asset
            t_text = self.ent_h_t_asset.text().replace(",", "")
            t = float(t_text) if t_text else self.current_t_asset
            dep = float(self.ent_h_deposit.text().replace(",", "").replace("+", "") or 0)
            memo = self.ent_h_memo.text()
            self.save_snapshot_requested.emit(d, f, t, dep, memo)
            # 저장 후 폼 초기화 (오늘 날짜 + 현재 자산값)
            self.ent_h_date.setText(datetime.now().strftime("%Y-%m-%d"))
            self.ent_h_f_asset.setText(f"{self.current_f_asset:,.0f}")
            self.ent_h_t_asset.setText(f"{self.current_t_asset:,.0f}")
            self.ent_h_deposit.clear()
            self.ent_h_memo.clear()
            self._is_editing = False
            self.btn_update.setEnabled(False)
            self.history_sheet.clearSelection()
        except ValueError: pass

    def emit_save_snapshot(self):
        """수정: 선택된 기존 기록을 업데이트"""
        try:
            d = self.ent_h_date.text()
            
            # 입력값이 비어있으면 현재 자산 값 사용, 아니면 입력값 사용
            f_text = self.ent_h_f_asset.text().replace(",", "")
            f = float(f_text) if f_text else self.current_f_asset
            
            t_text = self.ent_h_t_asset.text().replace(",", "")
            t = float(t_text) if t_text else self.current_t_asset
            
            dep = float(self.ent_h_deposit.text().replace(",", "").replace("+", "") or 0)
            memo = self.ent_h_memo.text()
            self.save_snapshot_requested.emit(d, f, t, dep, memo)
        except ValueError: pass

    def emit_delete(self):
        d = self.ent_h_date.text()
        if d:
            self.delete_requested.emit(d)

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def draw_yield_panel(self, history_cache, current_f_asset=0):
        self.clear_layout(self.yield_layout)

        lbl_title = QLabel("[연도별 수익률]")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; color: white; margin-bottom: 5px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.yield_layout.addWidget(lbl_title)

        tv_yield = QTreeWidget()
        tv_yield.setHeaderLabels(["연도", "순입고금액", "투자수익", "수익률"])
        tv_yield.setStyleSheet(self.history_sheet.styleSheet())
        self.yield_layout.addWidget(tv_yield)
        tv_yield.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        tv_yield.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        tv_yield.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        tv_yield.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        tv_yield.header().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)

        # 공통 모듈에서 연도별 수익률 계산
        yield_rows = calc_yearly_yield(history_cache, current_f_asset)

        # 내보내기용 데이터 저장
        self.yearly_yield_data = [
            {"연도": r["year"], "순입고": r["deposit"], "투자수익": r["profit"], "수익률": r["roi"]}
            for r in yield_rows
        ]

        for row in yield_rows:
            has_actual = row["has_actual"]
            in_hardcoded = row["in_hardcoded"]
            roi_val = row["roi_val"]

            item = QTreeWidgetItem(tv_yield)
            item.setText(0, row["year"])

            if has_actual:
                item.setText(1, row["deposit"])
                item.setText(2, row["profit"])
                item.setText(3, row["roi"])
                if row["deposit_sum"] is not None and row["deposit_sum"] < 0:
                    item.setForeground(1, QColor("#FF6B6B"))
                if row["profit_sum"] is not None and row["profit_sum"] < 0:
                    item.setForeground(2, QColor("#FF6B6B"))
            elif in_hardcoded:
                item.setText(1, "")
                item.setText(2, "")
                item.setText(3, row["roi"])
            else:
                item.setText(1, "")
                item.setText(2, "")
                item.setText(3, "")

            if roi_val is not None and (has_actual or in_hardcoded):
                if roi_val < 0:
                    item.setForeground(3, QColor("#FF6B6B"))
                elif roi_val >= 10.0:
                    item.setForeground(3, QColor("#4DABF7"))

            item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter)
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        

    def update_table(self, history_data, current_f_asset=0, current_t_asset=0):
        self.current_f_asset = current_f_asset
        self.current_t_asset = current_t_asset
        self.history_sheet.clear()
        
        rows = []
        prev_f, prev_t = 0, 0
        
        for item in history_data:
            f, t, dep = item['f_asset'], item['t_asset'], item['deposit']
            profit = (f - prev_f - dep) if prev_f > 0 else 0
            roi = (profit / prev_f * 100) if prev_f > 0 else 0
            growth = ((t - prev_t) / prev_t * 100) if prev_t > 0 else 0
            
            rows.append({
                "item": item, "profit": profit, "roi": roi, "growth": growth
            })
            prev_f, prev_t = f, t

        for row in reversed(rows):
            item = row['item']
            tree_item = QTreeWidgetItem(self.history_sheet)
            
            tree_item.setText(0, item['date'])
            tree_item.setText(1, f"{item['f_asset']:,.0f}")
            tree_item.setText(2, f"{item['t_asset']:,.0f}")
            tree_item.setText(3, f"{item['deposit']:+,.0f}")
            tree_item.setText(4, f"{row['profit']:+,.0f}")
            tree_item.setText(5, f"{row['roi']:+.2f}%")
            tree_item.setText(6, f"{row['growth']:+.2f}%")
            tree_item.setText(7, item['memo'])
            
            if item['deposit'] < 0:
                tree_item.setForeground(3, QColor("#FF6B6B"))

            if row['profit'] < 0:
                red_color = QColor("#FF6B6B")
                tree_item.setForeground(4, red_color)
                tree_item.setForeground(5, red_color)
            
            elif row['roi'] >= 2.0:
                blue_color = QColor("#4DABF7")
                tree_item.setForeground(4, blue_color)
                tree_item.setForeground(5, blue_color)
                
                font = tree_item.font(5)
                font.setBold(True)
                tree_item.setFont(4, font)
                tree_item.setFont(5, font)

            for col in [1, 2, 3, 4, 5, 6]:
                tree_item.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            tree_item.setTextAlignment(0, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        self.ent_h_f_asset.setText(f"{current_f_asset:,.0f}")
        self.ent_h_t_asset.setText(f"{current_t_asset:,.0f}")

        self.draw_yield_panel(history_data, current_f_asset)

    def save_settings(self):
        settings = QSettings("PortfolioManager", "HistoryView")
        settings.setValue("headerState", self.history_sheet.header().saveState())

    def load_settings(self):
        settings = QSettings("PortfolioManager", "HistoryView")
        state = settings.value("headerState")
        if state and hasattr(self, 'history_sheet'):
            self.history_sheet.header().restoreState(state)