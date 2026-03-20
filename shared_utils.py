"""공통 유틸리티 — 히스토리 파싱, 연도별 수익률, 상수 등

Desktop(PyQt), Backend(FastAPI), DailySummary 에서 공통으로 사용하는 로직을
한 곳에서 관리하여 코드 중복(DRY 위반)을 방지합니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


# ─── 과거 연도별 수익률 (히스토리 데이터 이전 기간) ───────────
HARDCODED_YIELDS: dict[str, float] = {
    "2011": 19.33, "2012": -4.83, "2013": -25.05, "2014": -33.87,
    "2015": 41.44, "2016": 11.57, "2017": 225.87, "2018": 10.28,
    "2019": 11.29, "2020": 33.68, "2021": 52.01, "2022": -0.36,
    "2023": 17.10, "2024": 16.38,
}


# ─── Firebase 히스토리 문서 파싱 ──────────────────────────────
def parse_history_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Firebase 히스토리 문서 목록을 정규화된 dict 리스트로 변환.

    Parameters
    ----------
    docs : list[dict]
        Firestore REST API 로부터 받은 documents 리스트.

    Returns
    -------
    list[dict]
        ``date`` 기준 오름차순 정렬된 히스토리 레코드 리스트.
        각 레코드: ``{date, f_asset, t_asset, deposit, memo}``
    """
    cache: list[dict[str, Any]] = []
    for doc in docs:
        date_id: str = doc["name"].split("/")[-1]
        fields: dict[str, Any] = doc.get("fields", {})

        def _num(field: str) -> float:
            v = fields.get(field, {})
            return float(v.get("doubleValue", v.get("integerValue", 0)))

        cache.append({
            "date": date_id,
            "f_asset": _num("financial_asset"),
            "t_asset": _num("total_asset") or _num("asset_value"),
            "deposit": _num("net_deposit"),
            "memo": fields.get("memo", {}).get("stringValue", ""),
        })
    cache.sort(key=lambda x: x["date"])
    return cache


# ─── 연도별 수익률 계산 ──────────────────────────────────────
def calc_yearly_yield(
    history_cache: list[dict[str, Any]],
    current_f_asset: float = 0,
) -> list[dict[str, Any]]:
    """히스토리 캐시로부터 연도별 수익률을 계산하여 반환.

    Parameters
    ----------
    history_cache : list[dict]
        ``parse_history_docs()`` 로 파싱된 히스토리 리스트.
    current_f_asset : float
        현재 금융자산 평가액 (0이면 실시간 반영 안 함).

    Returns
    -------
    list[dict]
        연도별 수익률 리스트 (최신 연도 우선).
        각 항목: ``{year, deposit, profit, roi, roi_val,
        deposit_sum, profit_sum, has_actual, in_hardcoded}``
    """
    yearly_summary: dict[str, dict[str, Any]] = {}
    prev_f: float = 0

    for record in history_cache:
        try:
            d = datetime.strptime(record["date"], "%Y-%m-%d")
            # 회계 마감일 기준: 1월 15일 이전 기록은 전년도
            year = str(d.year - 1) if (d.month == 1 and d.day <= 15) else str(d.year)
        except ValueError:
            year = record["date"][:4]

        f_val: float = record["f_asset"]
        dep: float = record["deposit"]
        profit: float = (f_val - prev_f - dep) if prev_f > 0 else 0
        roi: float = (profit / prev_f) if prev_f > 0 else 0

        if year not in yearly_summary:
            yearly_summary[year] = {
                "monthly_returns": [],
                "deposit_sum": 0,
                "profit_sum": 0,
                "has_actual": False,
            }

        if prev_f > 0:
            yearly_summary[year]["monthly_returns"].append(roi)
            yearly_summary[year]["profit_sum"] += profit
            yearly_summary[year]["has_actual"] = True

        yearly_summary[year]["deposit_sum"] += dep
        prev_f = f_val

    # 현재 시점 실시간 데이터 반영
    if current_f_asset > 0 and prev_f > 0:
        now = datetime.now()
        year = str(now.year - 1) if (now.month == 1 and now.day <= 15) else str(now.year)
        curr_profit = current_f_asset - prev_f
        curr_roi = curr_profit / prev_f

        if year not in yearly_summary:
            yearly_summary[year] = {
                "monthly_returns": [],
                "deposit_sum": 0,
                "profit_sum": 0,
                "has_actual": True,
            }
        yearly_summary[year]["monthly_returns"].append(curr_roi)
        yearly_summary[year]["profit_sum"] += curr_profit
        yearly_summary[year]["has_actual"] = True

    all_years = set(HARDCODED_YIELDS.keys()) | set(yearly_summary.keys())
    rows: list[dict[str, Any]] = []

    for year in sorted(all_years, reverse=True):
        ys = yearly_summary.get(year)
        has_actual = bool(ys and ys["has_actual"])

        if year in HARDCODED_YIELDS:
            roi_val = HARDCODED_YIELDS[year]
        elif has_actual:
            assert ys is not None
            prod = 1.0
            for r in ys["monthly_returns"]:
                prod *= (1 + r)
            roi_val = (prod - 1) * 100
        else:
            if not ys:
                continue
            roi_val = 0.0

        rows.append({
            "year": f"{year}년",
            "deposit": f"{ys['deposit_sum']:+,.0f}" if has_actual else "",
            "profit": f"{ys['profit_sum']:+,.0f}" if has_actual else "",
            "roi": f"{roi_val:+.2f}%" if (has_actual or year in HARDCODED_YIELDS) else "",
            "roi_val": roi_val if (has_actual or year in HARDCODED_YIELDS) else None,
            # Desktop UI 및 내보내기용 추가 필드
            "deposit_sum": ys["deposit_sum"] if has_actual else None,
            "profit_sum": ys["profit_sum"] if has_actual else None,
            "has_actual": has_actual,
            "in_hardcoded": year in HARDCODED_YIELDS,
        })

    return rows
