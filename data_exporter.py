import csv
import os
import sys
import zipfile
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox

class DataExporter:
    @staticmethod
    def export_csv(parent, summary_info, asset_columns, asset_data, history_columns, history_data, yearly_yield_data, analysis_metrics=None):
        today_str = datetime.now().strftime("%Y%m%d")
        # 실행 파일 위치를 기준으로 경로 설정
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        
        created_files = []

        try:
            # 1. Summary (자산 요약 정보)
            f_name = "Summary.csv"
            path = os.path.join(base_dir, f_name)
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["항목", "값"])
                for key, val in summary_info.items():
                    writer.writerow([key, val])
            created_files.append(f_name)
            
            # 2. Assets (자산 상세 목록)
            f_name = "Assets.csv"
            path = os.path.join(base_dir, f_name)
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                if asset_data:
                    writer = csv.DictWriter(f, fieldnames=asset_columns)
                    writer.writeheader()
                    writer.writerows(asset_data)
            created_files.append(f_name)
            
            # 3. History (월별 히스토리)
            f_name = "History.csv"
            path = os.path.join(base_dir, f_name)
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                if history_data:
                    writer = csv.DictWriter(f, fieldnames=history_columns)
                    writer.writeheader()
                    writer.writerows(history_data)
            created_files.append(f_name)
            
            # 4. Yearly Yield (연도별 수익률)
            f_name = "Yearly.csv"
            path = os.path.join(base_dir, f_name)
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                if yearly_yield_data:
                    fieldnames = ["연도", "순입고", "투자수익", "수익률"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(yearly_yield_data)
            created_files.append(f_name)

            # 5. Analysis (분석 지표)
            if analysis_metrics:
                f_name = "Analysis.csv"
                path = os.path.join(base_dir, f_name)
                with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    matrix = analysis_metrics.get('matrix')
                    if matrix:
                        # 매트릭스 구조 내보내기 (6개월 단위 확장)
                        periods = ['All', '6M', '1Y', '1.5Y', '2Y', '2.5Y', '3Y', '3.5Y', '4Y', '4.5Y', '5Y']
                        p_labels = [
                            "전체 (All)", "최근 6개월", "최근 1년", "최근 1.5년", 
                            "최근 2년", "최근 2.5년", "최근 3년", "최근 3.5년", 
                            "최근 4년", "최근 4.5년", "최근 5년"
                        ]
                        
                        writer.writerow(["지표 (Metric)"] + p_labels)
                        
                        def get_val(metric, source, period, is_pct=True):
                            if period not in matrix: return "-"
                            data = matrix[period].get(source)
                            if not data: return "-"
                            val = data.get(metric)
                            if val is None: return "-"
                            return f"{val*100:.2f}%" if is_pct else f"{val:.2f}"

                        metrics_map = [
                            ("CAGR", 'cagr', True),
                            ("MDD", 'mdd', True),
                            ("Sharpe Ratio", 'sharpe', False),
                            ("Sortino Ratio", 'sortino', False),
                            ("Risk-Free Rate", 'rf_avg', True)
                        ]

                        for label, key, is_pct in metrics_map:
                            # 내 포트폴리오 행
                            writer.writerow([f"{label} (내 포트)"] + [get_val(key, 'user', p, is_pct) for p in periods])
                            # 벤치마크 행들 (무위험 수익률은 공통 지표이므로 제외)
                            if key != 'rf_avg':
                                writer.writerow([f"{label} (SPY)"] + [get_val(key, 'spy', p, is_pct) for p in periods])
                                writer.writerow([f"{label} (KOSPI)"] + [get_val(key, 'kospi', p, is_pct) for p in periods])

                        # 연환산 변동성 (SPY/KOSPI만 — 포트폴리오는 월간 데이터라 제외)
                        writer.writerow(["연환산 변동성 (SPY)"]   + [get_val('vol', 'spy',   p, True) for p in periods])
                        writer.writerow(["연환산 변동성 (KOSPI)"] + [get_val('vol', 'kospi', p, True) for p in periods])
                    else:
                        # 기존 포맷 (Fallback)
                        writer.writerow(["지표", "내 포트폴리오", "S&P 500 (SPY)", "KOSPI"])
                        def fmt(val, is_pct=True):
                            if val is None: return "-"
                            return f"{val*100:.2f}%" if is_pct else f"{val:.2f}"
                        writer.writerow([
                            "CAGR", 
                            fmt(analysis_metrics.get('cagr_user'), True), 
                            fmt(analysis_metrics.get('cagr_spy'), True),
                            fmt(analysis_metrics.get('cagr_kospi'), True)
                        ])
                        # ... (기타 기존 로직)
                
                created_files.append(f_name)
            
            # Zip creation
            zip_name = f"{today_str}.zip"
            zip_path = os.path.join(base_dir, zip_name)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_name in created_files:
                    file_path = os.path.join(base_dir, file_name)
                    if os.path.exists(file_path):
                        zf.write(file_path, arcname=file_name)
                
                # rule.md (또는 Rule.md) 파일이 존재하면 ZIP에 추가
                for rule_name in ["rule.md", "Rule.md"]:
                    rule_path = os.path.join(base_dir, rule_name)
                    if os.path.exists(rule_path):
                        zf.write(rule_path, arcname=rule_name)
                        break
            
            # Cleanup CSV files
            for file_name in created_files:
                file_path = os.path.join(base_dir, file_name)
                if os.path.exists(file_path):
                    os.remove(file_path)

            msg = f"파일이 압축되어 저장되었습니다:\n{zip_name}"
            QMessageBox.information(parent, "성공", msg)
            
        except Exception as e:
            QMessageBox.critical(parent, "오류", f"파일 저장 중 오류 발생: {e}")