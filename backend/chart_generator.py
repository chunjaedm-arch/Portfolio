"""view_chart.py의 Plotly 차트 생성 로직 (PyQt 의존성 제거)"""
from __future__ import annotations

import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime


# ─── 자산 배분 트리맵 ──────────────────────────────────────────
def _build_alloc_fig(items: list) -> go.Figure | None:
    if not items:
        return None

    df = pd.DataFrame(items)
    df['label'] = df.apply(
        lambda x: x['ticker'] if x.get('ticker', '').strip() else x['name'], axis=1
    )
    color_map = {'부동산': '#228B22', '투자': '#1E90FF', '현금': '#FFD700', '단타': '#FF4500'}

    labels, parents, values, customdata, colors = [], [], [], [], []
    for main_cat, group in df.groupby('main'):
        labels.append(main_cat); parents.append("")
        values.append(group['row_val'].sum()); customdata.append(main_cat)
        colors.append(color_map.get(main_cat, 'grey'))
    for _, row in df.iterrows():
        labels.append(row['label']); parents.append(row['main'])
        values.append(row['row_val']); customdata.append(row['name'])
        colors.append(color_map.get(row['main'], 'grey'))

    fig = go.Figure(go.Treemap(
        labels=labels, parents=parents, values=values, customdata=customdata,
        marker_colors=colors, branchvalues='total'
    ))
    fig.update_traces(
        marker=dict(line=dict(width=1, color='#2b2b2b')),
        textinfo="label+percent entry", textposition="middle center",
        hovertemplate="<b>%{customdata}</b><br>%{value:,.0f}원<br>%{percentRoot:.1%}<extra></extra>",
        hoverlabel=dict(font_size=13, align="left")
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color="#e0e0e0",
        uniformtext=dict(minsize=8, mode='hide'),
        margin=dict(t=30, b=10, l=10, r=10)
    )
    return fig


def gen_alloc_html(items: list) -> str:
    fig = _build_alloc_fig(items)
    if fig is None:
        return _empty_html("자산 데이터가 없습니다.")
    return _wrap_html(fig.to_html(include_plotlyjs='cdn', full_html=True))


def gen_alloc_json(items: list) -> dict | None:
    """Plotly figure JSON (data + layout) — 프론트엔드에서 Plotly.react() 로 렌더링."""
    fig = _build_alloc_fig(items)
    return json.loads(fig.to_json()) if fig else None


def _build_history_fig(history_cache: list, real_estate_val: float = 0) -> go.Figure | None:
    if not history_cache:
        return None

    df = pd.DataFrame(history_cache)

    # 예측 데이터 추가 (2037-01-15까지)
    try:
        last_row = df.iloc[-1]
        last_date = pd.to_datetime(last_row['date'])
        current_f = float(last_row['f_asset'])
        target_date = pd.Timestamp("2037-01-15")
        future_data = []
        while True:
            last_date = (last_date + pd.DateOffset(months=1)).replace(day=15)
            if last_date > target_date:
                break
            next_f = current_f * 1.008 + 1600000
            future_data.append({
                "date": last_date.strftime("%Y-%m-%d"),
                "f_asset": next_f,
                "t_asset": next_f + real_estate_val,
                "deposit": 0, "memo": "예측"
            })
            current_f = next_f
        if future_data:
            df = pd.concat([df, pd.DataFrame(future_data)], ignore_index=True)
    except Exception as e:
        print(f"예측 생성 오류: {e}")

    df['prev_f'] = df['f_asset'].shift(1).fillna(0)
    df['prev_t'] = df['t_asset'].shift(1).fillna(0)
    df['profit'] = df.apply(
        lambda r: (r['f_asset'] - r['prev_f'] - r['deposit']) if r['prev_f'] > 0 else 0, axis=1
    )
    df['total_diff'] = df['t_asset'] - df['prev_t']
    df.loc[df['prev_t'] == 0, 'total_diff'] = 0
    if 'memo' in df.columns:
        df.loc[df['memo'] == '예측', ['deposit', 'profit', 'total_diff']] = None

    df['total_diff_m'] = df['total_diff'] / 1_000_000
    df['deposit_m']    = df['deposit']    / 1_000_000
    df['profit_m']     = df['profit']     / 1_000_000
    df['t_asset_100m'] = df['t_asset']    / 100_000_000

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ['#EF5350' if (v is not None and v >= 0) else '#42A5F5' for v in df['total_diff']]
    fig.add_trace(go.Bar(
        x=df['date'], y=df['total_diff_m'], name='전월대비 증감',
        marker=dict(color=colors, line=dict(width=0)),
        customdata=df['total_diff'],
        hovertemplate='%{x}<br>증감: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['deposit_m'], name='순입고',
        mode='lines', line=dict(color='#FFD54F', width=1),
        customdata=df['deposit'],
        hovertemplate='%{x}<br>순입고: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['profit_m'], name='투자손익',
        mode='lines', line=dict(color="#3085DB", width=1),
        customdata=df['profit'],
        hovertemplate='%{x}<br>투자손익: %{customdata:,.0f}원<br>(%{y:,.1f}백만)<extra></extra>'
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=df['date'], y=df['t_asset_100m'], name='총자산',
        mode='lines', line=dict(color='#69F0AE'),
        customdata=df['t_asset'],
        hovertemplate='%{x}<br>총자산: %{customdata:,.0f}원<br>(%{y:,.2f}억)<extra></extra>'
    ), secondary_y=True)

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color="#e0e0e0",
        xaxis=dict(showgrid=True, gridcolor='#404040', tickmode='linear', dtick="M12", tickformat="%y.%m"),
        yaxis=dict(showgrid=True, gridcolor='#404040', title='증감액/손익 (백만)',
                   tickformat=',.0f', zeroline=True, zerolinecolor='#666', zerolinewidth=1, range=[-3.3, 8]),
        yaxis2=dict(showgrid=False, title='총자산 (억)', tickformat=',.1f', range=[0, 10]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=20, l=20, r=20)
    )
    return fig


def gen_history_chart_html(history_cache: list, real_estate_val: float = 0) -> str:
    fig = _build_history_fig(history_cache, real_estate_val)
    if fig is None:
        return _empty_html("히스토리 데이터가 없습니다.")
    return _wrap_html(fig.to_html(include_plotlyjs='cdn', full_html=True))


def gen_history_chart_json(history_cache: list, real_estate_val: float = 0) -> dict | None:
    """Plotly figure JSON (data + layout) — 프론트엔드에서 Plotly.react() 로 렌더링."""
    fig = _build_history_fig(history_cache, real_estate_val)
    return json.loads(fig.to_json()) if fig else None


def _empty_html(msg: str) -> str:
    return f'<html><body style="background:#1e1e2e;color:#9e9e9e;display:flex;justify-content:center;align-items:center;height:100%;margin:0"><h3>{msg}</h3></body></html>'


def _wrap_html(html: str) -> str:
    return html.replace('<body>', '<body style="background-color:#1e1e2e;margin:0;">')
