import yfinance as yf
import requests
from bs4 import BeautifulSoup
import re
import FinanceDataReader as fdr
from datetime import datetime, timedelta

class APIManager:
    def fetch_exchange_rates(self):
        try:
            usd_df = yf.Ticker("USDKRW=X").history(period="1d")
            jpy_df = yf.Ticker("JPYKRW=X").history(period="1d")
            cny_df = yf.Ticker("CNYKRW=X").history(period="1d")
            brl_df = yf.Ticker("BRLKRW=X").history(period="1d")

            if not usd_df.empty and not jpy_df.empty and not cny_df.empty and not brl_df.empty:
                usd_rate = float(usd_df['Close'].iloc[-1])
                raw_jpy = float(jpy_df['Close'].iloc[-1])
                jpy_rate = raw_jpy / 100 if raw_jpy > 50 else raw_jpy
                cny_rate = float(cny_df['Close'].iloc[-1])
                brl_rate = float(brl_df['Close'].iloc[-1])
                return usd_rate, jpy_rate, cny_rate, brl_rate, "yfinance"
        except Exception as e:
            print(f"yfinance 환율 로드 실패 (FinanceDataReader로 재시도): {e}")

        # 2차 시도: FinanceDataReader (Fallback)
        return self._fetch_exchange_rates_fdr()

    def _fetch_exchange_rates_fdr(self):
        try:
            # 최근 7일 데이터 조회 (주말/휴일 고려)
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            usd_df = fdr.DataReader('USD/KRW', start_date)
            jpy_df = fdr.DataReader('JPY/KRW', start_date)
            cny_df = fdr.DataReader('CNY/KRW', start_date)
            brl_df = fdr.DataReader('BRL/KRW', start_date)

            if not usd_df.empty and not jpy_df.empty and not cny_df.empty and not brl_df.empty:
                usd_rate = float(usd_df['Close'].iloc[-1])
                raw_jpy = float(jpy_df['Close'].iloc[-1])
                
                # JPY 처리 (100엔 단위일 경우 1엔 단위로 변환)
                jpy_rate = raw_jpy / 100 if raw_jpy > 50 else raw_jpy
                cny_rate = float(cny_df['Close'].iloc[-1])
                brl_rate = float(brl_df['Close'].iloc[-1])
                return usd_rate, jpy_rate, cny_rate, brl_rate, "FinanceDataReader"
        except Exception as e:
            print(f"FinanceDataReader 환율 로드 실패: {e}")
        
        return None, None, None, None, None

    def fetch_market_indices(self):
        indices = {
            "KOSPI": "^KS11",
            "KOSDAQ": "^KQ11",
            "NASDAQ": "^NDX",
            "S&P500": "^GSPC",
            "Nikkei225": "^N225",
            "HangSeng": "^HSI",
            "VIX": "^VIX",
            "US10Y": "^TNX"
        }
        results = {}
        for name, ticker in indices.items():
            try:
                t = yf.Ticker(ticker)
                
                # fast_info를 사용하여 명시적으로 전일 종가(previous_close)와 현재가(last_price) 사용
                info = t.fast_info
                curr = info.last_price
                prev = info.previous_close
                
                if curr is not None and prev is not None and prev != 0:
                    chg = ((curr - prev) / prev) * 100
                    results[name] = (curr, chg)
                else:
                    hist = t.history(period="5d")
                    if len(hist) >= 2:
                        curr = float(hist['Close'].iloc[-1])
                        prev = float(hist['Close'].iloc[-2])
                        chg = ((curr - prev) / prev) * 100
                        results[name] = (curr, chg)
                    elif len(hist) == 1:
                        results[name] = (float(hist['Close'].iloc[-1]), 0.0)
            except Exception as e:
                print(f"Index {name} fetch failed: {e}")
        return results

    def get_upbit_price(self, symbol):
        market = f"KRW-{symbol.upper()}"
        url = f"https://api.upbit.com/v1/ticker?markets={market}"
        try:
            res = requests.get(url, timeout=5)
            data = res.json()
            # 업비트 API는 성공 시 리스트, 실패 시 에러 정보가 담긴 딕셔너리를 반환함
            if isinstance(data, list) and len(data) > 0:
                return float(data[0]['trade_price']), float(data[0]['prev_closing_price'])
        except Exception as e:
            print(f"업비트 {symbol} 시세 로드 실패: {e}")
            return None, None
        return None, None

    def get_detailed_gold_prices(self, usd_rate):
        results = {'int_spot': 0.0, 'int_future': 0.0, 'krx_spot': 0.0, 'domestic_spot': 0.0, 'int_spot_usd': 0.0, 'iau_usd': 0.0, 'iau_krw_g': 0.0}
        
        if not usd_rate:
            return results
            
        oz_to_g = 31.1034768
        headers = {'User-Agent': 'Mozilla/5.0'}

        try:
            future_data = yf.download("GC=F", period="5d", progress=False)
            if not future_data.empty:
                last_val = future_data['Close'].dropna().iloc[-1]
                last_price = float(last_val.iloc[0] if hasattr(last_val, 'iloc') else last_val)
                results['int_future'] = (last_price / oz_to_g) * usd_rate
        except Exception as e:
            print(f"금 선물 수집 오류: {e}")

        try:
            spot_url = "https://www.cnbc.com/quotes/XAU="
            res = requests.get(spot_url, headers=headers, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            container = soup.select_one("span.QuoteStrip-lastPrice")
            price_text = container.get_text(strip=True) if container else ""
            clean_price = re.sub(r'[^\d.]', '', price_text)
            if clean_price:
                results['int_spot_usd'] = float(clean_price)
                results['int_spot'] = (results['int_spot_usd'] / oz_to_g) * usd_rate
        except Exception as e:
            print(f"금 현물 수집 오류: {e}")

        try:
            iau_ticker = yf.Ticker("IAU")
            iau_hist = iau_ticker.history(period="1d")
            if not iau_hist.empty:
                results['iau_usd'] = float(iau_hist['Close'].iloc[-1])
                # IAU 1주 ≈ 0.5843g
                results['iau_krw_g'] = (results['iau_usd'] * usd_rate) / 0.5843
        except Exception as e:
            print(f"IAU 시세 수집 오류: {e}")

        results['krx_spot'] = self._get_krx_gold_price() or 0.0
        results['domestic_spot'] = self._get_domestic_gold_price() or 0.0

        return results
    
    def _get_krx_gold_price(self):
        url = "https://m.stock.naver.com/marketindex/metals/M04020000"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            for s in soup.find_all("strong"):
                if "원/g" in s.get_text():
                    return float(re.sub(r'[^0-9]', '', s.get_text()))
        except: return None
        return None
    
    def _get_domestic_gold_price(self):
        url = "https://m.stock.naver.com/marketindex/metals/CMDT_GD"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            res = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            price_tag = soup.select_one("strong[class*='DetailInfo_price']")
            if price_tag:
                return float(re.sub(r'[^0-9.]', '', price_tag.get_text()))
        except: return None
        return None