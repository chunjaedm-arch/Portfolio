"""view_analysis.py의 분석 로직 (PyQt 의존성 제거)"""
import pandas as pd
import numpy as np
import yfinance as yf
import FinanceDataReader as fdr
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime


HARDCODED_YIELDS = {
    "2011": 19.33, "2012": -4.83, "2013": -25.05, "2014": -33.87,
    "2015": 41.44, "2016": 11.57, "2017": 225.87, "2018": 10.28,
    "2019": 11.29, "2020": 33.68, "2021": 52.01, "2022": -0.36,
    "2023": 17.10, "2024": 16.38
}


def run_analysis(history_data: list, current_f_asset: float = 0.0) -> dict:
    if not history_data and current_f_asset <= 0:
        return {"metrics": {}, "chart_html": _empty_html("데이터가 없습니다."), "matrix": []}

    try:
        df_raw = pd.DataFrame(history_data)
        if current_f_asset > 0:
            new_row = {'date': datetime.now().strftime('%Y-%m-%d'), 'f_asset': current_f_asset,
                       'deposit': 0, 't_asset': 0, 'memo': 'Live'}
            df_raw = pd.concat([df_raw, pd.DataFrame([new_row])], ignore_index=True)

        df_raw['date'] = pd.to_datetime(df_raw['date'])
        df_raw.set_index('date', inplace=True)
        df_raw.sort_index(inplace=True)

        df_user = df_raw.resample('ME').agg({'f_asset': 'last', 'deposit': 'sum'})
        df_user['f_asset'] = df_user['f_asset'].ffill()
        df_user = df_user.dropna(subset=['f_asset'])
        df_user['prev_f'] = df_user['f_asset'].shift(1)
        df_user['return'] = 0.0

        for i in range(1, len(df_user)):
            prev = df_user.iloc[i]['prev_f']
            curr = df_user.iloc[i]['f_asset']
            dep  = df_user.iloc[i]['deposit']
            if prev > 0:
                denom = prev + (dep * 0.5)
                if denom != 0:
                    df_user.iloc[i, df_user.columns.get_loc('return')] = (curr - dep - prev) / denom

        df_user['cum_return'] = (1 + df_user['return']).cumprod()

        start_date = df_user.index[0] if not df_user.empty else datetime.now()
        end_date   = datetime.now()

        # SPY
        df_spy = yf.Ticker("SPY").history(start=start_date, end=end_date, auto_adjust=True)
        # KOSPI
        try:
            df_kospi = fdr.DataReader('KS11', start_date, end_date)
        except:
            df_kospi = pd.DataFrame()
        if df_kospi.empty:
            try:
                df_kospi = yf.Ticker("^KS11").history(start=start_date, end=end_date)
            except:
                pass
        # IRX
        df_irx = yf.Ticker("^IRX").history(start=start_date, end=end_date)

        for d in [df_spy, df_kospi, df_irx]:
            if not d.empty and d.index.tz is not None:
                d.index = d.index.tz_localize(None)

        df_irx_monthly = df_irx['Close'].resample('ME').mean() if not df_irx.empty else pd.Series()
        irx_series = df_irx_monthly.ffill() / 100 if not df_irx_monthly.empty else pd.Series(0.045, index=df_user.index)

        df_user['irx_annual'] = irx_series.reindex(df_user.index).ffill().fillna(0.045)
        df_user['rf_period']  = df_user['irx_annual'] / 12
        df_user['excess_return'] = df_user['return'] - df_user['rf_period']

        def proc_bench(df_b):
            # 앱 버전과 동일: 매월 15일 이하 마지막 거래일 기준
            close = df_b['Close']
            close_15 = close[close.index.day <= 15]
            m = close_15.groupby(close_15.index.to_period('M')).last().to_frame()
            m.index = m.index.to_timestamp() + pd.offsets.Day(14)
            m['return'] = m['Close'].pct_change().fillna(0)
            m['cum_return'] = (1 + m['return']).cumprod()
            m['irx_annual'] = irx_series.reindex(m.index, method='nearest').ffill().fillna(0.045)
            m['rf_period'] = m['irx_annual'] / 12
            m['excess_return'] = m['return'] - m['rf_period']
            return m

        df_spy   = proc_bench(df_spy)   if not df_spy.empty   else pd.DataFrame()
        df_kospi = proc_bench(df_kospi) if not df_kospi.empty else pd.DataFrame()

        def calc_metrics(df):
            if df.empty: return {}
            years = len(df) / 12
            if years <= 0: return {}
            total_ret = (1 + df['return']).prod()
            cagr = total_ret - 1 if years < 1 else (total_ret ** (1/years)) - 1
            cum  = (1 + df['return']).cumprod()
            mdd  = (cum / cum.cummax() - 1).min()
            # Sharpe/Sortino는 최소 6개월 이상 데이터가 있어야 의미있는 값
            if len(df) < 6:
                sharpe, sortino = None, None
            else:
                mean_ex = df['excess_return'].mean() * 12
                std_ex  = df['excess_return'].std() * np.sqrt(12)
                sharpe  = mean_ex / std_ex if (std_ex and not np.isnan(std_ex)) else 0.0
                downside = df[df['excess_return'] < 0]['excess_return']
                down_dev = np.sqrt((downside**2).sum()/len(df)) * np.sqrt(12) if len(downside) > 0 else 0.0
                sortino = (mean_ex / down_dev) if down_dev > 0 else (99.9 if mean_ex > 0 else 0.0)
            rf = df['irx_annual'].mean() if 'irx_annual' in df.columns else 0.045
            return {'cagr': cagr, 'mdd': mdd, 'sharpe': sharpe, 'sortino': sortino, 'rf_avg': rf}

        periods_map = {'All': 0, '2M': 2, '3M': 3, '6M': 6, '1Y': 12, '1.5Y': 18, '2Y': 24,
                       '2.5Y': 30, '3Y': 36, '3.5Y': 42, '4Y': 48, '4.5Y': 54, '5Y': 60}
        raw_matrix = {}
        for p_name, months in periods_map.items():
            if p_name == 'All':
                sub_u = df_user.iloc[1:] if len(df_user) > 1 else pd.DataFrame()
            else:
                if len(df_user) > months:
                    sub_u = df_user.tail(months)
                else:
                    raw_matrix[p_name] = {'user': None, 'spy': None, 'kospi': None}
                    continue
            if sub_u.empty:
                raw_matrix[p_name] = {'user': None, 'spy': None, 'kospi': None}
                continue
            start_dt = sub_u.index[0]
            sub_spy   = df_spy[df_spy.index >= start_dt]   if not df_spy.empty   else pd.DataFrame()
            sub_kospi = df_kospi[df_kospi.index >= start_dt] if not df_kospi.empty else pd.DataFrame()
            raw_matrix[p_name] = {
                'user':  calc_metrics(sub_u),
                'spy':   calc_metrics(sub_spy),
                'kospi': calc_metrics(sub_kospi),
            }

        all_u = raw_matrix.get('All', {}).get('user') or {}
        all_s = raw_matrix.get('All', {}).get('spy')  or {}
        all_k = raw_matrix.get('All', {}).get('kospi') or {}

        metrics = {
            'cagr_user':    all_u.get('cagr', 0),   'cagr_spy':    all_s.get('cagr', 0),   'cagr_kospi':    all_k.get('cagr', 0),
            'mdd_user':     all_u.get('mdd', 0),    'mdd_spy':     all_s.get('mdd', 0),    'mdd_kospi':     all_k.get('mdd', 0),
            'sharpe_user':  all_u.get('sharpe', 0), 'sharpe_spy':  all_s.get('sharpe', 0), 'sharpe_kospi':  all_k.get('sharpe', 0),
            'sortino_user': all_u.get('sortino', 0),'sortino_spy': all_s.get('sortino', 0),'sortino_kospi': all_k.get('sortino', 0),
            'rf_avg':       all_u.get('rf_avg', 0),
        }

        # DD 계산
        cum_u = (1 + df_user['return']).cumprod()
        df_user['dd'] = cum_u / cum_u.cummax() - 1
        if not df_spy.empty:
            cum_s = (1 + df_spy['return']).cumprod()
            df_spy['dd'] = cum_s / cum_s.cummax() - 1
        if not df_kospi.empty:
            cum_k = (1 + df_kospi['return']).cumprod()
            df_kospi['dd'] = cum_k / cum_k.cummax() - 1

        chart_html = _gen_analysis_chart(df_user, df_spy, df_kospi)

        # 매트릭스 테이블용 직렬화
        periods_order = ['All','2M','3M','6M','1Y','1.5Y','2Y','2.5Y','3Y','3.5Y','4Y','4.5Y','5Y']
        rows_def = [
            ("CAGR (내 포트)", 'cagr', 'user', True),
            ("CAGR (SPY)",    'cagr', 'spy',  True),
            ("CAGR (KOSPI)",  'cagr', 'kospi',True),
            ("MDD (내 포트)", 'mdd',  'user', True),
            ("MDD (SPY)",     'mdd',  'spy',  True),
            ("MDD (KOSPI)",   'mdd',  'kospi',True),
            ("Sharpe (내 포트)", 'sharpe', 'user', False),
            ("Sharpe (SPY)",     'sharpe', 'spy',  False),
            ("Sharpe (KOSPI)",   'sharpe', 'kospi',False),
            ("Sortino (내 포트)",'sortino','user', False),
            ("Sortino (SPY)",    'sortino','spy',  False),
            ("Sortino (KOSPI)",  'sortino','kospi',False),
            ("Risk-Free Rate",   'rf_avg', 'user', True),
        ]
        matrix_rows = []
        for label, mk, src, is_pct in rows_def:
            row = {"label": label}
            for p in periods_order:
                d = raw_matrix.get(p, {}).get(src)
                if d:
                    v = d.get(mk)
                    row[p] = f"{v*100:.2f}%" if (v is not None and is_pct) else (f"{v:.2f}" if v is not None else "-")
                else:
                    row[p] = "-"
            matrix_rows.append(row)

        return {"metrics": metrics, "chart_html": chart_html, "matrix": matrix_rows}

    except Exception as e:
        print(f"Analysis error: {e}")
        return {"metrics": {}, "chart_html": _empty_html(f"분석 오류: {e}"), "matrix": []}


