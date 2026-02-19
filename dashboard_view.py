from PyQt6.QtWidgets import QWidget, QGridLayout, QGroupBox, QVBoxLayout, QLabel
from datetime import datetime

class DashboardView(QWidget):
    def __init__(self):
        super().__init__()
        self.last_indices = {}
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout(self)
        
        # 1. 거래 지표
        gb1 = QGroupBox("💱 거래 지표")
        l1 = QVBoxLayout(gb1)
        self.rate_label = QLabel("환율 로딩 중...")
        l1.addWidget(self.rate_label)
        self.indices_label = QLabel("주요 지수 로딩 중...")
        self.indices_label.setWordWrap(True)
        l1.addWidget(self.indices_label)
        layout.addWidget(gb1, 0, 0)
        
        # 2. 차익 거래
        gb2 = QGroupBox("📊 차익 거래")
        l2 = QVBoxLayout(gb2)
        self.kimp_label = QLabel("코인 김치 프리미엄: -")
        self.krx_prem_label = QLabel("KRX 금 프리미엄: -")
        self.iau_prem_label = QLabel("IAU 금 프리미엄: -")
        self.gold_spread_label = QLabel("국제 금 스프레드: -")
        l2.addWidget(self.kimp_label)
        l2.addWidget(self.krx_prem_label)
        l2.addWidget(self.iau_prem_label)
        l2.addWidget(self.gold_spread_label)
        layout.addWidget(gb2, 0, 1)
        
        # 3. 현물 지표
        gb3 = QGroupBox("🏅 현물 지표")
        l3 = QVBoxLayout(gb3)
        self.gold_label = QLabel("금 시세 로딩 중...")
        l3.addWidget(self.gold_label)
        layout.addWidget(gb3, 0, 2)
        
        # 4. 자산 요약
        gb4 = QGroupBox("💰 자산 요약")
        l4 = QGridLayout(gb4)
        self.total_label = QLabel("금융자산: -")
        self.roi_label = QLabel("수익률: -")
        self.all_total_label = QLabel("총자산: -")
        self.growth_label = QLabel("증감률: -")
        self.max_date_label = QLabel("MAX -")
        self.max_val_label = QLabel("₩0")
        self.mdd_val_label = QLabel("DD액: -")
        self.mdd_pct_label = QLabel("DD%: -")
        
        l4.addWidget(self.total_label, 0, 0)
        l4.addWidget(self.roi_label, 1, 0)
        l4.addWidget(self.all_total_label, 2, 0)
        l4.addWidget(self.growth_label, 3, 0)
        l4.addWidget(self.max_date_label, 0, 1)
        l4.addWidget(self.max_val_label, 1, 1)
        l4.addWidget(self.mdd_val_label, 2, 1)
        l4.addWidget(self.mdd_pct_label, 3, 1)
        layout.addWidget(gb4, 0, 3)

    def update_market_indicators(self, usd_rate, jpy_rate, brl_rate, gold_info, upbit_usdt, indices=None):
        # 환율 업데이트
        if usd_rate and jpy_rate:
            self.rate_label.setText(f"실시간 환율: $ {usd_rate:,.2f} / ¥ {jpy_rate*100:,.2f} / R$ {brl_rate:,.2f}")
        else:
            self.rate_label.setText("⚠️ 환율 로드 실패")

        # 금 시세 업데이트
        if gold_info:
            def fmt(val): return f"{val:,.0f}원" if val > 0 else "로드 실패"
            
            gold_text = (
                f"국제 금 현물(g): {fmt(gold_info.get('int_spot', 0))}\n"
                f"국제 금 선물(g): {fmt(gold_info.get('int_future', 0))}\n"
                f"KRX 금 현물(g): {fmt(gold_info.get('krx_spot', 0))}\n"
                f"IAU 금 현물(g): {fmt(gold_info.get('iau_krw_g', 0))}\n"
                f"국내 금 현물(g): {fmt(gold_info.get('domestic_spot', 0))}"
            )
            self.gold_label.setText(gold_text)

        # 주요 지수 업데이트
        if indices:
            self.last_indices = indices
            lines = []
            groups = [
                ["KOSPI", "KOSDAQ"], 
                ["S&P500", "NASDAQ"], 
                ["VIX", "US10Y"]
            ]
            
            for group in groups:
                parts = []
                for name in group:
                    if name in indices:
                        price, chg = indices[name]
                        if price > 0:
                            # 상승: 빨강, 하락: 파랑, 보합: 회색
                            color = "#FF6B6B" if chg > 0 else "#4DABF7" if chg < 0 else "#e0e0e0"
                            parts.append(f"{name} <span style='color:{color}'>{price:,.2f} ({chg:+.2f}%)</span>")
                if parts:
                    lines.append("  |  ".join(parts))
            
            if lines:
                self.indices_label.setText("<br>".join(lines))
            else:
                self.indices_label.setText("지수 데이터 없음")
        else:
            self.indices_label.setText("지수 로드 실패")

        # 프리미엄 업데이트
        kimp_text = "코인 김치 프리미엄: 로드 실패"
        kimp_style = ""
        
        if upbit_usdt and usd_rate and upbit_usdt > 0 and usd_rate > 0:
            kimp_ratio = ((upbit_usdt / usd_rate) - 1) * 100
            kimp_text = f"코인 김치 프리미엄: {kimp_ratio:+.2f}%"
            
            if kimp_ratio < 0.5:
                kimp_style = "color: #4DABF7; font-weight: bold;"
            elif kimp_ratio > 6.0:
                kimp_style = "color: #FF6B6B; font-weight: bold;"
        
        self.kimp_label.setText(kimp_text)
        self.kimp_label.setStyleSheet(kimp_style)

        krx_text = "KRX 금 프리미엄: -"
        iau_text = "IAU 금 프리미엄: -"
        spread_text = "국제 금 스프레드: -"
        krx_style = ""
        iau_style = ""
        spread_style = ""

        if gold_info:
            g = gold_info
            if g.get('int_spot', 0) > 0 and g.get('krx_spot', 0) > 0:
                krx_prem = ((g['krx_spot'] / g['int_spot']) - 1) * 100
                iau_prem = ((g.get('iau_krw_g', 0) / g['int_spot']) - 1) * 100 if g.get('iau_krw_g', 0) > 0 else 0
                gold_spread = ((g['int_future'] / g['int_spot']) - 1) * 100 if g.get('int_future', 0) > 0 else 0
                
                krx_text = f"KRX 금 프리미엄: {krx_prem:+.2f}%"
                iau_text = f"IAU 금 프리미엄: {iau_prem:+.2f}%"
                spread_text = f"국제 금 스프레드: {gold_spread:+.2f}%"

                if krx_prem > 3.0:
                    krx_style = "color: #FF6B6B; font-weight: bold;"
                elif krx_prem <= 0.3:
                    krx_style = "color: #4DABF7; font-weight: bold;"

                if iau_prem > 1.0:
                    iau_style = "color: #FF6B6B; font-weight: bold;"
                elif iau_prem < -1.0:
                    iau_style = "color: #4DABF7; font-weight: bold;"

                if gold_spread > 3.0:
                    spread_style = "color: #FF6B6B; font-weight: bold;"
                elif gold_spread <= 0.3:
                    spread_style = "color: #4DABF7; font-weight: bold;"

        self.krx_prem_label.setText(krx_text)
        self.krx_prem_label.setStyleSheet(krx_style)
        self.iau_prem_label.setText(iau_text)
        self.iau_prem_label.setStyleSheet(iau_style)
        self.gold_spread_label.setText(spread_text)
        self.gold_spread_label.setStyleSheet(spread_style)

    def update_asset_summary(self, f_total, all_total, roi, growth, peak_val, peak_date, mdd_val, mdd_pct):
        self.total_label.setText(f"금융자산: {f_total:,.0f}")
        self.all_total_label.setText(f"총자산: {all_total:,.0f}")
        self.roi_label.setText(f"수익률: {roi:+.2f}%" if roi is not None else "수익률: 기록 없음")
        self.growth_label.setText(f"증감률: {growth:+.2f}%" if growth is not None else "증감률: 기록 없음")
        self.max_date_label.setText(f"MAX - {peak_date}")
        self.max_val_label.setText(f"₩{peak_val:,.0f}")
        self.mdd_val_label.setText(f"DD액: {mdd_val:,.0f}")
        self.mdd_pct_label.setText(f"DD%: {mdd_pct:.2f}%")

    def update_totals_only(self, f_total, all_total):
        self.total_label.setText(f"금융자산: {f_total:,.0f}")
        self.all_total_label.setText(f"총자산: {all_total:,.0f}")

    def get_summary_info(self, usd_rate, jpy_rate, brl_rate, gold_info):
        def clean(txt, prefix): return txt.replace(prefix, "").strip()
        summary = {
            "기록시간": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "USD환율": f"{usd_rate:,.2f}" if usd_rate else "0.00",
            "JPY환율(100엔)": f"{jpy_rate*100:,.2f}" if jpy_rate else "0.00",
            "BRL환율": f"{brl_rate:,.2f}" if brl_rate else "0.00",
            "국제금(현물)": f"{gold_info.get('int_spot', 0):,.0f}",
            "국제금(선물)": f"{gold_info.get('int_future', 0):,.0f}",
            "KRX금(현물)": f"{gold_info.get('krx_spot', 0):,.0f}",
            "국내금(현물)": f"{gold_info.get('domestic_spot', 0):,.0f}",
            "김치프리미엄": clean(self.kimp_label.text(), "코인 김치 프리미엄: "),
            "KRX금프리미엄": clean(self.krx_prem_label.text(), "KRX 금 프리미엄: "),
            "IAU금프리미엄": clean(self.iau_prem_label.text(), "IAU 금 프리미엄: "),
            "국제금스프레드": clean(self.gold_spread_label.text(), "국제 금 스프레드: "),
            "금융자산합계": clean(self.total_label.text(), "금융자산: "),
            "총자산(부동산포함)": clean(self.all_total_label.text(), "총자산: "),
            "투자수익률(전월비)": clean(self.roi_label.text(), "수익률: "),
            "자산증감률(전월비)": clean(self.growth_label.text(), "증감률: "),
            "전고점(Max)": clean(self.max_val_label.text(), "₩"),
            "전고점날짜": clean(self.max_date_label.text(), "MAX - "),
            "DD": clean(self.mdd_val_label.text(), "DD액: "),
            "DD%": clean(self.mdd_pct_label.text(), "DD%: ")
        }

        if self.last_indices:
            order = ["KOSPI", "KOSDAQ", "S&P500", "NASDAQ", "VIX", "US10Y"]
            for name in order:
                if name in self.last_indices:
                    price, chg = self.last_indices[name]
                    summary[name] = f"{price:,.2f} ({chg:+.2f}%)"
        
        return summary