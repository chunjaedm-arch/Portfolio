import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, 
    QFrame, QStackedWidget, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class AnalysisWorker(QThread):
    finished = pyqtSignal(object, object, object, dict)

    def __init__(self, history_data, current_f_asset=0.0):
        super().__init__()
        self.history_data = history_data
        self.current_f_asset = current_f_asset

    def run(self):
        if not self.history_data and self.current_f_asset <= 0:
            self.finished.emit(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {})
            return

        try:
            # 1. User Data Processing (Monthly)
            df_raw = pd.DataFrame(self.history_data)
            
            # [New] 현재 자산 상태 추가 (Live Data) -> 이번 달 데이터로 반영
            if self.current_f_asset > 0:
                new_row = {
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'f_asset': self.current_f_asset,
                    'deposit': 0, # 현재 시점의 추가 입금은 0으로 가정 (순수 평가액 변동 반영)
                    't_asset': 0,
                    'memo': 'Live'
                }
                if df_raw.empty:
                    df_raw = pd.DataFrame([new_row])
                else:
                    df_raw = pd.concat([df_raw, pd.DataFrame([new_row])], ignore_index=True)
            
            df_raw['date'] = pd.to_datetime(df_raw['date'])
            df_raw.set_index('date', inplace=True)
            df_raw.sort_index(inplace=True)

            # [Change] 월 단위 리샘플링 (Month End)
            # 자산: 월말 기준 마지막 기록 (없으면 전월 유지)
            # 입금: 해당 월의 총 입금액 합계
            df_user = df_raw.resample('ME').agg({
                'f_asset': 'last',
                'deposit': 'sum'
            })
            
            # 자산이 비어있는 달(기록 안 한 달)은 전월 자산으로 채움
            df_user['f_asset'] = df_user['f_asset'].ffill()
            
            # 데이터 시작 시점 이전의 NaN 제거 (첫 기록이 있는 달부터 시작)
            df_user = df_user.dropna(subset=['f_asset'])

            # 수익률 계산: (기말자산 - 순입고 - 기초자산) / 기초자산
            # 기초자산(prev_f)은 '전월 말 자산'
            df_user['prev_f'] = df_user['f_asset'].shift(1)
            df_user['return'] = 0.0
            
            # 첫 달은 수익률 0으로 시작 (전월 데이터가 없으므로)
            for i in range(1, len(df_user)):
                prev = df_user.iloc[i]['prev_f']
                curr = df_user.iloc[i]['f_asset']
                dep = df_user.iloc[i]['deposit']
                
                if prev > 0:
                    # 해당 월 수익률
                    # [Modified Dietz] 분모 = 기초 + (순입고 * 0.5)
                    denominator = prev + (dep * 0.5)
                    if denominator != 0:
                        ret = (curr - dep - prev) / denominator
                        df_user.iloc[i, df_user.columns.get_loc('return')] = ret
            
            # Cumulative Return (Start from 1.0)
            df_user['cum_return'] = (1 + df_user['return']).cumprod()
            
            # 2. Benchmark & Risk-Free Rate Fetching
            if not df_user.empty:
                start_date = df_user.index[0]
            else:
                start_date = datetime.now() # Fallback
            end_date = datetime.now()
            
            # SPY (Benchmark)
            spy = yf.Ticker("SPY")
            df_spy = spy.history(start=start_date, end=end_date, auto_adjust=True)

            # KOSPI (Benchmark 2) - FinanceDataReader
            try:
                df_kospi = fdr.DataReader('KS11', start_date, end_date)
            except Exception as e:
                print(f"KOSPI(FDR) Load Error: {e}")
                df_kospi = pd.DataFrame()
            
            # [Fallback] FDR 데이터가 없으면 yfinance로 재시도 (^KS11)
            if df_kospi.empty:
                try:
                    df_kospi = yf.Ticker("^KS11").history(start=start_date, end=end_date)
                except Exception as e:
                    print(f"KOSPI(YF) Load Error: {e}")
            
            # ^IRX (Risk-Free Rate, 13 Week Treasury Bill)
            irx = yf.Ticker("^IRX")
            df_irx = irx.history(start=start_date, end=end_date)
            
            # [Fix] 타임존 불일치 해결 (Aware -> Naive 변환)
            if not df_spy.empty:
                df_spy.index = df_spy.index.tz_localize(None)
            if not df_kospi.empty and df_kospi.index.tz is not None:
                df_kospi.index = df_kospi.index.tz_localize(None)
            if not df_irx.empty:
                df_irx.index = df_irx.index.tz_localize(None)
            
            # 3. Risk-Free Rate Mapping (Dynamic)
            # IRX 데이터 전처리 (연이율 % -> 소수점)
            # 결측치는 앞의 값으로 채움 (ffill), 없으면 4.5% 가정
            # 월 단위 분석이므로 IRX도 월 평균(Mean) 또는 월말(Last) 사용. 여기선 월 평균 사용.
            df_irx_monthly = df_irx['Close'].resample('ME').mean()
            irx_series = df_irx_monthly.ffill() / 100
            
            if irx_series.empty:
                irx_series = pd.Series(0.045, index=df_user.index)

            # (1) User Data에 Rf 매핑
            # 월간 데이터이므로 reindex로 매핑
            df_user['irx_annual'] = irx_series.reindex(df_user.index).ffill().fillna(0.045)
            
            # 월간 무위험 수익률 = 연이율 / 12
            df_user['rf_period'] = df_user['irx_annual'] / 12
            
            # 초과 수익률 (Excess Return) = 내 수익률 - 무위험 수익률
            df_user['excess_return'] = df_user['return'] - df_user['rf_period']

            # (2) SPY Data에 Rf 매핑
            if not df_spy.empty:
                # SPY 월간 데이터로 변환 (매월 15일 기준: 15일 이하 마지막 거래일)
                spy_close = df_spy['Close']
                spy_15 = spy_close[spy_close.index.day <= 15]
                df_spy_monthly = spy_15.groupby(spy_15.index.to_period('M')).last().to_frame()
                df_spy_monthly.index = df_spy_monthly.index.to_timestamp() + pd.offsets.Day(14)

                df_spy_monthly['return'] = df_spy_monthly['Close'].pct_change().fillna(0)
                df_spy_monthly['cum_return'] = (1 + df_spy_monthly['return']).cumprod()

                # IRX 매핑 (SPY 인덱스는 15일 기준 → nearest로 동일 월 IRX 매핑)
                df_spy_monthly['irx_annual'] = irx_series.reindex(df_spy_monthly.index, method='nearest').fillna(0.045)
                df_spy_monthly['rf_period'] = df_spy_monthly['irx_annual'] / 12
                df_spy_monthly['excess_return'] = df_spy_monthly['return'] - df_spy_monthly['rf_period']

                # 변수명 교체 (이후 로직 호환성)
                df_spy = df_spy_monthly

            # (3) KOSPI Data에 Rf 매핑
            if not df_kospi.empty:
                # KOSPI 월간 데이터 변환 (매월 15일 기준: 15일 이하 마지막 거래일)
                kospi_close = df_kospi['Close']
                kospi_15 = kospi_close[kospi_close.index.day <= 15]
                df_kospi_monthly = kospi_15.groupby(kospi_15.index.to_period('M')).last().to_frame()
                df_kospi_monthly.index = df_kospi_monthly.index.to_timestamp() + pd.offsets.Day(14)

                df_kospi_monthly['return'] = df_kospi_monthly['Close'].pct_change().fillna(0)
                df_kospi_monthly['cum_return'] = (1 + df_kospi_monthly['return']).cumprod()

                df_kospi_monthly['irx_annual'] = irx_series.reindex(df_kospi_monthly.index, method='nearest').fillna(0.045)
                df_kospi_monthly['rf_period'] = df_kospi_monthly['irx_annual'] / 12
                df_kospi_monthly['excess_return'] = df_kospi_monthly['return'] - df_kospi_monthly['rf_period']
                df_kospi = df_kospi_monthly
            
            # 3. Metrics Calculation (Matrix: All + 6M intervals up to 5Y)
            periods_map = {
                'All': 0,
                '6M': 6,
                '1Y': 12, '1.5Y': 18,
                '2Y': 24, '2.5Y': 30,
                '3Y': 36, '3.5Y': 42,
                '4Y': 48, '4.5Y': 54,
                '5Y': 60
            }
            matrix = {}

            # 지표 계산 헬퍼 함수
            def calc_metrics(df, freq=12):
                if df.empty: return {}
                
                # CAGR
                # [Change] 월간 데이터 개수 기반으로 기간 산정 (날짜 차이로 계산 시 오차 발생 가능)
                years = len(df) / 12
                if years <= 0: return {}
                total_ret = (1 + df['return']).prod()
                
                if years < 1:
                    cagr = total_ret - 1
                else:
                    cagr = (total_ret ** (1/years)) - 1

                # MDD
                cum = (1 + df['return']).cumprod()
                dd = cum / cum.cummax() - 1
                mdd = dd.min()

                # Sharpe
                mean_ex = df['excess_return'].mean() * freq
                std_ex = df['excess_return'].std() * np.sqrt(freq)
                sharpe = mean_ex / std_ex if (std_ex != 0 and not np.isnan(std_ex)) else 0.0

                # Sortino
                downside = df[df['excess_return'] < 0]['excess_return']
                down_dev = 0.0
                if len(downside) > 0:
                    down_dev = np.sqrt((downside**2).sum()/len(df)) * np.sqrt(freq)

                if down_dev > 0:
                    sortino = mean_ex / down_dev
                else: # 하방 편차(downside deviation)가 없는 경우
                    sortino = 99.9 if mean_ex > 0 else 0.0

                # Rf Avg
                rf = df['irx_annual'].mean() if 'irx_annual' in df.columns else 0.045

                return {'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe, 'sortino': sortino, 'rf_avg': rf}

            for p_name, months in periods_map.items():
                if p_name == 'All':
                    # 전체 기간: 기준점(첫 행, 수익률 0)을 제외한 실제 수익률 발생 구간만 사용
                    sub_user = df_user.iloc[1:] if len(df_user) > 1 else pd.DataFrame()
                else:
                    # 고정 기간: 최근 N개월의 수익률 데이터만 추출 (tail 사용)
                    # df_user에는 기준점(수익률 0)이 포함되어 있으므로, len > months 여야 N개월 수익률 계산 가능
                    if len(df_user) > months:
                        sub_user = df_user.tail(months)
                    else:
                        matrix[p_name] = {'user': None, 'spy': None}
                        continue
                
                if sub_user.empty:
                    matrix[p_name] = {'user': None, 'spy': None}
                    continue

                start_dt = sub_user.index[0]

                # 벤치마크 데이터 기간 동기화 (월 기준 비교: 포트 월말 vs 벤치마크 15일 인덱스 불일치 방지)
                start_period = start_dt.to_period('M')
                sub_spy = df_spy[df_spy.index.to_period('M') >= start_period] if not df_spy.empty else pd.DataFrame()
                sub_kospi = df_kospi[df_kospi.index.to_period('M') >= start_period] if not df_kospi.empty else pd.DataFrame()

                m_user = calc_metrics(sub_user)
                m_spy = calc_metrics(sub_spy)
                m_kospi = calc_metrics(sub_kospi)
                
                matrix[p_name] = {'user': m_user, 'spy': m_spy, 'kospi': m_kospi}

            # UI용 기본 지표 (All 기준)
            all_u = matrix['All']['user'] or {}
            all_s = matrix['All']['spy'] or {}
            all_k = matrix['All'].get('kospi') or {}

            metrics = {
                'cagr_user': all_u.get('cagr', 0), 'cagr_spy': all_s.get('cagr', 0),
                'cagr_kospi': all_k.get('cagr', 0),
                'mdd_user': all_u.get('mdd', 0), 'mdd_spy': all_s.get('mdd', 0),
                'mdd_kospi': all_k.get('mdd', 0),
                'sharpe_user': all_u.get('sharpe', 0), 'sharpe_spy': all_s.get('sharpe', 0),
                'sharpe_kospi': all_k.get('sharpe', 0),
                'sortino_user': all_u.get('sortino', 0), 'sortino_spy': all_s.get('sortino', 0),
                'sortino_kospi': all_k.get('sortino', 0),
                'rf_avg': all_u.get('rf_avg', 0),
                'matrix': matrix
            }

            # Attach DD to dataframes for plotting
            cum_all = (1 + df_user['return']).cumprod()
            df_user['dd'] = cum_all / cum_all.cummax() - 1
            
            if not df_spy.empty:
                cum_spy = (1 + df_spy['return']).cumprod()
                df_spy['dd'] = cum_spy / cum_spy.cummax() - 1

            if not df_kospi.empty:
                cum_kospi = (1 + df_kospi['return']).cumprod()
                df_kospi['dd'] = cum_kospi / cum_kospi.cummax() - 1

            self.finished.emit(df_user, df_spy, df_kospi, metrics)

        except Exception as e:
            print(f"Analysis Error: {e}")
            self.finished.emit(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {})

class AnalysisView(QWidget):
    def __init__(self):
        super().__init__()
        self.last_metrics = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 0. Info Label (분석 기준 명시)
        lbl_info = QLabel("※ 분석 기준: 금융자산 (현금 포함, 부동산 제외) | 1년 미만 기간은 단순 누적 수익률로 표시됩니다.")
        lbl_info.setStyleSheet("color: #888; font-size: 12px; margin-bottom: 0px;")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(lbl_info)

        # --- Navigation Buttons ---
        nav_layout = QHBoxLayout()
        self.btn_dashboard = QPushButton("📊 대시보드")
        self.btn_matrix = QPushButton("📋 상세 매트릭스")
        
        for btn in [self.btn_dashboard, self.btn_matrix]:
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #353535; color: #aaa; border: none; border-radius: 4px; font-weight: bold; padding: 0 15px;
                }
                QPushButton:checked {
                    background-color: #1976D2; color: white;
                }
                QPushButton:hover {
                    background-color: #454545;
                }
            """)
        
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.clicked.connect(lambda: self.switch_page(0))
        self.btn_matrix.clicked.connect(lambda: self.switch_page(1))
        
        nav_layout.addWidget(self.btn_dashboard)
        nav_layout.addWidget(self.btn_matrix)
        nav_layout.addStretch()
        layout.addLayout(nav_layout)

        # --- Stacked Widget ---
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Page 1: Dashboard
        self.page_dashboard = QWidget()
        self.init_dashboard_ui()
        self.stack.addWidget(self.page_dashboard)

        # Page 2: Matrix
        self.page_matrix = QWidget()
        self.init_matrix_ui()
        self.stack.addWidget(self.page_matrix)

    def init_dashboard_ui(self):
        layout = QVBoxLayout(self.page_dashboard)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # 1. Summary Section (Top)
        self.summary_group = QGroupBox("📊 핵심 지표 분석")
        self.summary_group.setStyleSheet("""
            QGroupBox { 
                font-weight: bold; color: white; border: 1px solid #555; border-radius: 5px; margin-top: 10px; 
            } 
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
        self.summary_group.setFixedHeight(130) # 높이 증가 (KOSPI 라벨 추가 공간 확보)
        sum_layout = QHBoxLayout(self.summary_group)
        sum_layout.setSpacing(20)

        self.card_cagr = self.create_metric_card("CAGR (연평균/누적 수익률)")
        self.card_mdd = self.create_metric_card("MDD (최대 낙폭)")
        self.card_sharpe = self.create_metric_card("Sharpe Ratio (샤프 지수)")
        self.card_sortino = self.create_metric_card("Sortino Ratio (소르티노 지수)")
        self.card_rf = self.create_metric_card("Risk-Free Rate (무위험 수익률)")

        sum_layout.addWidget(self.card_cagr)
        sum_layout.addWidget(self.card_mdd)
        sum_layout.addWidget(self.card_sharpe)
        sum_layout.addWidget(self.card_sortino)
        sum_layout.addWidget(self.card_rf)

        layout.addWidget(self.summary_group)

        # 2. Charts Section (Middle & Bottom)
        self.chart_view = QWebEngineView()
        self.chart_view.page().setBackgroundColor(Qt.GlobalColor.transparent)
        layout.addWidget(self.chart_view)

    def init_matrix_ui(self):
        layout = QVBoxLayout(self.page_matrix)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.matrix_table = QTableWidget()
        self.matrix_table.setAlternatingRowColors(True)
        self.matrix_table.setStyleSheet("""
            QTableWidget {
                background-color: #2b2b2b;
                alternate-background-color: #353535;
                color: #e0e0e0;
                gridline-color: #404040;
                border: 1px solid #555;
            }
            QHeaderView::section {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #555;
                padding: 4px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTableWidget::item:selected {
                background-color: #1976D2;
            }
        """)
        layout.addWidget(self.matrix_table)

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_dashboard.setChecked(index == 0)
        self.btn_matrix.setChecked(index == 1)

    def create_metric_card(self, title):
        frame = QFrame()
        frame.setStyleSheet("background-color: #353535; border-radius: 8px;")
        l = QVBoxLayout(frame)
        l.setContentsMargins(15, 10, 15, 10)
        l.setSpacing(5)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #bbb; font-size: 12px;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_value = QLabel("-")
        lbl_value.setStyleSheet("color: #fff; font-size: 18px; font-weight: bold;")
        lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_sub = QLabel("vs SPY: -")
        lbl_sub.setStyleSheet("color: #888; font-size: 11px;")
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_sub2 = QLabel("vs KOSPI: -")
        lbl_sub2.setStyleSheet("color: #888; font-size: 11px;")
        lbl_sub2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        l.addWidget(lbl_title)
        l.addWidget(lbl_value)
        l.addWidget(lbl_sub)
        l.addWidget(lbl_sub2)
        
        # Store references to labels for updates
        frame.lbl_value = lbl_value
        frame.lbl_sub = lbl_sub
        frame.lbl_sub2 = lbl_sub2
        return frame

    def update_card(self, card, user_val, spy_val, kospi_val, is_pct=True, higher_is_better=True):
        fmt = "{:+.2f}%" if is_pct else "{:.2f}"
        
        u_text = fmt.format(user_val * 100 if is_pct else user_val)
        s_text = fmt.format(spy_val * 100 if is_pct else spy_val)
        k_text = fmt.format(kospi_val * 100 if is_pct else kospi_val)
        
        card.lbl_value.setText(u_text)
        card.lbl_sub.setText(f"vs SPY: {s_text}")
        card.lbl_sub2.setText(f"vs KOSPI: {k_text}")
        
        # Color coding
        color = "#ffffff"
        if higher_is_better:
            if user_val > spy_val: color = "#4DABF7" # Blue
            elif user_val < spy_val: color = "#FF6B6B" # Red
        else: # Lower is better (e.g. MDD magnitude? usually MDD is negative, so closer to 0 is better)
            if user_val > spy_val: color = "#4DABF7"
            elif user_val < spy_val: color = "#FF6B6B"
            
        card.lbl_value.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")

    def render_analysis(self, history_data, current_f_asset=0.0):
        self.chart_view.setHtml('<body style="background-color: #2b2b2b; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100%;"><h3>데이터 분석 중...</h3></body>')
        
        self.worker = AnalysisWorker(history_data, current_f_asset)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.start()

    def on_analysis_finished(self, df_user, df_spy, df_kospi, metrics):
        self.last_metrics = metrics
        
        if df_user.empty:
            self.chart_view.setHtml('<body style="background-color: #2b2b2b; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100%;"><h3>데이터가 부족합니다.</h3></body>')
            return

        # Update Cards
        self.update_card(self.card_cagr, metrics.get('cagr_user', 0), metrics.get('cagr_spy', 0), metrics.get('cagr_kospi', 0), is_pct=True)
        self.update_card(self.card_mdd, metrics.get('mdd_user', 0), metrics.get('mdd_spy', 0), metrics.get('mdd_kospi', 0), is_pct=True)
        self.update_card(self.card_sharpe, metrics.get('sharpe_user', 0), metrics.get('sharpe_spy', 0), metrics.get('sharpe_kospi', 0), is_pct=False)
        self.update_card(self.card_sortino, metrics.get('sortino_user', 0), metrics.get('sortino_spy', 0), metrics.get('sortino_kospi', 0), is_pct=False)
        
        # Update Matrix Table
        self.update_matrix_table(metrics.get('matrix', {}))

        # 무위험 수익률 카드 업데이트 (별도 처리)
        rf_val = metrics.get('rf_avg', 0)
        self.card_rf.lbl_value.setText(f"{rf_val * 100:.2f}%")
        self.card_rf.lbl_sub.setText("기간 평균")
        self.card_rf.lbl_sub2.setText("") # KOSPI 라벨 비움
        self.card_rf.lbl_value.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold;")

        # Draw Charts
        fig = make_subplots(
            rows=2, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.1, 
            row_heights=[0.65, 0.35],
            subplot_titles=("📈 누적 수익률 (Cumulative Return)", "🌊 낙폭 (Drawdown)")
        )

        # 1. Cumulative Return
        # Convert to percentage for display
        user_cum_pct = (df_user['cum_return'] - 1) * 100
        
        fig.add_trace(go.Scatter(
            x=df_user.index, y=user_cum_pct,
            name="내 포트폴리오",
            line=dict(color='#4DABF7', width=3),
            hovertemplate='%{y:.2f}%'
        ), row=1, col=1)

        if not df_spy.empty:
            spy_cum_pct = (df_spy['cum_return'] - 1) * 100
            fig.add_trace(go.Scatter(
                x=df_spy.index, y=spy_cum_pct,
                name="S&P 500 (SPY)",
                line=dict(color='#9E9E9E', width=1.5, dash='dot'),
                hovertemplate='%{y:.2f}%'
            ), row=1, col=1)
            
        if not df_kospi.empty:
            kospi_cum_pct = (df_kospi['cum_return'] - 1) * 100
            fig.add_trace(go.Scatter(
                x=df_kospi.index, y=kospi_cum_pct,
                name="KOSPI",
                line=dict(color='#FF9800', width=1.5, dash='dot'),
                hovertemplate='%{y:.2f}%'
            ), row=1, col=1)

        # 2. Drawdown
        user_dd_pct = df_user['dd'] * 100
        fig.add_trace(go.Scatter(
            x=df_user.index, y=user_dd_pct,
            name="내 DD",
            fill='tozeroy',
            line=dict(color='#FF6B6B', width=1),
            hovertemplate='%{y:.2f}%'
        ), row=2, col=1)

        if not df_spy.empty:
            spy_dd_pct = df_spy['dd'] * 100
            fig.add_trace(go.Scatter(
                x=df_spy.index, y=spy_dd_pct,
                name="SPY DD",
                line=dict(color='#9E9E9E', width=1, dash='dot'),
                hovertemplate='%{y:.2f}%'
            ), row=2, col=1)
            
        if not df_kospi.empty:
            kospi_dd_pct = df_kospi['dd'] * 100
            fig.add_trace(go.Scatter(
                x=df_kospi.index, y=kospi_dd_pct,
                name="KOSPI DD",
                line=dict(color='#FF9800', width=1, dash='dot'),
                hovertemplate='%{y:.2f}%'
            ), row=2, col=1)

        # Layout
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color="#6e6917",
            margin=dict(t=40, b=20, l=20, r=20),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hoverlabel=dict(
                bgcolor="#000000",       # 툴팁 배경색: 검정
                font_size=13,            # 글자 크기 (선택사항)
                font_color="#D4AF37",    # 툴팁 글자색: 황금색
                bordercolor="#D4AF37"
            )
        )
        
        fig.update_yaxes(title_text="수익률 (%)", row=1, col=1, gridcolor='#404040', zerolinecolor='#666')
        fig.update_yaxes(title_text="낙폭 (%)", row=2, col=1, gridcolor='#404040', zerolinecolor='#666')
        fig.update_xaxes(gridcolor='#404040')

        html = fig.to_html(include_plotlyjs='cdn', full_html=True)
        html = html.replace('<body>', '<body style="background-color: #2b2b2b; margin: 0;">')
        self.chart_view.setHtml(html)

    def update_matrix_table(self, matrix):
        if not matrix: return
        
        periods = ['All', '6M', '1Y', '1.5Y', '2Y', '2.5Y', '3Y', '3.5Y', '4Y', '4.5Y', '5Y']
        headers = ["지표 (Metric)", "전체 (All)", "최근 6개월", "최근 1년", "최근 1.5년", "최근 2년", "최근 2.5년", "최근 3년", "최근 3.5년", "최근 4년", "최근 4.5년", "최근 5년"]
        
        rows_def = [
            ("CAGR (내 포트)", 'cagr', 'user', True),
            ("CAGR (SPY)", 'cagr', 'spy', True),
            ("CAGR (KOSPI)", 'cagr', 'kospi', True),
            ("MDD (내 포트)", 'mdd', 'user', True),
            ("MDD (SPY)", 'mdd', 'spy', True),
            ("MDD (KOSPI)", 'mdd', 'kospi', True),
            ("Sharpe Ratio (내 포트)", 'sharpe', 'user', False),
            ("Sharpe Ratio (SPY)", 'sharpe', 'spy', False),
            ("Sharpe Ratio (KOSPI)", 'sharpe', 'kospi', False),
            ("Sortino Ratio (내 포트)", 'sortino', 'user', False),
            ("Sortino Ratio (SPY)", 'sortino', 'spy', False),
            ("Sortino Ratio (KOSPI)", 'sortino', 'kospi', False),
            ("Risk-Free Rate (^IRX)", 'rf_avg', 'user', True),
        ]

        self.matrix_table.setRowCount(len(rows_def))
        self.matrix_table.setColumnCount(len(headers))
        self.matrix_table.setHorizontalHeaderLabels(headers)
        
        for r_idx, (label, metric_key, source, is_pct) in enumerate(rows_def):
            # Header Column
            item_head = QTableWidgetItem(label)
            item_head.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.matrix_table.setItem(r_idx, 0, item_head)
            
            for c_idx, period in enumerate(periods):
                val_str = "-"
                if period in matrix:
                    data = matrix[period].get(source)
                    if data:
                        val = data.get(metric_key)
                        if val is not None:
                            if is_pct:
                                val_str = f"{val*100:.2f}%"
                            else:
                                val_str = f"{val:.2f}"
                
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.matrix_table.setItem(r_idx, c_idx + 1, item)

        self.matrix_table.resizeColumnsToContents()