def _gen_analysis_chart(df_user, df_spy, df_kospi) -> str:
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
        row_heights=[0.65, 0.35],
        subplot_titles=("📈 누적 수익률 (Cumulative Return)", "🌊 낙폭 (Drawdown)")
    )
    fig.add_trace(go.Scatter(
        x=df_user.index, y=(df_user['cum_return']-1)*100, name="내 포트폴리오",
        line=dict(color='#4DABF7', width=3), hovertemplate='%{y:.2f}%'
    ), row=1, col=1)
    if not df_spy.empty:
        fig.add_trace(go.Scatter(
            x=df_spy.index, y=(df_spy['cum_return']-1)*100, name="S&P500 (SPY)",
            line=dict(color='#9E9E9E', width=1.5, dash='dot'), hovertemplate='%{y:.2f}%'
        ), row=1, col=1)
    if not df_kospi.empty:
        fig.add_trace(go.Scatter(
            x=df_kospi.index, y=(df_kospi['cum_return']-1)*100, name="KOSPI",
            line=dict(color='#FF9800', width=1.5, dash='dot'), hovertemplate='%{y:.2f}%'
        ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_user.index, y=df_user['dd']*100, name="내 DD",
        fill='tozeroy', line=dict(color='#FF6B6B', width=1), hovertemplate='%{y:.2f}%'
    ), row=2, col=1)
    if not df_spy.empty:
        fig.add_trace(go.Scatter(
            x=df_spy.index, y=df_spy['dd']*100, name="SPY DD",
            line=dict(color='#9E9E9E', width=1, dash='dot'), hovertemplate='%{y:.2f}%'
        ), row=2, col=1)
    if not df_kospi.empty:
        fig.add_trace(go.Scatter(
            x=df_kospi.index, y=df_kospi['dd']*100, name="KOSPI DD",
            line=dict(color='#FF9800', width=1, dash='dot'), hovertemplate='%{y:.2f}%'
        ), row=2, col=1)
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color="#e0e0e0", margin=dict(t=40, b=20, l=20, r=20),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#000", font_size=13, font_color="#D4AF37", bordercolor="#D4AF37")
    )
    fig.update_yaxes(title_text="수익률 (%)", row=1, col=1, gridcolor='#404040', zerolinecolor='#666')
    fig.update_yaxes(title_text="낙폭 (%)",   row=2, col=1, gridcolor='#404040', zerolinecolor='#666')
    fig.update_xaxes(gridcolor='#404040')
    html = fig.to_html(include_plotlyjs='cdn', full_html=True)
    return html.replace('<body>', '<body style="background-color:#1e1e2e;margin:0;">')


