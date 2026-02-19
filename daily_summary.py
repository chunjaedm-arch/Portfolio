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
    usd, jpy, brl, _ = api_manager.fetch_exchange_rates()
    usd = usd or 0.0
    jpy = jpy or 0.0
    brl = brl or 0.0
    
    gold_prices = api_manager.get_detailed_gold_prices(usd)
    indices = api_manager.fetch_market_indices()

    print("3. 포트폴리오 데이터 계산 중...")
    data = db_manager.fetch_portfolio(id_token)
    docs = data.get('documents', [])
    
    # GUI 없이 데이터 처리만 수행
    items, f_total, all_total, invest_total, _ = data_processor.process_portfolio_data(
        docs, usd, jpy, brl, gold_prices, api_manager
    )

    print("4. 메시지 작성 중...")
    # KST 시간 설정 (UTC+9)
    KST = timezone(timedelta(hours=9))
    now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M')
    
    message = f"📊 **Daily Asset Summary**\n`{now_str}`\n\n"
    
    message += f"💰 **총 자산**: ₩{all_total:,.0f}\n"
    message += f"🏦 **금융 자산**: ₩{f_total:,.0f}\n"
    message += f"📈 **투자 자산**: ₩{invest_total:,.0f}\n"
    
    message += "\n━━━━━━━━━━━━━━\n"
    message += "💱 **환율 정보**\n"
    message += f"🇺🇸 USD: {usd:,.2f}원\n"
    message += f"🇯🇵 JPY: {jpy*100:,.2f}원\n"
    
    message += "\n🌍 **주요 지수**\n"
    # 표시 순서: KOSPI, KOSDAQ, S&P500, NASDAQ, VIX, US10Y
    target_indices = ["KOSPI", "KOSDAQ", "S&P500", "NASDAQ", "VIX", "US10Y"]
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

    print("5. 텔레그램 전송...")
    asyncio.run(send_telegram_message(message))
    print("완료!")

if __name__ == "__main__":
    main()
