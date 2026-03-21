import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import csv
import io
import zipfile as _zipfile
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from api_manager import APIManager
from db_manager import DBManager
from data_processor import DataProcessor
from config import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chart_generator import gen_alloc_html, gen_alloc_json, gen_history_chart_html, gen_history_chart_json
from analysis_generator import run_analysis
from shared_utils import parse_history_docs, calc_yearly_yield

app = FastAPI(title="Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://SDMTechnology.asuscomm.com",
        "https://SDMTechnology.asuscomm.com",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

_API_KEY = os.environ.get("API_SECRET_KEY", "")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def _verify_key(key: str = Depends(_api_key_header)):
    if not _API_KEY or key != _API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")

api = APIManager()
db  = DBManager(config['projectId'], config['apiKey'])
processor = DataProcessor()

# ─── 마켓 데이터 인메모리 캐시 ─────────────────────────────
_market_cache: dict = {}
_market_cache_at: datetime | None = None
MARKET_CACHE_TTL = 60  # 초

# ─── Firebase 토큰 관리 ───────────────────────────────────
_id_token: str | None = None
_refresh_token_str: str | None = None


def _do_login():
    global _id_token, _refresh_token_str
    email    = os.environ.get("FIREBASE_EMAIL", "")
    password = os.environ.get("FIREBASE_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("FIREBASE_EMAIL / FIREBASE_PASSWORD 환경변수가 설정되지 않았습니다.")
    result = db.login(email, password)
    _id_token = result["idToken"]
    _refresh_token_str = result.get("refreshToken")


def _get_id_token() -> str:
    global _id_token
    if _id_token is None:
        _do_login()
    return _id_token  # type: ignore


def _refresh_id_token() -> str:
    global _id_token, _refresh_token_str
    if _refresh_token_str:
        _id_token, _refresh_token_str = db.refresh_auth_token(_refresh_token_str)
    else:
        _do_login()
    return _id_token  # type: ignore


def _with_auth(fn, *args, **kwargs):
    """인증 오류 시 토큰 갱신 후 1회 재시도"""
    try:
        token = _get_id_token()
        return fn(token, *args, **kwargs)
    except Exception as e:
        if "authentication" in str(e).lower() or "401" in str(e):
            token = _refresh_id_token()
            return fn(token, *args, **kwargs)
        raise


# ─── 마켓 데이터 패치 (공통) ──────────────────────────────
def _fetch_market_data() -> dict:
    global _market_cache, _market_cache_at
    now = datetime.now()
    if _market_cache_at and (now - _market_cache_at) < timedelta(seconds=MARKET_CACHE_TTL):
        return _market_cache

    usd_rate, jpy_rate, cny_rate, brl_rate, source = api.fetch_exchange_rates()
    usd_rate = usd_rate or 0.0
    jpy_rate = jpy_rate or 0.0
    cny_rate = cny_rate or 0.0
    brl_rate = brl_rate or 0.0

    raw_indices = api.fetch_market_indices()
    indices = {name: {"price": p, "change": c} for name, (p, c) in raw_indices.items()}

    gold_info   = api.get_detailed_gold_prices(usd_rate)
    upbit_usdt, _ = api.get_upbit_price("USDT")

    kimp = krx_prem = iau_prem = gold_spread = None
    if upbit_usdt and usd_rate > 0:
        kimp = ((upbit_usdt / usd_rate) - 1) * 100
    if gold_info.get("int_spot", 0) > 0 and gold_info.get("krx_spot", 0) > 0:
        krx_prem = ((gold_info["krx_spot"]    / gold_info["int_spot"]) - 1) * 100
    if gold_info.get("int_spot", 0) > 0 and gold_info.get("iau_krw_g", 0) > 0:
        iau_prem = ((gold_info["iau_krw_g"]   / gold_info["int_spot"]) - 1) * 100
    if gold_info.get("int_spot", 0) > 0 and gold_info.get("int_future", 0) > 0:
        gold_spread = ((gold_info["int_future"] / gold_info["int_spot"]) - 1) * 100

    _market_cache = {
        "source": source or "-",
        "usd_rate": usd_rate, "jpy_rate": jpy_rate,
        "cny_rate": cny_rate, "brl_rate": brl_rate,
        "indices": indices, "gold_info": gold_info,
        "kimp": kimp, "krx_prem": krx_prem,
        "iau_prem": iau_prem, "gold_spread": gold_spread,
    }
    _market_cache_at = now
    return _market_cache


# ─── 엔드포인트: 마켓 ────────────────────────────────────
@app.get("/api/market", dependencies=[Depends(_verify_key)])
async def get_market():
    return _fetch_market_data()


# ─── 엔드포인트: 포트폴리오 ──────────────────────────────
@app.get("/api/portfolio", dependencies=[Depends(_verify_key)])
async def get_portfolio():
    try:
        market = _fetch_market_data()
        usd = market["usd_rate"]; jpy = market["jpy_rate"]
        cny = market["cny_rate"]; brl = market["brl_rate"]
        gold = market["gold_info"]

        # Firebase에서 포트폴리오 조회
        data = _with_auth(db.fetch_portfolio)
        docs = data.get("documents", [])

        items, f_total, all_total, invest_total, _ = processor.process_portfolio_data(
            docs, usd, jpy, cny, brl, gold, api
        )

        # 리밸런싱 예정금액 계산
        for item in items:
            rebal = 0.0
            if item["main"] in ["투자", "단타"] and item["target_ratio"] > 0:
                target_val = invest_total * (item["target_ratio"] / 100)
                rebal = target_val - item["row_val"]
            item["rebal_amt"] = rebal

        # 히스토리 및 Peak 조회 (수익률·MDD 계산용)
        history_cache = []
        peak_f_asset = 0.0
        peak_date = "-"
        try:
            h_data = _with_auth(db.fetch_history)
            history_cache = parse_history_docs(h_data.get("documents", []))

            stats = _with_auth(db.get_stats)
            sf = stats.get("fields", {})
            pv = sf.get("peak_financial_asset", {})
            peak_f_asset = float(pv.get("doubleValue", pv.get("integerValue", 0)))
            ts = sf.get("updated_at", {}).get("timestampValue", "")
            peak_date = ts[:10].replace("-", "") if ts else "-"
        except Exception as e:
            print(f"히스토리/Peak 로드 오류: {e}")

        roi, growth = processor.calculate_metrics(f_total, all_total, history_cache)
        mdd_val, mdd_pct = processor.calculate_mdd(f_total, peak_f_asset, peak_date, history_cache)

        return {
            "items": items,
            "f_total": f_total,
            "all_total": all_total,
            "invest_total": invest_total,
            "roi": roi,
            "growth": growth,
            "peak_val": peak_f_asset,
            "peak_date": peak_date[:4] + "-" + peak_date[4:6] if len(peak_date) == 8 else peak_date,
            "mdd_val": mdd_val,
            "mdd_pct": mdd_pct,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 엔드포인트: 자산 저장 ───────────────────────────────
class AssetPayload(BaseModel):
    name: str
    fields: dict


@app.patch("/api/portfolio/{name}", dependencies=[Depends(_verify_key)])
async def save_asset(name: str, body: AssetPayload):
    try:
        payload = {
            "fields": {
                "대분류":    {"stringValue": body.fields.get("대분류", "")},
                "소분류":    {"stringValue": body.fields.get("소분류", "")},
                "티커":      {"stringValue": body.fields.get("티커", "")},
                "수량":      {"doubleValue": float(body.fields.get("수량", 0) or 0)},
                "금액(달러)": {"doubleValue": float(body.fields.get("금액(달러)", 0) or 0)},
                "금액(엔)":  {"doubleValue": float(body.fields.get("금액(엔)", 0) or 0)},
                "금액(원)":  {"doubleValue": float(body.fields.get("금액(원)", 0) or 0)},
                "목표비중":  {"doubleValue": float(body.fields.get("목표비중", 0) or 0)},
                "비고":      {"stringValue": body.fields.get("비고", "")},
            }
        }
        _with_auth(db.save_asset, name, payload)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 엔드포인트: 자산 삭제 ───────────────────────────────
@app.delete("/api/portfolio/{name}", dependencies=[Depends(_verify_key)])
async def delete_asset(name: str):
    try:
        _with_auth(db.delete_asset, name)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_history_cache() -> list:
    h_data = _with_auth(db.fetch_history)
    return parse_history_docs(h_data.get("documents", []))


# ─── 엔드포인트: 히스토리 조회 ───────────────────────────
@app.get("/api/history", dependencies=[Depends(_verify_key)])
async def get_history():
    try:
        cache = _get_history_cache()
        # 연도별 수익률 계산
        yearly = calc_yearly_yield(cache)
        # 테이블용 행 계산 (투자수익, 수익률 추가)
        rows = []
        prev_f, prev_t = 0.0, 0.0
        for item in cache:
            f, t, dep = item['f_asset'], item['t_asset'], item['deposit']
            profit = (f - prev_f - dep) if prev_f > 0 else 0
            roi    = (profit / prev_f * 100) if prev_f > 0 else 0
            growth = ((t - prev_t) / prev_t * 100) if prev_t > 0 else 0
            rows.append({**item, "profit": profit, "roi": roi, "growth": growth})
            prev_f, prev_t = f, t
        return {"rows": list(reversed(rows)), "yearly": yearly}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 엔드포인트: 히스토리 저장 ───────────────────────────
class HistoryPayload(BaseModel):
    date: str
    f_asset: float
    t_asset: float
    deposit: float
    memo: str = ""


@app.patch("/api/history/{date_id}", dependencies=[Depends(_verify_key)])
async def save_history(date_id: str, body: HistoryPayload):
    try:
        payload = {"fields": {
            "financial_asset": {"doubleValue": body.f_asset},
            "total_asset":     {"doubleValue": body.t_asset},
            "net_deposit":     {"doubleValue": body.deposit},
            "memo":            {"stringValue": body.memo},
        }}
        _with_auth(db.save_history, date_id, payload)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 엔드포인트: 히스토리 삭제 ───────────────────────────
@app.delete("/api/history/{date_id}", dependencies=[Depends(_verify_key)])
async def delete_history(date_id: str):
    try:
        _with_auth(db.delete_history, date_id)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 엔드포인트: 차트 HTML 생성 ──────────────────────────
@app.get("/api/charts", dependencies=[Depends(_verify_key)])
async def get_charts():
    try:
        market  = _fetch_market_data()
        port    = await get_portfolio()          # 내부 재사용
        items   = port.get("items", []) if isinstance(port, dict) else port.body  # type: ignore
        history = _get_history_cache()
        re_val  = sum(i['row_val'] for i in (port["items"] if isinstance(port, dict) else []) if i.get('main') == '부동산')
        port_items = port["items"] if isinstance(port, dict) else []
        alloc_html   = gen_alloc_html(port_items)
        history_html = gen_history_chart_html(history, re_val)
        alloc_json   = gen_alloc_json(port_items)
        history_json = gen_history_chart_json(history, re_val)
        return {
            "alloc_html": alloc_html, "history_html": history_html,
            "alloc_json": alloc_json, "history_json": history_json,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── 분석 캐시 ────────────────────────────────────────────
_analysis_cache: dict = {}
_analysis_cache_at: datetime | None = None
ANALYSIS_CACHE_TTL = 300  # 5분


# ─── 엔드포인트: 분석 ────────────────────────────────────
@app.get("/api/analysis", dependencies=[Depends(_verify_key)])
async def get_analysis():
    global _analysis_cache, _analysis_cache_at
    now = datetime.now()
    if _analysis_cache_at and (now - _analysis_cache_at) < timedelta(seconds=ANALYSIS_CACHE_TTL):
        return _analysis_cache
    try:
        history = _get_history_cache()
        port    = await get_portfolio()
        f_total = port.get("f_total", 0) if isinstance(port, dict) else 0
        result  = run_analysis(history, f_total)
        _analysis_cache = result
        _analysis_cache_at = now
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── 엔드포인트: CSV 내보내기 (ZIP) ──────────────────────
@app.get("/api/export", dependencies=[Depends(_verify_key)])
async def export_data():
    today_str = datetime.now().strftime("%Y%m%d")

    def csv_bytes(rows: list) -> bytes:
        buf = io.StringIO()
        csv.writer(buf).writerows(rows)
        return buf.getvalue().encode("utf-8-sig")

    def fmt_pct(v):
        if v is None: return "-"
        return f"{v:+.2f}%"

    zip_buf = io.BytesIO()
    with _zipfile.ZipFile(zip_buf, "w", _zipfile.ZIP_DEFLATED) as zf:

        # ── 포트폴리오 / 자산 ────────────────────────────
        port   = await get_portfolio()
        items  = port.get("items", []) if isinstance(port, dict) else []
        market = _fetch_market_data()
        gold   = market.get("gold_info", {})
        indices = market.get("indices", {})
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── Summary.csv (기존 앱과 동일 구조) ─────────────
        f_total   = port.get("f_total",  0)
        all_total = port.get("all_total", 0)
        roi       = port.get("roi")
        growth    = port.get("growth")
        peak_val  = port.get("peak_val",  0)
        peak_date = port.get("peak_date", "-")
        mdd_val   = port.get("mdd_val",   0)
        mdd_pct   = port.get("mdd_pct",   0)
        invest_total = port.get("invest_total", 0)

        usd = market.get("usd_rate", 0)
        jpy = market.get("jpy_rate", 0)
        cny = market.get("cny_rate", 0)
        brl = market.get("brl_rate", 0)
        kimp       = market.get("kimp")
        krx_prem   = market.get("krx_prem")
        iau_prem   = market.get("iau_prem")
        gold_spread= market.get("gold_spread")

        summary_rows = [["항목", "값"], ["기록시간", now_str]]
        summary_rows += [
            ["USD환율",          f"{usd:,.2f}"],
            ["JPY환율(100엔)",   f"{jpy*100:,.2f}"],
            ["CNY환율",          f"{cny:,.2f}"],
            ["BRL환율",          f"{brl:,.2f}"],
            ["국제금(현물)",     f"{gold.get('int_spot',0):,.0f}"],
            ["국제금(선물)",     f"{gold.get('int_future',0):,.0f}"],
            ["KRX금(현물)",      f"{gold.get('krx_spot',0):,.0f}"],
            ["국내금(현물)",     f"{gold.get('domestic_spot',0):,.0f}"],
            ["김치프리미엄",     fmt_pct(kimp)],
            ["KRX금프리미엄",    fmt_pct(krx_prem)],
            ["IAU금프리미엄",    fmt_pct(iau_prem)],
            ["국제금스프레드",   fmt_pct(gold_spread)],
            ["* 금융자산합계",   f"{f_total:,.0f}"],
            ["* 총자산(부동산포함)", f"{all_total:,.0f}"],
            ["투자수익률(전월비)", fmt_pct(roi)],
            ["자산증감률(전월비)", fmt_pct(growth)],
            ["전고점(Max)",      f"{peak_val:,.0f}"],
            ["전고점날짜",       peak_date],
            ["DD",               f"{mdd_val:,.0f}"],
            ["DD%",              f"{mdd_pct:.2f}%"],
            ["rebalance_active_pool", f"{invest_total:.0f}"],
        ]
        for name in ["KOSPI","KOSDAQ","S&P500","NASDAQ","Nikkei225","HangSeng","VIX","US10Y"]:
            if name in indices:
                idx = indices[name]
                summary_rows.append([name, f"{idx['price']:,.2f} ({idx['change']:+.2f}%)"])
        zf.writestr("Summary.csv", csv_bytes(summary_rows))

        # ── Assets.csv (기존 앱과 동일 컬럼) ─────────────
        asset_header = [
            "대분류", "소분류", "품명", "리밸런싱예정금액", "평가액(합계)",
            "금액(달러)", "금액(엔)", "금액(원)", "수량", "티커",
            "목표비중", "전일대비", "단가", "비고",
            "AI_Category", "Price_Updated_At", "Market_Status",
        ]
        asset_rows = [asset_header]
        for it in items:
            main = it.get("main", "")
            ai_cat = "Active_Pool" if main in ("투자", "단타") else ("Savings" if main == "현금" else "None")
            tr = it.get("target_ratio", 0)
            asset_rows.append([
                main,
                it.get("sub", ""),
                it.get("name", ""),
                f"{it.get('rebal_amt', 0):+.0f}",
                f"{it.get('row_val', 0):,.0f}",
                f"{it.get('usd', 0):,.2f}" if it.get("usd") else "",
                f"{it.get('jpy', 0):,.2f}" if it.get("jpy") else "",
                f"{it.get('krw', 0):,.0f}" if it.get("krw") else "",
                it.get("qty", ""),
                it.get("ticker", ""),
                f"{tr:.4f}" if tr else "0",
                it.get("diff_str", ""),
                it.get("unit_price_str", ""),
                it.get("note", ""),
                ai_cat,
                it.get("updated_at", "-"),
                it.get("market_status", "-"),
            ])
        zf.writestr("Assets.csv", csv_bytes(asset_rows))

        # ── History.csv (기존 앱과 동일 컬럼) ────────────
        cache = _get_history_cache()
        hist_header = ["날짜", "금융자산", "총자산", "순입고", "투자손익", "투자수익률", "자산증감율", "비고"]
        hist_rows = [hist_header]
        prev_f, prev_t = 0.0, 0.0
        for item in cache:
            f, t, dep = item["f_asset"], item["t_asset"], item["deposit"]
            profit = (f - prev_f - dep) if prev_f > 0 else 0
            roi_h  = (profit / prev_f * 100) if prev_f > 0 else 0
            growth_h = ((t - prev_t) / prev_t * 100) if prev_t > 0 else 0
            hist_rows.append([
                item["date"],
                f"{f:,.0f}", f"{t:,.0f}", f"{dep:,.0f}",
                f"{profit:,.0f}", f"{roi_h:.2f}%", f"{growth_h:.2f}%",
                item["memo"],
            ])
            prev_f, prev_t = f, t
        zf.writestr("History.csv", csv_bytes(hist_rows))

        # ── Yearly.csv ────────────────────────────────────
        yearly = calc_yearly_yield(cache)
        yearly_rows = [["연도", "순입고", "투자수익", "수익률"]] + [
            [r.get("year",""), r.get("deposit",""), r.get("profit",""), r.get("roi","")]
            for r in yearly
        ]
        zf.writestr("Yearly.csv", csv_bytes(yearly_rows))

        # ── Analysis.csv ──────────────────────────────────
        try:
            analysis = await get_analysis()
            matrix   = analysis.get("matrix", []) if isinstance(analysis, dict) else []
            if matrix:
                periods = ["All","2M","3M","6M","1Y","1.5Y","2Y","2.5Y","3Y","3.5Y","4Y","4.5Y","5Y"]
                an_rows = [["지표"] + periods]
                for row in matrix:
                    an_rows.append([row.get("label","")] + [row.get(p, "-") for p in periods])
                zf.writestr("Analysis.csv", csv_bytes(an_rows))
        except Exception as e:
            print(f"Analysis export 오류: {e}")

    zip_buf.seek(0)
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={today_str}.zip"},
    )
