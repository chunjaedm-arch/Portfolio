import sys
import os
from datetime import datetime, timezone
import json

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QDialog, QGridLayout,
    QTreeWidget, QTreeWidgetItem, QGroupBox, QStackedWidget,
    QFileDialog
)
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from config import config
from login_dialog import LoginDialog
from api_manager import APIManager
from db_manager import DBManager
from data_processor import DataProcessor
from view_asset import AssetView
from view_history import HistoryView
from settings_dialog import SettingsDialog
from view_chart import ChartView
from view_analysis import AnalysisView
from dashboard_view import DashboardView
from data_exporter import DataExporter
from calculator_dialog import CalculatorDialog
from style_manager import StyleManager

class Preloader(QThread):
    finished_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.api_manager = APIManager()

    def run(self):
        try:
            # 1. 환율 조회
            usd, jpy, cny, brl, source = self.api_manager.fetch_exchange_rates()
            usd_rate = usd if usd is not None else 0.0
            jpy_rate = jpy if jpy is not None else 0.0
            cny_rate = cny if cny is not None else 0.0
            brl_rate = brl if brl is not None else 0.0

            # 2. 금 시세 및 코인 프리미엄 조회
            gold_prices = self.api_manager.get_detailed_gold_prices(usd_rate)
            upbit_usdt, _ = self.api_manager.get_upbit_price("USDT")
            
            # 3. 주요 지수 조회
            indices = self.api_manager.fetch_market_indices()
            
            self.finished_data.emit({
                "usd_rate": usd_rate,
                "jpy_rate": jpy_rate,
                "cny_rate": cny_rate,
                "brl_rate": brl_rate,
                "gold_prices": gold_prices,
                "upbit_usdt": upbit_usdt,
                "indices": indices,
                "source": source
            })
        except Exception as e:
            print(f"Preload error: {e}")

class PortfolioLoader(QThread):
    finished_data = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, api_manager, db_manager, data_processor, id_token, preloaded_data=None):
        super().__init__()
        self.api_manager = api_manager
        self.db_manager = db_manager
        self.data_processor = data_processor
        self.id_token = id_token
        self.preloaded_data = preloaded_data

    def run(self):
        try:
            # Preloaded 데이터가 있으면 사용, 없으면 직접 조회
            if self.preloaded_data:
                usd_rate = self.preloaded_data.get('usd_rate', 0.0)
                jpy_rate = self.preloaded_data.get('jpy_rate', 0.0)
                cny_rate = self.preloaded_data.get('cny_rate', 0.0)
                brl_rate = self.preloaded_data.get('brl_rate', 0.0)
                gold_prices = self.preloaded_data.get('gold_prices', {})
                upbit_usdt = self.preloaded_data.get('upbit_usdt', 0.0)
                indices = self.preloaded_data.get('indices', {})
                source = self.preloaded_data.get('source', '-')
            else:
                # 1. 환율 조회
                usd, jpy, cny, brl, source = self.api_manager.fetch_exchange_rates()
                usd_rate = usd if usd is not None else 0.0
                jpy_rate = jpy if jpy is not None else 0.0
                cny_rate = cny if cny is not None else 0.0
                brl_rate = brl if brl is not None else 0.0

                # 2. 금 시세 및 코인 프리미엄 조회
                gold_prices = self.api_manager.get_detailed_gold_prices(usd_rate)
                upbit_usdt, _ = self.api_manager.get_upbit_price("USDT")
                
                # 3. 주요 지수 조회
                indices = self.api_manager.fetch_market_indices()

            # 3. 포트폴리오 데이터 조회 및 가공
            data = self.db_manager.fetch_portfolio(self.id_token)
            docs = data.get('documents', [])

            items, f_total, all_total, invest_total, quote_source = self.data_processor.process_portfolio_data(
                docs, usd_rate, jpy_rate, cny_rate, brl_rate, gold_prices, self.api_manager
            )

            result = {
                "usd_rate": usd_rate,
                "jpy_rate": jpy_rate,
                "cny_rate": cny_rate,
                "brl_rate": brl_rate,
                "gold_prices": gold_prices,
                "upbit_usdt": upbit_usdt,
                "indices": indices,
                "items": items,
                "f_total": f_total,
                "all_total": all_total,
                "invest_total": invest_total,
                "source": f"{source} & {quote_source}"
            }
            self.finished_data.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

class PortfolioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("자산 관리 시스템 1.6")
        self.setGeometry(10, 60, 1900, 850)

        self.db_manager = DBManager(config['projectId'], config['apiKey'])
        self.api_manager = APIManager()
        self.data_processor = DataProcessor()
        self.id_token = None
        self.user_refresh_token = None
        self.is_retrying = False
        self.usd_rate = None
        self.jpy_rate = None
        self.cny_rate = 0.0
        self.brl_rate = 0.0
        self.history_cache = []
        self.history_loaded = False
        self.selected_history_id = None
        self.current_items = []
        
        self.current_f_total = 0.0
        self.current_all_total = 0.0
        self.peak_f_asset = 0.0
        self.peak_date = "-"
        self.current_invest_total = 0.0
        self.preloaded_data = None

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        placeholder_label = QLabel("로그인 성공. UI를 구성합니다...")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(placeholder_label)

    def set_preloaded_data(self, data):
        self.preloaded_data = data

    def closeEvent(self, event):
        if hasattr(self, 'asset_view'):
            self.asset_view.save_settings()
        if hasattr(self, 'history_view'):
            self.history_view.save_settings()
        super().closeEvent(event)

    def handle_login(self, email, password):
        try:
            result = self.db_manager.login(email, password)
            self.id_token = result['idToken']
            self.user_refresh_token = result.get('refreshToken')
            self.init_ui()
            self.fetch_all()
            return True

        except Exception as e:
            print(f"로그인 예외 발생: {e}")
            msg = self.db_manager.get_friendly_error_message(str(e))
            QMessageBox.critical(self, "로그인 실패", msg)
            return False

    def init_ui(self):
        for i in reversed(range(self.main_layout.count())): 
            widget_to_remove = self.main_layout.itemAt(i).widget()
            if widget_to_remove:
                widget_to_remove.setParent(None)

        menu_widget = QWidget()
        menu_layout = QHBoxLayout(menu_widget)
        menu_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_asset_view = QPushButton("📊 자산 관리")
        self.btn_history_view = QPushButton("📜 히스토리")
        self.btn_chart_view = QPushButton("📈 차트")
        self.btn_analysis_view = QPushButton("📉 분석")
        btn_calculator = QPushButton("🧮 계산기")
        btn_refresh = QPushButton("🔄 데이터 새로고침")
        btn_export = QPushButton("📥 데이터 내보내기")
        
        self.status_label = QLabel("상태: 대기 중")
        self.source_label = QLabel("Source: -")
        self.source_label.setStyleSheet("color: #b0bec5; margin-right: 15px; font-size: 11px;")
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setFixedSize(25, 25)
        self.btn_settings.setStyleSheet("font-size: 15px; padding: 0px; background: transparent; border: none; color: #888;")

        menu_layout.addWidget(self.btn_asset_view)
        menu_layout.addWidget(self.btn_history_view)
        menu_layout.addWidget(self.btn_chart_view)
        menu_layout.addWidget(self.btn_analysis_view)
        menu_layout.addWidget(btn_calculator)
        
        menu_layout.addWidget(btn_refresh)
        menu_layout.addWidget(btn_export)
        menu_layout.addStretch()
        menu_layout.addWidget(self.source_label)
        menu_layout.addWidget(self.status_label)
        menu_layout.addWidget(self.btn_settings)

        self.main_layout.addWidget(menu_widget)

        self.dashboard_view = DashboardView()
        self.main_layout.addWidget(self.dashboard_view)
        
        self.stack = QStackedWidget()
        self.main_layout.addWidget(self.stack)
        
        self.asset_view = AssetView()
        self.history_view = HistoryView()
        self.chart_view = ChartView()
        self.analysis_view = AnalysisView()
        
        self.stack.addWidget(self.asset_view)
        self.stack.addWidget(self.history_view)
        self.stack.addWidget(self.chart_view)
        self.stack.addWidget(self.analysis_view)
        
        self.asset_view.save_requested.connect(self.handle_asset_save)
        self.asset_view.delete_requested.connect(self.handle_asset_delete)
        
        self.history_view.save_snapshot_requested.connect(self.push_history_to_firebase)
        self.history_view.delete_requested.connect(self.delete_history_from_firebase)

        self.btn_asset_view.clicked.connect(self.show_asset_view)
        self.btn_history_view.clicked.connect(self.show_history_view)
        self.btn_chart_view.clicked.connect(self.show_chart_view)
        self.btn_analysis_view.clicked.connect(self.show_analysis_view)
        btn_calculator.clicked.connect(self.show_calculator)
        btn_refresh.clicked.connect(self.fetch_all)
        btn_export.clicked.connect(self.export_data)
        self.btn_settings.clicked.connect(self.show_settings_dialog)

    def show_asset_view(self):
        self.stack.setCurrentWidget(self.asset_view)
        self.btn_asset_view.setStyleSheet("font-weight: bold; background-color: #1976D2; color: white;")
        self.btn_history_view.setStyleSheet("")
        self.btn_chart_view.setStyleSheet("")
        self.btn_analysis_view.setStyleSheet("")

    def show_history_view(self):
        self.stack.setCurrentWidget(self.history_view)
        self.btn_history_view.setStyleSheet("font-weight: bold; background-color: #607D8B; color: white;")
        self.btn_asset_view.setStyleSheet("")
        self.btn_chart_view.setStyleSheet("")
        self.btn_analysis_view.setStyleSheet("")
        
        if not self.history_loaded:
            self.fetch_history()

    def show_chart_view(self):
        self.stack.setCurrentWidget(self.chart_view)
        self.btn_chart_view.setStyleSheet("font-weight: bold; background-color: #9C27B0; color: white;")
        self.btn_asset_view.setStyleSheet("")
        self.btn_history_view.setStyleSheet("")
        self.btn_analysis_view.setStyleSheet("")
        
        if not self.history_loaded:
            self.fetch_history()
        self.chart_view.render_charts(self.history_cache, self.current_items)

    def show_analysis_view(self):
        self.stack.setCurrentWidget(self.analysis_view)
        self.btn_analysis_view.setStyleSheet("font-weight: bold; background-color: #E91E63; color: white;")
        self.btn_asset_view.setStyleSheet("")
        self.btn_history_view.setStyleSheet("")
        self.btn_chart_view.setStyleSheet("")
        
        if not self.history_loaded:
            self.fetch_history()
        
        # Render analysis with current history data
        self.analysis_view.render_analysis(self.history_cache, self.current_f_total)

    def show_calculator(self):
        gold_info = getattr(self, 'current_gold_info', {})
        
        # 포트폴리오에서 IAU, PAXG 현재가 찾기 (보유 중인 경우)
        iau_price = 0.0
        paxg_price = 0.0
        for item in self.current_items:
            if item['ticker'] == 'IAU' and item['qty'] > 0:
                iau_price = item['usd'] / item['qty']
            elif item['ticker'] == 'PAXG' and item['qty'] > 0:
                # 빗썸 등 원화 마켓 가정 (보유 자산의 KRW 평가액 / 수량)
                if item['krw'] > 0:
                    paxg_price = item['krw'] / item['qty']

        dlg = CalculatorDialog(self, self.usd_rate, gold_info, iau_price, paxg_price)
        dlg.exec()

    def show_settings_dialog(self):
        dlg = SettingsDialog(self, self.peak_f_asset)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_peak = dlg.get_value()
            self.update_peak_manually(new_peak)

    def update_peak_manually(self, new_val):
        if not self.id_token: return
        try:
            self.peak_f_asset = new_val
            self.peak_date, payload = self.data_processor.get_peak_update_payload(new_val, self.peak_date)
            self.db_manager.update_stats(self.id_token, payload)
            QMessageBox.information(self, "성공", "전고점이 수동으로 수정되었습니다.")
            self.fetch_all() # UI 및 MDD 재계산을 위해 데이터 새로고침
        except Exception as e:
            QMessageBox.critical(self, "오류", f"전고점 수정 실패: {e}")

    def delete_history_from_firebase(self, date_id):
        reply = QMessageBox.question(self, "삭제 확인", f"날짜 [{date_id}]의 기록을 삭제하시겠습니까?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self.db_manager.delete_history(self.id_token, date_id)

            self.history_cache = [h for h in self.history_cache if h['date'] != date_id]
            self.history_view.update_table(self.history_cache, self.current_f_total, self.current_all_total)
            
            self.selected_history_id = None
        except Exception as e:
            QMessageBox.critical(self, "오류", f"삭제 실패: {e}")

    def push_history_to_firebase(self, date_id, f_asset, t_asset, deposit, memo):
        payload = {
            "fields": {
                "financial_asset": {"doubleValue": f_asset},
                "total_asset": {"doubleValue": t_asset},
                "net_deposit": {"doubleValue": deposit},
                "memo": {"stringValue": memo}
            }
        }
        try:
            self.db_manager.save_history(self.id_token, date_id, payload)
            QMessageBox.information(self, "성공", "기록이 반영되었습니다.")
            
            self.history_cache = [h for h in self.history_cache if h['date'] != date_id]
            
            self.history_cache.append({
                "date": date_id,
                "f_asset": f_asset,
                "t_asset": t_asset,
                "deposit": deposit,
                "memo": memo
            })
            self.history_cache.sort(key=lambda x: x['date'])
            self.history_view.update_table(self.history_cache, self.current_f_total, self.current_all_total)
        except Exception as e:
            QMessageBox.critical(self, "실패", f"저장 오류: {e}")

    def display_history_from_cache(self):
        self.history_view.update_table(self.history_cache, self.current_f_total, self.current_all_total)

    def fetch_history(self, force_refresh=False):
        if self.history_loaded and not force_refresh:
            self.display_history_from_cache()
            return

        if not self.id_token: return

        try:
            data = self.db_manager.fetch_history(self.id_token)
            docs = data.get('documents', [])
            self.history_cache = []
            for doc in docs:
                date_id = doc['name'].split('/')[-1]
                f = doc.get('fields', {})
                
                def get_val(field):
                    v = f.get(field, {})
                    return float(v.get('doubleValue', v.get('integerValue', 0)))

                self.history_cache.append({
                    "date": date_id,
                    "f_asset": get_val('financial_asset'),
                    "t_asset": get_val('total_asset') or get_val('asset_value'),
                    "deposit": get_val('net_deposit'),
                    "memo": f.get('memo', {}).get('stringValue', '')
                })
            
            self.history_cache.sort(key=lambda x: x['date'])
            self.history_loaded = True
            self.history_view.update_table(self.history_cache, self.current_f_total, self.current_all_total)
            
        except Exception as e:
            print(f"히스토리 로드 오류: {e}")
        
    def export_data(self):
        if not self.history_loaded:
            self.fetch_history()

        g_info = getattr(self, 'current_gold_info', {})
        raw_summary = self.dashboard_view.get_summary_info(self.usd_rate, self.jpy_rate, self.cny_rate, self.brl_rate, g_info)
        
        # AI 분석을 위한 요약 데이터 가공
        summary_info = {}
        for k, v in raw_summary.items():
            clean_v = v.replace(",", "")
            if k == "금융자산합계":
                summary_info["* 금융자산합계"] = clean_v
            elif k == "총자산(부동산포함)":
                summary_info["* 총자산(부동산포함)"] = clean_v
            else:
                summary_info[k] = clean_v
        
        summary_info["rebalance_active_pool"] = f"{self.current_invest_total:.0f}"

        # 자산 상세 데이터 매칭을 위한 룩업 테이블
        items_lookup = {it['name']: it for it in self.current_items}

        data_list = []
        root = self.asset_view.sheet.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            row_data = {}
            for idx, col in enumerate(self.asset_view.columns):
                val = item.text(idx).replace(",", "")
                if col == "전일대비":
                    # %, ▲, ▼, + 기호 제거 및 소수점 환산 (예: 1.2%▲ -> 0.012)
                    is_down = "▼" in val
                    clean = val.replace("%", "").replace("▲", "").replace("▼", "").replace("+", "").strip()
                    try:
                        num = float(clean) / 100
                        val = f"{-num if is_down else num:.4f}"
                    except: val = "0"
                elif col == "목표비중":
                    # % 제거 및 소수점 환산 (예: 10.00% -> 0.1)
                    try:
                        val = f"{float(val.replace('%', '').strip()) / 100:.4f}"
                    except: val = "0"
                elif col == "단가":
                    # ₩, $, ¥ 기호 제거하여 숫자로 인식되게 함
                    val = val.replace("₩", "").replace("$", "").replace("¥", "").strip()
                row_data[col] = val
            
            # AI 분석용 데이터 추가
            asset_name = item.text(2)
            item_data = items_lookup.get(asset_name, {})
            
            # AI 분석용 카테고리 추가 (Active_Pool, Savings, None)
            main_cat = item.text(0)
            ai_cat = "None"
            if main_cat in ["투자", "단타"]:
                ai_cat = "Active_Pool"
            elif main_cat == "현금":
                ai_cat = "Savings"
            row_data["AI_Category"] = ai_cat
            
            # 가격 갱신 시점 및 시장 상태
            row_data["Price_Updated_At"] = item_data.get('updated_at', '-')
            row_data["Market_Status"] = item_data.get('market_status', '-')
            
            data_list.append(row_data)

        history_list = []
        h_root = self.history_view.history_sheet.invisibleRootItem()
        for i in range(h_root.childCount()):
            item = h_root.child(i)
            row_data = {col: item.text(idx).replace(",", "") for idx, col in enumerate(self.history_view.h_columns)}
            history_list.append(row_data)

        yearly_yield_list = []
        for row in self.history_view.yearly_yield_data:
            new_row = {k: v.replace(",", "") for k, v in row.items()}
            yearly_yield_list.append(new_row)

        analysis_metrics = getattr(self.analysis_view, 'last_metrics', None)

        # 자산 목록 컬럼에 AI 분석용 필드 추가
        export_asset_columns = self.asset_view.columns + ["AI_Category", "Price_Updated_At", "Market_Status"]

        DataExporter.export_csv(
            self,
            summary_info,
            export_asset_columns,
            data_list,
            self.history_view.h_columns,
            history_list,
            yearly_yield_list,
            analysis_metrics
        )

    def refresh_exchange_rates(self):
        try:
            usd, jpy, cny, brl, source = self.api_manager.fetch_exchange_rates()
            if usd is not None and jpy is not None and cny is not None and brl is not None:
                self.usd_rate = usd
                self.jpy_rate = jpy
                self.cny_rate = cny
                self.brl_rate = brl
                self.source_label.setText(f"Source: {source}")
            else:
                raise ValueError("모든 소스에서 환율 로드 실패")
        except Exception as e:
            print(f"환율 갱신 실패: {e}")
            self.dashboard_view.rate_label.setText("⚠️ 환율 로드 실패")
            # 기존 값이 없으면 0.0으로 초기화하여 계산 오류 방지
            if self.usd_rate is None or self.usd_rate == 0.0:
                self.usd_rate = 0.0
                self.jpy_rate = 0.0
                self.cny_rate = 0.0
                self.brl_rate = 0.0

    def check_and_update_peak(self, current_f_total):
        if not self.id_token: return

        if self.peak_f_asset == 0:
            try:
                data = self.db_manager.get_stats(self.id_token)
                fields = data.get('fields', {})
                val = fields.get('peak_financial_asset', {})
                self.peak_f_asset = float(val.get('doubleValue', val.get('integerValue', 0)))
                
                ts = fields.get('updated_at', {}).get('timestampValue', '')
                if ts:
                    self.peak_date = ts[:10].replace("-", "")
                else:
                    self.peak_date = "-"
            except Exception as e:
                print(f"Peak 로드 실패: {e}")

        is_new_peak, _ = self.data_processor.check_peak_update(
            current_f_total, self.peak_f_asset, self.peak_date, self.history_cache
        )

        if is_new_peak:
            self.peak_f_asset = current_f_total
            self.peak_date, payload = self.data_processor.get_peak_update_payload(current_f_total)
            try:
                self.db_manager.update_stats(self.id_token, payload)
            except Exception as e:
                print(f"Peak 저장 실패: {e}")

    def fetch_all(self, is_retry=False):
        self.is_retrying = is_retry
        self.status_label.setText("데이터 로딩 중... (잠시만 기다려주세요)")
        self.btn_asset_view.setEnabled(False)  # 중복 실행 방지
        
        self.loader = PortfolioLoader(self.api_manager, self.db_manager, self.data_processor, self.id_token, self.preloaded_data)
        self.loader.finished_data.connect(self.on_data_loaded)
        self.loader.error_occurred.connect(self.on_data_error)
        self.preloaded_data = None  # 한 번 사용 후 초기화 (새로고침 시에는 최신 데이터 조회)
        self.loader.start()

    def on_data_loaded(self, data):
        self.btn_asset_view.setEnabled(True)
        self.asset_view.sheet.clear()
        
        try:
            # 1. 데이터 언패킹 및 상태 업데이트
            self.usd_rate = data['usd_rate']
            self.jpy_rate = data['jpy_rate']
            self.cny_rate = data.get('cny_rate', 0.0)
            self.brl_rate = data.get('brl_rate', 0.0)
            self.current_gold_info = data['gold_prices']
            self.current_items = data['items']
            self.source_label.setText(f"Source: {data.get('source') or '-'}")
            
            f_total = data['f_total']
            all_total = data['all_total']
            invest_total = data['invest_total']

            if self.usd_rate == 0.0:
                self.status_label.setText("⚠️ 환율 로드 실패: 외화 자산 가치가 0으로 계산됩니다.")

            # 2. 대시보드 업데이트
            self.dashboard_view.update_market_indicators(
                self.usd_rate, self.jpy_rate, self.cny_rate, self.brl_rate, self.current_gold_info, data['upbit_usdt'], data.get('indices')
            )

            # 3. 자산 목록 UI 구성
            items = self.current_items
            for i in items:
                rebal_amt = 0
                if i['main'] in ["투자", "단타"] and i['target_ratio'] > 0:
                    target_val = invest_total * (i['target_ratio'] / 100)
                    rebal_amt = target_val - i['row_val']
                
                rebal_str = f"{rebal_amt:,.0f}" if rebal_amt != 0 else ""
                item = QTreeWidgetItem(self.asset_view.sheet)
                item.setText(0, i['main'])
                item.setText(1, i['sub'])
                item.setText(2, i['name'])
                item.setText(3, rebal_str)
                item.setText(4, f"{i['row_val']:,.0f}")
                item.setText(5, f"{i['usd']:,.2f}")
                item.setText(6, f"{i['jpy']:,.0f}")
                item.setText(7, f"{i['krw']:,.0f}")
                item.setText(8, f"{i['qty']:,.2f}")
                item.setText(9, i['ticker'])
                item.setText(10, f"{i['target_ratio']:.2f}%" if i['target_ratio'] > 0 else "")
                item.setText(11, i.get('diff_str', ''))
                item.setText(12, i.get('unit_price_str', ''))
                item.setText(13, i['note'])
                
                if rebal_amt < 0:
                    item.setForeground(3, QBrush(QColor("#FF6B6B")))
                elif rebal_amt > 0:
                    item.setForeground(3, QBrush(QColor("#4DABF7")))
                    font = item.font(3)
                    font.setBold(True)
                    item.setFont(3, font)

                if i.get('diff_color') == 'red':
                    item.setForeground(11, QBrush(QColor("#FF6B6B"))) # 전일대비 컬럼 색상
                elif i.get('diff_color') == 'blue':
                    item.setForeground(11, QBrush(QColor("#4DABF7"))) # 전일대비 컬럼 색상

                for col in [3, 4, 5, 6, 7, 8, 10, 11, 12]:
                    item.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                for col in [0, 1, 2, 9]:
                    item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

                if i['qty'] <= 0:
                    for col in range(self.asset_view.sheet.columnCount()):
                        item.setForeground(col, QBrush(QColor("gray")))

            self.current_f_total = f_total
            self.current_all_total = all_total
            self.current_invest_total = invest_total
            
            self.status_label.setText(f"상태: 갱신 완료 ({datetime.now().strftime('%H:%M:%S')})")
            
            if not self.history_loaded:
                self.fetch_history()
            elif self.history_loaded:
                self.fetch_history(force_refresh=True)
            
            # 수익률, 증감률 계산 (DataProcessor 위임)
            roi, growth = self.data_processor.calculate_metrics(f_total, all_total, self.history_cache)
            
            self.check_and_update_peak(f_total)
            
            # MDD 계산 (DataProcessor 위임)
            mdd_val, mdd_pct = self.data_processor.calculate_mdd(f_total, self.peak_f_asset, self.peak_date, self.history_cache)
            
            # 대시보드 자산 요약 업데이트
            self.dashboard_view.update_asset_summary(
                f_total, all_total, roi, growth, 
                self.peak_f_asset, self.peak_date, mdd_val, mdd_pct
            )
            
            # [최적화] 데이터 갱신 시 차트도 미리 렌더링 (탭 전환 시 딜레이 제거)
            self.chart_view.render_charts(self.history_cache, self.current_items)
            
            # [추가] 분석 데이터도 백그라운드에서 미리 계산 (내보내기 시 포함되도록)
            self.analysis_view.render_analysis(self.history_cache, self.current_f_total)
            
        except Exception as e:
            self.on_data_error(str(e))

    def try_refresh_token(self):
        if not self.user_refresh_token: return False
        try:
            # DBManager로 로직 위임
            self.id_token, new_refresh = self.db_manager.refresh_auth_token(self.user_refresh_token)
            if new_refresh:
                self.user_refresh_token = new_refresh
            print("토큰 갱신 성공")
            return True
        except Exception as e:
            print(f"토큰 갱신 실패: {e}")
            return False

    def on_data_error(self, error_msg):
        # 인증 오류 감지 (401 또는 authentication 관련 메시지)
        if ("authentication" in error_msg.lower() or "401" in error_msg) and not self.is_retrying:
            print("인증 오류 감지. 토큰 갱신 시도...")
            if self.try_refresh_token():
                self.fetch_all(is_retry=True)
                return

        self.btn_asset_view.setEnabled(True)
        self.status_label.setText("⚠️ 데이터 로드 실패")
        QMessageBox.critical(self, "오류", f"데이터 로드 실패: {error_msg}")
            
    def get_upbit_price(self, symbol):
        return self.api_manager.get_upbit_price(symbol)
    
    def get_detailed_gold_prices(self):
        return self.api_manager.get_detailed_gold_prices(self.usd_rate)

    def update_local_asset_ui(self, name, data_fields):
        main = data_fields["대분류"]["stringValue"]
        sub = data_fields["소분류"]["stringValue"]
        ticker = data_fields["티커"]["stringValue"]
        qty = float(data_fields["수량"]["doubleValue"])
        usd = float(data_fields["금액(달러)"]["doubleValue"])
        jpy = float(data_fields["금액(엔)"]["doubleValue"])
        krw = float(data_fields["금액(원)"]["doubleValue"])
        target_ratio = float(data_fields.get("목표비중", {}).get("doubleValue", 0))
        note = data_fields["비고"]["stringValue"]

        gold_info = getattr(self, 'current_gold_info', {})
        success, c_krw, c_usd, c_jpy, c_prev, updated_at, market_status = self.data_processor.calculate_asset_values(
            ticker, qty, note, gold_info, self.api_manager, sub, self.usd_rate or 0.0, self.jpy_rate or 0.0, self.cny_rate or 0.0, self.brl_rate
        )
        
        if success:
            krw, usd, jpy = c_krw, c_usd, c_jpy
        else:
            c_prev = 0.0

        row_val = (usd * (self.usd_rate or 0)) + (jpy * (self.jpy_rate or 0)) + krw
        
        rebal_amt = 0
        if main in ["투자", "단타"] and target_ratio > 0:
            rebal_amt = (self.current_invest_total * (target_ratio / 100)) - row_val
        
        rebal_str = f"{rebal_amt:,.0f}" if rebal_amt != 0 else ""

        unit_price_str, diff_str, diff_color = self.data_processor.get_price_display_info(
            ticker, qty, usd, jpy, krw, c_prev
        )

        target_item = None
        root = self.asset_view.sheet.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(2) == name:
                target_item = item
                break
        
        if not target_item:
            target_item = QTreeWidgetItem(self.asset_view.sheet)

        target_item.setText(0, main)
        target_item.setText(1, sub)
        target_item.setText(2, name)
        target_item.setText(3, rebal_str)
        target_item.setText(4, f"{row_val:,.0f}")
        target_item.setText(5, f"{usd:,.2f}")
        target_item.setText(6, f"{jpy:,.0f}")
        target_item.setText(7, f"{krw:,.0f}")
        target_item.setText(8, f"{qty:,.2f}")
        target_item.setText(9, ticker)
        target_item.setText(10, f"{target_ratio:.2f}%" if target_ratio > 0 else "")
        target_item.setText(11, diff_str)
        target_item.setText(12, unit_price_str)
        target_item.setText(13, note)

        # 색상 초기화 (기존 색상 제거)
        for col in range(self.asset_view.sheet.columnCount()):
            target_item.setData(col, Qt.ItemDataRole.ForegroundRole, None)

        if rebal_amt < 0:
            target_item.setForeground(3, QBrush(QColor("#FF6B6B")))
        elif rebal_amt > 0:
            target_item.setForeground(3, QBrush(QColor("#4DABF7")))
            font = target_item.font(3)
            font.setBold(True)
            target_item.setFont(3, font)

        if diff_color == 'red':
            target_item.setForeground(11, QBrush(QColor("#FF6B6B"))) # 전일대비 컬럼 색상
        elif diff_color == 'blue':
            target_item.setForeground(11, QBrush(QColor("#4DABF7"))) # 전일대비 컬럼 색상

        for col in [3, 4, 5, 6, 7, 8, 10, 11, 12]:
            target_item.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for col in [0, 1, 2, 9]:
            target_item.setTextAlignment(col, Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        if qty <= 0:
            for col in range(self.asset_view.sheet.columnCount()):
                target_item.setForeground(col, QBrush(QColor("gray")))

        self.recalculate_totals()

    def recalculate_totals(self):
        f_total, all_total, invest_total = 0.0, 0.0, 0.0
        
        root = self.asset_view.sheet.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            val = float(item.text(4).replace(",", ""))
            main_cat = item.text(0)
            
            all_total += val
            if main_cat != "부동산": f_total += val
            if main_cat in ["투자", "단타"]: invest_total += val
        
        self.current_f_total = f_total
        self.current_all_total = all_total
        self.current_invest_total = invest_total
        
        self.dashboard_view.update_totals_only(f_total, all_total)

    def handle_asset_save(self, name, input_data):
        if not name or not self.id_token: return
        
        try:
            data = {"fields": {
                "대분류": {"stringValue": input_data["대분류"]},
                "소분류": {"stringValue": input_data["소분류"]},
                "티커": {"stringValue": input_data["티커"].strip()},
                "수량": {"doubleValue": float(input_data["수량"] or 0)},
                "금액(달러)": {"doubleValue": float(input_data["금액(달러)"] or 0)},
                "금액(엔)": {"doubleValue": float(input_data["금액(엔)"] or 0)},
                "금액(원)": {"doubleValue": float(input_data["금액(원)"] or 0)},
                "목표비중": {"doubleValue": float(input_data["목표비중"] or 0)},
                "비고": {"stringValue": input_data["비고"]},
                "업데이트시간": {"timestampValue": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            }}
            
            self.db_manager.save_asset(self.id_token, name, data)
            self.update_local_asset_ui(name, data["fields"])
            QMessageBox.information(self, "완료", f"'{name}' 저장되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패: {e}")

    def handle_asset_delete(self, name):
        if not name: return        

        reply = QMessageBox.question(self, "삭제", f"'{name}'을(를) 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db_manager.delete_asset(self.id_token, name)
                root = self.asset_view.sheet.invisibleRootItem()
                for i in range(root.childCount()):
                    item = root.child(i)
                    if item.text(2) == name:
                        root.removeChild(item)
                        break
                self.recalculate_totals()
                QMessageBox.information(self, "삭제 완료", f"'{name}'이 삭제되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"삭제 실패: {e}")



def main():
    # [환경 설정] 사용 환경에 따라 아래 설정 중 하나를 선택하세요.
    
    # 1. 로컬 환경 (최고 성능): GPU 가속을 사용하고 DirectComposition 에러만 억제 시도
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--use-angle=d3d11 --disable-direct-composition"

    # 2. 문라이트/스트리밍 환경 (최고 안정성): 에러가 계속 발생하면 아래 주석을 해제하고 위 라인을 주석 처리하세요.
    # os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu --disable-direct-composition"
    
    app = QApplication(sys.argv)
    
    StyleManager.apply_theme(app)

    main_win = PortfolioApp()
    
    # 백그라운드 데이터 로딩 시작 (로그인 창과 병렬 실행)
    preloader = Preloader()
    preloader.finished_data.connect(main_win.set_preloaded_data)
    preloader.start()
    
    login_dialog = LoginDialog()
    
    while True:
        if login_dialog.exec() == QDialog.DialogCode.Accepted:
            email, password = login_dialog.get_credentials()
            if main_win.handle_login(email, password):
                main_win.show()
                break 
        else:
            sys.exit()
            
    sys.exit(app.exec())

if __name__ == "__main__":
    main()