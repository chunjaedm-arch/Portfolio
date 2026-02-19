import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QLabel, QTreeWidget, QTreeWidgetItem, QPushButton, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWebEngineWidgets import QWebEngineView

class ChartView(QWidget):
    def __init__(self):
        super().__init__()
        self.last_items = None
        self.last_history = None
        self.last_re_val = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)
        
        self.alloc_panel = QWidget()
        self.alloc_layout = QVBoxLayout(self.alloc_panel)
        self.splitter.addWidget(self.alloc_panel)
        
        self.alloc_view = QWebEngineView()
        self.alloc_layout.addWidget(self.alloc_view)
        
        self.chart_container = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_container)
        self.splitter.addWidget(self.chart_container)
        
        self.chart_view_widget = QWebEngineView()
        self.chart_layout.addWidget(self.chart_view_widget)
        
        self.splitter.setSizes([650, 1200])

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def render_charts(self, history_cache, current_assets_items):
        real_estate_val = sum(item['row_val'] for item in current_assets_items if item['main'] == '부동산') if current_assets_items else 0

        # 데이터가 변경되지 않았으면 리렌더링 방지 (최적화)
        if (self.last_items is current_assets_items and 
            self.last_history is history_cache and 
            self.last_re_val == real_estate_val):
            return

        self.last_items = current_assets_items
        self.last_history = history_cache
        self.last_re_val = real_estate_val

        self.draw_alloc_panel(current_assets_items)
        self.draw_right_chart(history_cache, real_estate_val)

    def draw_alloc_panel(self, items):
        if not items:
            self.alloc_view.setHtml('<body style="background-color: #2b2b2b; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100%;"><h3>자산 데이터가 없습니다.</h3></body>')
            return

        df = pd.DataFrame(items)
        
        df['name'] = df['name'].fillna(df['main'])
        
        df['label'] = df.apply(lambda x: x['ticker'] if x['ticker'] and x['ticker'].strip() else x['name'], axis=1)

        color_map = {'부동산': '#228B22', '투자': '#1E90FF', '현금': '#FFD700', '단타': '#FF4500'}

        labels = []
        parents = []
        values = []
        customdata = []
        colors = []

        for main_cat, group in df.groupby('main'):
            labels.append(main_cat)
            parents.append("")
            values.append(group['row_val'].sum())
            customdata.append(main_cat)
            colors.append(color_map.get(main_cat, 'grey'))

        for _, row in df.iterrows():
            labels.append(row['label'])
            parents.append(row['main'])
            values.append(row['row_val'])
            customdata.append(row['name'])
            colors.append(color_map.get(row['main'], 'grey'))

        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=parents,
            values=values,
            customdata=customdata,
            marker_colors=colors,
            branchvalues='total'
        ))
        
        fig.update_traces(
            marker=dict(line=dict(width=1, color='#2b2b2b')),
            textinfo="label+percent entry", 
            textposition="middle center",
            hovertemplate="<b>%{customdata}</b><br>%{value:,.0f}원<br>%{percentRoot:.1%}<extra></extra>",
            hoverlabel=dict(font_size=13, font_family="Malgun Gothic", align="left")
        )

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color="#e0e0e0",
            uniformtext=dict(minsize=8, mode='hide'),
            margin=dict(t=30, b=10, l=10, r=10)
        )

        html = fig.to_html(include_plotlyjs='cdn', full_html=True)
        html = html.replace('<body>', '<body style="background-color: #2b2b2b; margin: 0;">')
        self.alloc_view.setHtml(html)

    def draw_right_chart(self, history_cache, real_estate_val=0):
        if not history_cache:
            self.chart_view_widget.setHtml('<body style="background-color: #2b2b2b; color: #e0e0e0; display: flex; justify-content: center; align-items: center; height: 100%;"><h3>히스토리 데이터가 없습니다.</h3></body>')
            return

        df = pd.DataFrame(history_cache)
        
        if not df.empty:
            try:
                last_row = df.iloc[-1]
                last_date = pd.to_datetime(last_row['date'])
                current_f = float(last_row['f_asset'])
                
                target_date = pd.Timestamp("2037-01-15")
                future_data = []
                
                while True:
                    last_date = last_date + pd.DateOffset(months=1)
                    last_date = last_date.replace(day=15)
                    if last_date > target_date:
                        break
                    
                    next_f = current_f * 1.008 + 1600000
                    next_t = next_f + real_estate_val
                    
                    future_data.append({
                        "date": last_date.strftime("%Y-%m-%d"),
                        "f_asset": next_f,
                        "t_asset": next_t,
                        "deposit": 0,
                        "memo": "예측"
                    })
                    current_f = next_f
                
                if future_data:
                    df = pd.concat([df, pd.DataFrame(future_data)], ignore_index=True)
            except Exception as e:
                print(f"예측 데이터 생성 중 오류: {e}")
        
        df['prev_f'] = df['f_asset'].shift(1).fillna(0)
        df['prev_t'] = df['t_asset'].shift(1).fillna(0)
        
        df['profit'] = df.apply(lambda row: (row['f_asset'] - row['prev_f'] - row['deposit']) if row['prev_f'] > 0 else 0, axis=1)
        
        df['total_diff'] = df['t_asset'] - df['prev_t']
        df.loc[df['prev_t'] == 0, 'total_diff'] = 0
        
        if 'memo' in df.columns:
            df.loc[df['memo'] == '예측', ['deposit', 'profit', 'total_diff']] = None

        df['total_diff_m'] = df['total_diff'] / 1000000
        df['deposit_m'] = df['deposit'] / 1000000
        df['profit_m'] = df['profit'] / 1000000
        df['t_asset_100m'] = df['t_asset'] / 100000000

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        colors = ['#EF5350' if v >= 0 else '#42A5F5' for v in df['total_diff']]
        fig.add_trace(go.Bar(
            x=df['date'], 
            y=df['total_diff_m'], 
            name='전월대비 증감', 
            marker=dict(color=colors,line=dict(width=0)), 
            customdata=df['total_diff'],
            hovertemplate='%{x}<br>증감: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=df['date'], 
            y=df['deposit_m'], 
            name='순입고', 
            mode='lines', 
            line=dict(color='#FFD54F', width=1),
            customdata=df['deposit'],
            hovertemplate='%{x}<br>순입고: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=df['date'], 
            y=df['profit_m'], 
            name='투자손익', 
            mode='lines', 
            line=dict(color="#3085DB", width=1),
            customdata=df['profit'],
            hovertemplate='%{x}<br>투자손익: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
        ), secondary_y=False)

        fig.add_trace(go.Scatter(
            x=df['date'], 
            y=df['t_asset_100m'], 
            name='총자산', 
            mode='lines', 
            line=dict(color='#69F0AE'),
            customdata=df['t_asset'],
            hovertemplate='%{x}<br>총자산: %{customdata:,.0f}원<br>(%{y:,.2f}억)<extra></extra>'
        ), secondary_y=True)

        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color="#e0e0e0",
            xaxis=dict(
                showgrid=True, gridcolor='#404040', tickmode='linear', dtick="M12", tickformat="%y.%m"
            ),
            yaxis=dict(
                showgrid=True, gridcolor='#404040', title='증감액 / 손익 (백만)', tickformat=',.0f',
                zeroline=True, zerolinecolor='#666666', zerolinewidth=1,
                range=[-3.3, 8]
            ),
            yaxis2=dict(
                showgrid=False, title='총자산 (억)', tickformat=',.1f',
                range=[0, 10]
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40, b=20, l=20, r=20)
        )

        html = fig.to_html(include_plotlyjs='cdn', full_html=True)
        html = html.replace('<body>', '<body style="background-color: #2b2b2b; margin: 0;">')
        self.chart_view_widget.setHtml(html)
