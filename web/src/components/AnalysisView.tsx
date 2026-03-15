'use client'

import { useState } from 'react'

export interface AnalysisMetrics {
  cagr_user: number;    cagr_spy: number;    cagr_kospi: number
  mdd_user: number;     mdd_spy: number;     mdd_kospi: number
  sharpe_user: number;  sharpe_spy: number;  sharpe_kospi: number
  sortino_user: number; sortino_spy: number; sortino_kospi: number
  rf_avg: number
}

export interface MatrixRow {
  label: string
  [period: string]: string
}

interface AnalysisViewProps {
  metrics: AnalysisMetrics | null
  chartHtml: string
  matrix: MatrixRow[]
}

const PERIODS = ['All','2M','3M','6M','1Y','1.5Y','2Y','2.5Y','3Y','3.5Y','4Y','4.5Y','5Y']

function MetricCard({ title, userVal, spyVal, kospiVal, isPct = true }:
  { title: string; userVal: number; spyVal: number; kospiVal: number; isPct?: boolean }) {
  const fmt = (v: number) => isPct ? `${(v * 100) >= 0 ? '+' : ''}${(v * 100).toFixed(2)}%` : v.toFixed(2)
  const color = userVal > spyVal ? '#4DABF7' : userVal < spyVal ? '#FF6B6B' : '#ffffff'

  return (
    <div className="rounded-lg px-4 py-3 flex flex-col items-center gap-1"
      style={{ background: '#2d2d3f', flex: 1 }}>
      <div className="text-xs text-center" style={{ color: '#9e9e9e' }}>{title}</div>
      <div className="text-lg font-bold" style={{ color }}>{fmt(userVal)}</div>
      <div className="text-xs" style={{ color: '#888' }}>vs SPY: {fmt(spyVal)}</div>
      <div className="text-xs" style={{ color: '#888' }}>vs KOSPI: {fmt(kospiVal)}</div>
    </div>
  )
}

export default function AnalysisView({ metrics, chartHtml, matrix }: AnalysisViewProps) {
  const [page, setPage] = useState<'dashboard' | 'matrix'>('dashboard')

  const btnStyle = (active: boolean) => ({
    background: active ? '#1976D2' : '#2d2d3f',
    color: active ? 'white' : '#9e9e9e',
    border: 'none', borderRadius: '4px', padding: '6px 16px',
    cursor: 'pointer', fontWeight: 'bold' as const, minHeight: '36px',
  })

  return (
    <div className="flex flex-col gap-2">
      {/* 정보 */}
      <div className="text-xs text-right" style={{ color: '#666' }}>
        ※ 분석 기준: 금융자산 (현금 포함, 부동산 제외) | 1년 미만 기간은 단순 누적 수익률로 표시
      </div>

      {/* 탭 */}
      <div className="flex gap-2">
        <button style={btnStyle(page === 'dashboard')} onClick={() => setPage('dashboard')}>📊 대시보드</button>
        <button style={btnStyle(page === 'matrix')}    onClick={() => setPage('matrix')}>📋 상세 매트릭스</button>
      </div>

      {page === 'dashboard' && (
        <>
          {/* 핵심 지표 카드 */}
          {metrics && (
            <div className="flex gap-2">
              <MetricCard title="CAGR (연평균/누적)"
                userVal={metrics.cagr_user} spyVal={metrics.cagr_spy} kospiVal={metrics.cagr_kospi} />
              <MetricCard title="MDD (최대낙폭)"
                userVal={metrics.mdd_user} spyVal={metrics.mdd_spy} kospiVal={metrics.mdd_kospi} />
              <MetricCard title="Sharpe Ratio"
                userVal={metrics.sharpe_user} spyVal={metrics.sharpe_spy} kospiVal={metrics.sharpe_kospi} isPct={false} />
              <MetricCard title="Sortino Ratio"
                userVal={metrics.sortino_user} spyVal={metrics.sortino_spy} kospiVal={metrics.sortino_kospi} isPct={false} />
              {/* RF Rate 카드 */}
              <div className="rounded-lg px-4 py-3 flex flex-col items-center gap-1"
                style={{ background: '#2d2d3f', flex: 1 }}>
                <div className="text-xs text-center" style={{ color: '#9e9e9e' }}>Risk-Free Rate</div>
                <div className="text-lg font-bold" style={{ color: '#fff' }}>
                  {(metrics.rf_avg * 100).toFixed(2)}%
                </div>
                <div className="text-xs" style={{ color: '#888' }}>기간 평균</div>
              </div>
            </div>
          )}

          {/* 누적수익률 + DD 차트 */}
          <div className="rounded-lg overflow-hidden" style={{ height: '55vh', border: '1px solid #2d2d3f' }}>
            {chartHtml ? (
              <iframe srcDoc={chartHtml} className="w-full h-full"
                style={{ border: 'none', background: '#1e1e2e' }} title="분석 차트" />
            ) : (
              <div className="flex items-center justify-center h-full" style={{ color: '#9e9e9e' }}>
                차트 로딩 중...
              </div>
            )}
          </div>
        </>
      )}

      {page === 'matrix' && (
        <div className="overflow-auto rounded-lg" style={{ border: '1px solid #2d2d3f', maxHeight: '70vh' }}>
          <table className="text-xs" style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr style={{ background: '#2d2d3f', color: '#9e9e9e', position: 'sticky', top: 0, zIndex: 1 }}>
                <th className="px-3 py-2 text-left whitespace-nowrap">지표</th>
                {PERIODS.map(p => (
                  <th key={p} className="px-3 py-2 text-center whitespace-nowrap">{p === 'All' ? '전체' : `최근 ${p}`}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.map((row, idx) => (
                <tr key={row.label} style={{ background: idx % 2 === 0 ? '#1e1e2e' : '#22223a' }}>
                  <td className="px-3 py-1.5 whitespace-nowrap" style={{ color: '#9e9e9e' }}>{row.label}</td>
                  {PERIODS.map(p => (
                    <td key={p} className="px-3 py-1.5 text-right whitespace-nowrap"
                      style={{ color: '#e0e0e0' }}>
                      {row[p] ?? '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
