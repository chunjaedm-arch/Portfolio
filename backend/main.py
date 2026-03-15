import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from api_manager import APIManager
from db_manager import DBManager
from data_processor import DataProcessor
from config import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chart_generator import gen_alloc_html, gen_history_chart_html
from analysis_generator import run_analysis, calc_yearly_yield

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
            for doc in h_data.get("documents", []):
                date_id = doc["name"].split("/")[-1]
                f = doc.get("fields", {})
                def gv(field):
                    v = f.get(field, {})
                    return float(v.get("doubleValue", v.get("integerValue", 0)))
                history_cache.append({
                    "date": date_id,
                    "f_asset": gv("financial_asset"),
                    "t_asset": gv("total_asset") or gv("asset_value"),
                    "deposit": gv("net_deposit"),
                    "memo": f.get("memo", {}).get("stringValue", "")
                })
            history_cache.sort(key=lambda x: x["date"])

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


# ─── 히스토리 공통 파싱 헬퍼 ─────────────────────────────
def _parse_history_docs(docs: list) -> list:
    cache = []
    for doc in docs:
        date_id = doc["name"].split("/")[-1]
        f = doc.get("fields", {})
        def gv(field):
            v = f.get(field, {})
            return float(v.get("doubleValue", v.get("integerValue", 0)))
        cache.append({
            "date": date_id,
            "f_asset": gv("financial_asset"),
            "t_asset": gv("total_asset") or gv("asset_value"),
            "deposit": gv("net_deposit"),
            "memo": f.get("memo", {}).get("stringValue", "")
        })
    cache.sort(key=lambda x: x["date"])
    return cache


def _get_history_cache() -> list:
    h_data = _with_auth(db.fetch_history)
    return _parse_history_docs(h_data.get("documents", []))


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
        alloc_html   = gen_alloc_html(port["items"] if isinstance(port, dict) else [])
        history_html = gen_history_chart_html(history, re_val)
        return {"alloc_html": alloc_html, "history_html": history_html}
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
