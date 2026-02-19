import pandas as pd
import os
import sys
from datetime import datetime

def test_analysis_logic():
    print("--- Analysis Logic Verification (from History.csv) ---")
    
    # 1. History.csv 로드 시도
    # 실행 파일 위치 기준
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "History.csv")
    
    if not os.path.exists(csv_path):
        print(f"[오류] {csv_path} 파일을 찾을 수 없습니다.")
        print("-> 앱에서 '데이터 내보내기'를 먼저 실행하여 History.csv를 생성해주세요.")
        return

    print(f"[성공] History.csv 로드: {csv_path}")
    try:
        # 인코딩은 utf-8-sig (DataExporter 기준)
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except Exception as e:
        print(f"[오류] CSV 읽기 실패: {e}")
        return

    # 2. 데이터 전처리
    # 컬럼 매핑: '날짜' -> 'date', '금융자산' -> 'f_asset', '순입고' -> 'deposit'
    if '날짜' in df.columns:
        df['date'] = pd.to_datetime(df['날짜'])
    else:
        print("[오류] '날짜' 컬럼을 찾을 수 없습니다.")
        return

    def parse_currency(val):
        if isinstance(val, str):
            return float(val.replace(',', '').replace('+', '').replace(' ', ''))
        return float(val)

    try:
        df['f_asset'] = df['금융자산'].apply(parse_currency)
        df['deposit'] = df['순입고'].apply(parse_currency)
    except KeyError as e:
        print(f"[오류] 필요한 컬럼이 없습니다: {e}")
        return

    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)

    # 3. 2025년 8월, 9월 데이터 확인 (사용자 요청 사항)
    print("\n[1. 2025년 8월 ~ 9월 데이터 확인]")
    target_months = ['2025-08', '2025-09']
    
    for tm in target_months:
        # 해당 월의 데이터 필터링
        mask = df.index.astype(str).str.startswith(tm)
        subset = df[mask]
        
        if not subset.empty:
            print(f"\n>>> {tm} 데이터 발견 ({len(subset)}건)")
            for idx, row in subset.iterrows():
                print(f"Date: {idx.date()} | 금융자산(f_asset): {row['f_asset']:,.0f} | 순입고(deposit): {row['deposit']:,.0f}")
        else:
            print(f"\n>>> {tm} 데이터 없음")

    # 4. 최근 6개월 수익률 계산 시뮬레이션
    print("\n[2. 최근 6개월 수익률 계산 검증]")
    
    # 월 단위 리샘플링 (AnalysisWorker 로직 동일 적용)
    try:
        df_monthly = df.resample('ME').agg({
            'f_asset': 'last',
            'deposit': 'sum'
        })
    except ValueError:
        # pandas 버전에 따라 'ME'가 지원되지 않을 경우 'M' 사용
        df_monthly = df.resample('M').agg({
            'f_asset': 'last',
            'deposit': 'sum'
        })

    # 빈 달은 전월 자산으로 채움
    df_monthly['f_asset'] = df_monthly['f_asset'].ffill()
    
    # 최근 6개월 필터링
    if df_monthly.empty:
        print("데이터가 없습니다.")
        return

    end_date = df_monthly.index[-1]
    start_date = end_date - pd.DateOffset(months=6)
    
    df_sub = df_monthly[df_monthly.index >= start_date].copy()
    
    print(f"분석 기간: {start_date.date()} ~ {end_date.date()}")
    
    # 수익률 계산 (Modified Dietz 적용)
    df_sub['prev_f'] = df_sub['f_asset'].shift(1)
    df_sub['return'] = 0.0
    
    print(f"\n{'Date':<12} | {'Prev Asset':>15} | {'Deposit':>12} | {'Curr Asset':>15} | {'Return(%)':>10}")
    print("-" * 80)

    for i in range(1, len(df_sub)):
        dt = df_sub.index[i]
        prev = df_sub.iloc[i]['prev_f']
        curr = df_sub.iloc[i]['f_asset']
        dep = df_sub.iloc[i]['deposit']
        
        ret = 0.0
        if prev > 0:
            ret = (curr - dep - prev) / prev
        
        df_sub.iloc[i, df_sub.columns.get_loc('return')] = ret
        print(f"{dt.strftime('%Y-%m-%d'):<12} | {prev:15,.0f} | {dep:12,.0f} | {curr:15,.0f} | {ret*100:10.2f}%")

    # 결과 요약
    total_ret = (1 + df_sub['return']).prod() - 1
    days = (df_sub.index[-1] - df_sub.index[0]).days
    years = days / 365.25
    
    print("-" * 80)
    print(f"단순 누적 수익률: {total_ret * 100:.2f}%")
    print(f"기간(년): {years:.2f}")
    
    if years < 1:
        print(f"CAGR (1년 미만 -> 단순 수익률 표시): {total_ret * 100:.2f}%")
    else:
        cagr = ((1 + total_ret) ** (1/years)) - 1
        print(f"CAGR (연율화 적용): {cagr * 100:.2f}%")

if __name__ == "__main__":
    test_analysis_logic()