def calc_yearly_yield(history_cache: list, current_f_asset: float = 0) -> list:
    yearly_summary = {}
    prev_f = 0
    for record in history_cache:
        try:
            from datetime import datetime as dt
            d = dt.strptime(record['date'], "%Y-%m-%d")
            year = str(d.year - 1) if (d.month == 1 and d.day <= 15) else str(d.year)
        except:
            year = record['date'][:4]
        f, dep = record['f_asset'], record['deposit']
        profit = (f - prev_f - dep) if prev_f > 0 else 0
        roi    = (profit / prev_f) if prev_f > 0 else 0
        if year not in yearly_summary:
            yearly_summary[year] = {'monthly_returns': [], 'deposit_sum': 0, 'profit_sum': 0, 'has_actual': False}
        if prev_f > 0:
            yearly_summary[year]['monthly_returns'].append(roi)
            yearly_summary[year]['profit_sum'] += profit
            yearly_summary[year]['has_actual'] = True
        yearly_summary[year]['deposit_sum'] += dep
        prev_f = f

    if current_f_asset > 0 and prev_f > 0:
        from datetime import datetime as dt
        now = dt.now()
        year = str(now.year - 1) if (now.month == 1 and now.day <= 15) else str(now.year)
        curr_profit = current_f_asset - prev_f
        curr_roi    = curr_profit / prev_f
        if year not in yearly_summary:
            yearly_summary[year] = {'monthly_returns': [], 'deposit_sum': 0, 'profit_sum': 0, 'has_actual': True}
        yearly_summary[year]['monthly_returns'].append(curr_roi)
        yearly_summary[year]['profit_sum'] += curr_profit
        yearly_summary[year]['has_actual'] = True

    all_years = set(HARDCODED_YIELDS.keys()) | set(yearly_summary.keys())
    rows = []
    for year in sorted(all_years, reverse=True):
        ys = yearly_summary.get(year)
        has_actual = ys and ys['has_actual']
        if year in HARDCODED_YIELDS:
            roi = HARDCODED_YIELDS[year]
        elif has_actual:
            prod = 1.0
            for r in ys['monthly_returns']:
                prod *= (1 + r)
            roi = (prod - 1) * 100
        else:
            if not ys: continue
            roi = 0
        rows.append({
            "year":    f"{year}년",
            "deposit": f"{ys['deposit_sum']:+,.0f}" if has_actual else "",
            "profit":  f"{ys['profit_sum']:+,.0f}"  if has_actual else "",
            "roi":     f"{roi:+.2f}%" if (has_actual or year in HARDCODED_YIELDS) else "",
            "roi_val": roi if (has_actual or year in HARDCODED_YIELDS) else None,
        })
    return rows


def _empty_html(msg: str) -> str:
    return f'<html><body style="background:#1e1e2e;color:#9e9e9e;display:flex;justify-content:center;align-items:center;height:100%;margin:0"><h3>{msg}</h3></body></html>'
