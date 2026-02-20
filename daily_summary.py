import os
import asyncio
import telegram
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from config import config
from api_manager import APIManager
from db_manager import DBManager
from data_processor import DataProcessor

# .env 파일 로드 (로컬 실행 시 환경변수 주입)
load_dotenv()

# GitHub Secrets에서 환경변수로 주입받을 값들
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
FIREBASE_EMAIL = os.environ.get("FIREBASE_EMAIL")
FIREBASE_PASSWORD = os.environ.get("FIREBASE_PASSWORD")

async def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("텔레그램 토큰 또는 채팅 ID가 설정되지 않았습니다.")
        return
    
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode='Markdown')

def main():
    if not FIREBASE_EMAIL or not FIREBASE_PASSWORD:
        print("Firebase 계정 정보가 설정되지 않았습니다.")
        return

    print("1. 초기화 및 로그인 중...")
    db_manager = DBManager(config['projectId'], config['apiKey'])
    api_manager = APIManager()
    data_processor = DataProcessor()

    try:
        auth_result = db_manager.login(FIREBASE_EMAIL, FIREBASE_PASSWORD)
        id_token = auth_result['idToken']
    except Exception as e:
        print(f"로그인 실패: {e}")
        return

    print("2. 시장 데이터 수집 중...")
    usd, jpy, cny, brl, _ = api_manager.fetch_exchange_rates()
    usd = usd or 0.0
    jpy = jpy or 0.0
    cny = cny or 0.0
    brl = brl or 0.0
    
    gold_prices = api_manager.get_detailed_gold_prices(usd)
    indices = api_manager.fetch_market_indices()
    upbit_usdt, _ = api_manager.get_upbit_price("USDT")

    print("3. 포트폴리오 데이터 계산 중...")
    data = db_manager.fetch_portfolio(id_token)
    docs = data.get('documents', [])
    
    # GUI 없이 데이터 처리만 수행
    items, f_total, all_total, invest_total, _ = data_processor.process_portfolio_data(
        docs, usd, jpy, cny, brl, gold_prices, api_manager
    )

    # 히스토리 및 통계 데이터 로드 (MDD, Peak 계산용)
    history_resp = db_manager.fetch_history(id_token)
    history_docs = history_resp.get('documents', [])
    history_cache = []
    for doc in history_docs:
        date_id = doc['name'].split('/')[-1]
        f = doc.get('fields', {})
        def get_val(field):
            v = f.get(field, {})
            return float(v.get('doubleValue', v.get('integerValue', 0)))
        history_cache.append({
            "date": date_id,
            "f_asset": get_val('financial_asset'),
            "t_asset": get_val('total_asset') or get_val('asset_value'),
            "deposit": get_val('net_deposit')
        })
    history_cache.sort(key=lambda x: x['date'])

    # 수익률 및 증감률 계산
    roi, growth = data_processor.calculate_metrics(f_total, all_total, history_cache)

    stats_resp = db_manager.get_stats(id_token)
    stats_fields = stats_resp.get('fields', {})
    val = stats_fields.get('peak_financial_asset', {})
    peak_f_asset = float(val.get('doubleValue', val.get('integerValue', 0)))
    ts = stats_fields.get('updated_at', {}).get('timestampValue', '')
    peak_date = ts[:10].replace("-", "") if ts else "-"

    # Peak 갱신 여부 확인 및 MDD 계산
    is_new_peak, adjusted_current = data_processor.check_peak_update(f_total, peak_f_asset, peak_date, history_cache)
    display_peak = adjusted_current if is_new_peak else peak_f_asset
    display_peak_date = datetime.now().strftime("%Y%m%d") if is_new_peak else peak_date
    mdd_val, mdd_pct = data_processor.calculate_mdd(f_total, display_peak, display_peak_date, history_cache)

    print("4. 메시지 작성 중...")
    # KST 시간 설정 (UTC+9)
    KST = timezone(timedelta(hours=9))
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    
    message = f"📊 **Daily Asset Summary**\n`{now_str}`\n\n"
    
    growth_str = f" ({growth:+.2f}%)" if growth is not None else ""
    message += f"💰 **총 자산**: ₩{all_total:,.0f}{growth_str}\n"
    
    roi_str = f" ({roi:+.2f}%)" if roi is not None else ""
    message += f"🏦 **금융 자산**: ₩{f_total:,.0f}{roi_str}\n"
    
    message += f"📈 **투자 자산**: ₩{invest_total:,.0f}\n"
    peak_date_str = display_peak_date[2:] if len(display_peak_date) == 8 else display_peak_date
    message += f"🏆 **MAX-{peak_date_str}**: ₩{display_peak:,.0f}\n"
    message += f"📉 **DD**: ₩{mdd_val:,.0f} ({mdd_pct:.2f}%)\n"
    
    message += "\n━━━━━━━━━━━━━━\n"
    message += "💱 **환율 정보**\n"
    message += f"🇺🇸 USD: {usd:,.2f}원\n"
    message += f"🇯🇵 JPY: {jpy*100:,.2f}원\n"
    message += f"🇨🇳 CNY: {cny:,.2f}원\n"
    message += f"🇧🇷 BRL: {brl:,.2f}원\n"
    
    message += "\n━━━━━━━━━━━━━━\n"
    message += "📊 **차익 거래**\n"
    
    # 김치 프리미엄
    kimp_str = "N/A"
    if upbit_usdt and usd > 0:
        kimp = ((upbit_usdt / usd) - 1) * 100
        kimp_str = f"{kimp:+.2f}%"
    message += f"🇰🇷 코인 김프: {kimp_str}\n"

    # 금 프리미엄/스프레드
    g = gold_prices
    if g.get('int_spot', 0) > 0:
        krx_prem = ((g.get('krx_spot', 0) / g['int_spot']) - 1) * 100 if g.get('krx_spot') else 0
        iau_prem = ((g.get('iau_krw_g', 0) / g['int_spot']) - 1) * 100 if g.get('iau_krw_g') else 0
        spread = ((g.get('int_future', 0) / g['int_spot']) - 1) * 100 if g.get('int_future') else 0
        
        message += f"🥇 KRX 금프: {krx_prem:+.2f}%\n"
        message += f"🇺🇸 IAU 금프: {iau_prem:+.2f}%\n"
        message += f"⚖️ 금 스프레드: {spread:+.2f}%\n"
    
    message += "\n🌍 **주요 지수**\n"
    # 표시 순서: KOSPI, KOSDAQ, S&P500, NASDAQ, Nikkei225, HangSeng, VIX, US10Y
    target_indices = ["KOSPI", "KOSDAQ", "S&P500", "NASDAQ", "Nikkei225", "HangSeng", "VIX", "US10Y"]
    for name in target_indices:
        if name in indices:
            val, chg = indices[name]
            # 이모지: 상승(🔺), 하락(🔹), 보합(➖)
            icon = "🔺" if chg > 0 else "🔹" if chg < 0 else "➖"
            # VIX와 US10Y는 등락률 대신 값만 강조하거나 다르게 표시할 수도 있음
            if name in ["VIX", "US10Y"]:
                 message += f"{icon} {name}: {val:,.2f} ({chg:+.2f}%)\n"
            else:
                 message += f"{icon} {name}: {val:,.2f} ({chg:+.2f}%)\n"

    # 자산 상세 메시지 작성
    assets_message = "💼 **Asset Details**\n"
    last_main = ""
    for item in items:
        if item['qty'] <= 0:
            continue

        if item['main'] != last_main:
            assets_message += f"\n📂 **{item['main']}**\n"
            last_main = item['main']
        
        diff = f" ({item['diff_str']})" if item.get('diff_str') else ""
        
        qty = item['qty']
        qty_str = f"{int(qty):,}" if qty == int(qty) else f"{qty:,.4f}".rstrip('0').rstrip('.')
        assets_message += f"• {item['name']}: {qty_str} / ₩{item['row_val']:,.0f}{diff}\n"

    print("5. 텔레그램 전송...")
    asyncio.run(send_telegram_message(message))
    asyncio.run(send_telegram_message(assets_message))
    print("완료!")

if __name__ == "__main__":
    main()
