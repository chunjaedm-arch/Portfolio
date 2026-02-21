from datetime import datetime, timezone
import yfinance as yf
import requests
from yahooquery import Ticker as YQTicker
import re

class DataProcessor:
    def __init__(self):
        self.order_list = [
            ("부동산", "주택"), ("현금", "예금"), ("현금", "예수금"),
            ("현금", "초단기채권ETF"), ("투자", "주식"), ("투자", "주식+채권대용"), 
            ("투자", "주식+현금흐름"), ("투자", "현금흐름"), ("투자", "채권"), ("투자", "원자재"),
            ("단타", "주식"), ("단타", "코인")
        ]

    def get_rank(self, m, s):
        m_c, s_c = (m.strip() if m else ""), (s.strip() if s else "")
        for i, (main, sub) in enumerate(self.order_list):
            if m_c == main and s_c == sub: 
                return i
        return 99

    def calculate_youth_account(self, data_text):
        try:
            if not data_text or ":" not in data_text:
                return None
            
            parts = data_text.split(':')
            if len(parts) < 3: 
                return None
            
            principal = float(parts[0])
            grant = float(parts[1])
            total_interest = float(parts[2])
        
            target_date = datetime(2028, 7, 10)
            start_date = datetime(2023, 7, 10)
            today = datetime.now()
        
            total_days = (target_date - start_date).days
            remaining_days = (target_date - today).days
            passed_days = total_days - remaining_days
        
            ratio = max(0, min(1, passed_days / total_days))
        
            current_value = principal + grant + (total_interest * ratio)
            return int(current_value)
        except Exception as e:
            print(f"도약계좌 계산 오류: {e}")
            return None

    # --- Refactored Helper Methods ---
    def _calculate_bond_value(self, note, qty, brl_rate, usd_rate, jpy_rate, cny_rate):
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (KST)"
        market_status = "Open"
        
        # 1. "구매단가:매수환율:현재가[:통화]" 형식 파싱
        if ":" in note:
            try:
                parts = note.split(':')
                if len(parts) >= 3:
                    p_match = re.search(r"[-+]?\d*\.\d+|\d+", parts[0])
                    r_match = re.search(r"[-+]?\d*\.\d+|\d+", parts[1])
                    c_match = re.search(r"[-+]?\d*\.\d+|\d+", parts[2])
                    
                    if p_match and r_match and c_match:
                        p_price = float(p_match.group())
                        p_rate = float(r_match.group())
                        c_price = float(c_match.group())

                        currency = "KRW"
                        if len(parts) >= 4:
                            currency = parts[3].strip().upper()
                        
                        current_rate = 1.0
                        if currency == "USD": current_rate = usd_rate
                        elif currency == "JPY": current_rate = jpy_rate
                        elif currency == "CNY": current_rate = cny_rate
                        elif currency == "BRL": current_rate = brl_rate
                        
                        krw_val = qty * c_price * current_rate
                        prev_unit_krw = p_price * p_rate
                        return True, krw_val, 0.0, 0.0, prev_unit_krw, updated_at, market_status
            except Exception:
                pass

        # 2. 기존 로직: 숫자 하나만 있는 경우 (단가로 간주)
        match = re.search(r"[-+]?\d*\.\d+|\d+", note)
        if match:
            unit_price = float(match.group())
            krw_val = qty * unit_price * brl_rate
            return True, krw_val, 0.0, 0.0, 0.0, updated_at, market_status
            
        return False, 0, 0, 0, 0, updated_at, market_status

    def _calculate_krx_gold(self, qty, gold_prices):
        current_p = gold_prices.get('krx_spot', 0)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (KST)"
        market_status = "Open" if 9 <= datetime.now().hour < 16 else "Closed"
        return True, current_p * qty, 0.0, 0.0, 0.0, updated_at, market_status

    def _calculate_crypto(self, ticker_upper, qty, api_manager):
        symbol = ticker_upper.replace("KRW=", "").replace("=UPBIT", "")
        current_p, prev_p = api_manager.get_upbit_price(symbol)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (KST)"
        if current_p is not None:
            market_status = "Open"
            return True, current_p * qty, 0.0, 0.0, prev_p, updated_at, market_status
        return False, 0, 0, 0, 0, updated_at, "n/a"

    def _calculate_stock(self, ticker, ticker_upper, qty):
        current_p = None
        prev_p = 0.0
        updated_at = "-"
        market_status = "n/a"
        
        # 1. [우선순위] yfinance로 가격 및 시장 상태 조회
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d", interval="5m", prepost=True)
            
            if not hist.empty:
                current_p = float(hist['Close'].iloc[-1])
                last_dt = hist.index[-1]
                updated_at = last_dt.strftime("%Y-%m-%d %H:%M") + f" ({last_dt.tzname() or ''})"

            if hasattr(stock, 'history_metadata') and isinstance(stock.history_metadata, dict):
                m_state = stock.history_metadata.get('marketState')
                if m_state:
                    m_state = m_state.upper()
                    if 'REGULAR' in m_state: market_status = 'Open'
                    elif 'CLOSED' in m_state: market_status = 'Closed'
                    elif 'PRE' in m_state: market_status = 'Pre-Market'
                    elif 'POST' in m_state: market_status = 'Post-Market'
                    else: market_status = m_state.capitalize()

            if market_status == "n/a":
                try:
                    m_state = stock.fast_info.market_state
                    if m_state:
                        m_state = m_state.upper()
                        if m_state in ['REGULAR', 'REGULARMARKET']: market_status = 'Open'
                        elif m_state in ['CLOSED', 'CLOSEDMARKET']: market_status = 'Closed'
                        elif 'PRE' in m_state: market_status = 'Pre-Market'
                        elif 'POST' in m_state: market_status = 'Post-Market'
                        else: market_status = m_state.capitalize()
                except: pass

            if market_status == "n/a" and 'last_dt' in locals():
                t_min = last_dt.hour * 60 + last_dt.minute
                if 240 <= t_min < 570:   market_status = "Pre-Market"
                elif 570 <= t_min < 960: market_status = "Open"
                elif 960 <= t_min < 1200: market_status = "Post-Market"
                else: market_status = "Closed"

            try: prev_p = stock.fast_info.previous_close
            except: prev_p = stock.info.get('previousClose', 0.0)

            if prev_p is None or prev_p == 0.0:
                hist_daily = stock.history(period="2d")
                if len(hist_daily) > 1:
                    prev_p = float(hist_daily['Close'].iloc[-2])
                elif not hist_daily.empty:
                    prev_p = float(hist_daily['Close'].iloc[-1])
        except Exception:
            current_p = None

        # 2. [Fallback] YahooQuery
        if current_p is None:
            try:
                yq_ticker = YQTicker(ticker)
                price_data = yq_ticker.price.get(ticker)
                
                if isinstance(price_data, dict):
                    if market_status == "n/a":
                        market_status = price_data.get('marketState', '').capitalize()
                    
                    market_state_upper = price_data.get('marketState', '').upper()
                    reg_price = price_data.get('regularMarketPrice')
                    pre_price = price_data.get('preMarketPrice')
                    post_price = price_data.get('postMarketPrice')
                    
                    yq_prev_p = price_data.get('regularMarketPreviousClose')
                    if yq_prev_p: prev_p = yq_prev_p

                    if 'PRE' in market_state_upper and pre_price: current_p = pre_price
                    elif 'POST' in market_state_upper and post_price: current_p = post_price
                    elif 'REGULAR' in market_state_upper and reg_price: current_p = reg_price
                    elif 'CLOSED' in market_state_upper and post_price: current_p = post_price
                    elif 'CLOSED' in market_state_upper and reg_price: current_p = reg_price

                    if current_p is not None:
                        print(f"[{ticker}] yfinance 실패 -> YahooQuery Fallback 사용: {current_p}")
                        if updated_at == "-" or updated_at == "n/a":
                            reg_time = price_data.get('regularMarketTime')
                            if reg_time:
                                dt = datetime.fromtimestamp(reg_time)
                                tz_short = price_data.get('exchangeTimezoneShortName', '')
                                updated_at = dt.strftime("%Y-%m-%d %H:%M") + f" ({tz_short})"
            except Exception:
                pass

        if current_p is None:
            print(f"[{ticker}] 시세 조회 실패 (데이터 없음)")
            return False, 0, 0, 0, 0, updated_at, market_status

        if ticker_upper.endswith((".KS", ".KQ")):
            return True, current_p * qty, 0.0, 0.0, prev_p, updated_at, market_status
        elif ticker_upper.endswith(".T"):
            return True, 0.0, 0.0, current_p * qty, prev_p, updated_at, market_status
        else:
            return True, 0.0, current_p * qty, 0.0, prev_p, updated_at, market_status

    # --- Main Router Method ---
    def calculate_asset_values(self, ticker, qty, note, gold_prices, api_manager, sub_category=None, usd_rate=0.0, jpy_rate=0.0, cny_rate=0.0, brl_rate=0.0):
        updated_at = "-"
        market_status = "n/a"
        
        if ticker == "도약":
            calculated_youth = self.calculate_youth_account(note)
            if calculated_youth is not None:
                updated_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (KST)"
                return True, float(calculated_youth), 0.0, 0.0, 0.0, updated_at, "n/a"

        if not ticker:
            return False, 0, 0, 0, 0, updated_at, market_status

        try:
            if sub_category == "채권":
                return self._calculate_bond_value(note, qty, brl_rate, usd_rate, jpy_rate, cny_rate)

            ticker_upper = ticker.upper()
            
            if ticker_upper == "KRX_GOLD":
                return self._calculate_krx_gold(qty, gold_prices)
            
            elif "UPBIT" in ticker_upper:
                return self._calculate_crypto(ticker_upper, qty, api_manager)

            else:
                return self._calculate_stock(ticker, ticker_upper, qty)

        except Exception as e:
            print(f"[{ticker}] 자산 계산 오류: {e}")
            return False, 0, 0, 0, 0, updated_at, market_status

    def get_price_display_info(self, ticker, qty, usd, jpy, krw, prev_close):
        price_str = ""
        diff_str = ""
        diff_color = None

        if ticker and qty > 0:
            current_unit_price = 0.0
            symbol = ""
            
            if usd > 0:
                current_unit_price = usd / qty
                symbol = "$"
            elif jpy > 0:
                current_unit_price = jpy / qty
                symbol = "¥"
            elif krw > 0:
                current_unit_price = krw / qty
                symbol = "₩"
            
            arrow = ""
            pct_str = ""
            if prev_close > 0 and current_unit_price > 0:
                diff = current_unit_price - prev_close
                pct = (diff / prev_close) * 100
                if diff > 0:
                    arrow = "▲"
                    diff_color = 'red'
                    pct_str = f"{abs(pct):.1f}%"
                elif diff < 0:
                    arrow = "▼"
                    diff_color = 'blue'
                    pct_str = f"{abs(pct):.1f}%"
            
            if symbol:
                diff_str = f"{pct_str}{arrow}"
                if symbol == "₩":
                    price_str = f"{symbol} {current_unit_price:,.0f}".strip()
                else:
                    price_str = f"{symbol} {current_unit_price:,.2f}".strip()
        
        return price_str, diff_str, diff_color

    def process_portfolio_data(self, docs, usd_rate, jpy_rate, cny_rate, brl_rate, gold_prices, api_manager):
        items = []
        f_total, all_total, invest_total = 0.0, 0.0, 0.0

        for doc in docs:
            fields = doc.get('fields', {})
            name = doc['name'].split('/')[-1]
            
            def val(k): return fields.get(k, {}).get('stringValue', "").strip()
            def nval(k): 
                v = fields.get(k, {})
                return float(v.get('doubleValue', v.get('integerValue', 0)))

            item = {
                "name": name, 
                "main": val("대분류"),
                "sub": val("소분류"), 
                "ticker": val("티커"),
                "qty": nval("수량"), 
                "usd": nval("금액(달러)"), 
                "jpy": nval("금액(엔)"), 
                "krw": nval("금액(원)"), 
                "target_ratio": nval("목표비중"),
                "note": val("비고")
            }

            success, c_krw, c_usd, c_jpy, c_prev, updated_at, market_status = self.calculate_asset_values(
                item['ticker'], item['qty'], item['note'], gold_prices, api_manager, item['sub'], usd_rate, jpy_rate, cny_rate, brl_rate
            )
            if success:
                item['krw'], item['usd'], item['jpy'] = c_krw, c_usd, c_jpy
                item['prev_close'] = c_prev
                item['updated_at'] = updated_at
                item['market_status'] = market_status
            else:
                item['prev_close'] = 0.0
                item['updated_at'] = updated_at
                item['market_status'] = market_status

            item['unit_price_str'], item['diff_str'], item['diff_color'] = self.get_price_display_info(
                item['ticker'], item['qty'], item['usd'], item['jpy'], item['krw'], item['prev_close']
            )

            item['row_val'] = (item['usd'] * usd_rate) + (item['jpy'] * jpy_rate) + item['krw']
            
            all_total += item['row_val']
            if item['main'] != "부동산": f_total += item['row_val']
            if item['main'] in ["투자", "단타"]: invest_total += item['row_val']
            
            items.append(item)

        items.sort(key=lambda x: self.get_rank(x['main'], x['sub']))
        
        return items, f_total, all_total, invest_total, "YahooQuery"

    def calculate_metrics(self, f_total, all_total, history_cache):
        """수익률(ROI) 및 자산 증감률(Growth) 계산"""
        roi = None
        growth = None
        
        if history_cache:
            last_record = history_cache[-1]
            prev_f_asset = last_record['f_asset']
            prev_t_asset = last_record['t_asset']
            
            if prev_t_asset > 0:
                growth = (all_total - prev_t_asset) / prev_t_asset * 100
            
            # 순입고(deposit)는 월중 변동이 있을 수 있으나, 현재 로직상 전월 확정분 기준 계산
            pending_deposit = 0
            if prev_f_asset > 0:
                profit = f_total - prev_f_asset - pending_deposit
                roi = (profit / prev_f_asset) * 100
        
        return roi, growth

    def get_deposit_sum_since(self, history_cache, base_date_str):
        """특정 날짜(YYYYMMDD) 이후의 순입고 합계 계산"""
        deposit_sum = 0
        if base_date_str and base_date_str != "-" and history_cache:
            for record in history_cache:
                # history date format: YYYY-MM-DD -> YYYYMMDD
                h_date = record['date'].replace("-", "")
                if h_date > base_date_str:
                    deposit_sum += record.get('deposit', 0)
        return deposit_sum

    def calculate_mdd(self, f_total, peak_f_asset, peak_date_str, history_cache):
        """DD(Drawdown) 계산 (순입고 보정 포함)"""
        mdd_val = 0
        mdd_pct = 0.0
        
        # 전고점 이후의 순입고 합계 가져오기
        deposit_sum = self.get_deposit_sum_since(history_cache, peak_date_str)

        if peak_f_asset > 0:
            # 현재 자산에서 전고점 이후 입금된 금액을 제외하고 실질 수익력 계산
            adjusted_current = f_total - deposit_sum
            dd_amount = peak_f_asset - adjusted_current
            
            # 실질적으로 전고점보다 낮을 때만 DD 표시 (수익 중이면 0)
            if dd_amount > 0:
                mdd_val = dd_amount
                mdd_pct = (dd_amount / peak_f_asset) * 100
        return mdd_val, mdd_pct

    def check_peak_update(self, current_f_total, peak_f_asset, peak_date_str, history_cache):
        """
        Peak(전고점) 갱신 여부 판단 로직
        결과: (갱신여부, 보정된 실질 가치)
        """
        # 전고점 이후의 순입고 합계 가져오기
        deposit_sum = self.get_deposit_sum_since(history_cache, peak_date_str)
        
        # 보정된 현재 가치 (입금액 제외)
        adjusted_current = current_f_total - deposit_sum
        
        # 보정된 가치가 기존 Peak를 넘었을 때만 갱신 인정
        is_new_peak = adjusted_current > peak_f_asset
        
        return is_new_peak, adjusted_current

    def get_peak_update_payload(self, current_f_total, custom_date_str=None):
        """Peak 갱신을 위한 페이로드 생성"""
        if custom_date_str and len(custom_date_str) == 8:
            peak_date = custom_date_str
            formatted_date = f"{peak_date[:4]}-{peak_date[4:6]}-{peak_date[6:]}"
            ts_val = f"{formatted_date}T00:00:00Z"
        else:
            peak_date = datetime.now().strftime("%Y%m%d")
            ts_val = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            
        payload = {"fields": {"peak_financial_asset": {"doubleValue": current_f_total}, "updated_at": {"timestampValue": ts_val}}}
        return peak_date, payload