'use client'

import { useEffect, useRef } from 'react'

declare global {
  interface Window {
    Plotly?: {
      react: (el: HTMLElement, data: unknown[], layout: Record<string, unknown>, config?: Record<string, unknown>) => void
    }
  }
}

interface PlotlyFigure {
  data: unknown[]
  layout: Record<string, unknown>
}

interface ChartViewProps {
  allocHtml: string
  historyHtml: string
  allocJson?: PlotlyFigure | null
  historyJson?: PlotlyFigure | null
}

function PlotlyChart({ figure, title, style }: { figure: PlotlyFigure; title: string; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || !figure) return

    const render = () => {
      if (window.Plotly && ref.current) {
        window.Plotly.react(ref.current, figure.data, {
          ...figure.layout,
          autosize: true,
        }, { responsive: true, displayModeBar: false })
      }
    }

    // Plotly가 아직 로드되지 않았을 수 있으므로 폴링
    if (window.Plotly) {
      render()
    } else {
      const interval = setInterval(() => {
        if (window.Plotly) {
          clearInterval(interval)
          render()
        }
      }, 100)
      return () => clearInterval(interval)
    }
  }, [figure])

  return <div ref={ref} className="w-full h-full" title={title} style={style} />
}

export default function ChartView({ allocHtml, historyHtml, allocJson, historyJson }: ChartViewProps) {
  if (!allocHtml && !historyHtml && !allocJson && !historyJson) {
    return (
      <div className="flex items-center justify-center h-40" style={{ color: '#9e9e9e' }}>
        차트 데이터 로딩 중...
      </div>
    )
  }

  return (
    <div className="flex gap-2" style={{ height: '70vh' }}>
      {/* 자산 배분 트리맵 */}
      <div className="rounded-lg overflow-hidden" style={{ flex: 4, border: '1px solid #2d2d3f' }}>
        {allocJson ? (
          <PlotlyChart figure={allocJson} title="자산 배분" style={{ background: '#1e1e2e' }} />
        ) : (
          <iframe
            srcDoc={allocHtml}
            className="w-full h-full"
            style={{ border: 'none', background: '#1e1e2e' }}
            title="자산 배분"
          />
        )}
      </div>

      {/* 히스토리 차트 */}
      <div className="rounded-lg overflow-hidden" style={{ flex: 6, border: '1px solid #2d2d3f' }}>
        {historyJson ? (
          <PlotlyChart figure={historyJson} title="자산 추이" style={{ background: '#1e1e2e' }} />
        ) : (
          <iframe
            srcDoc={historyHtml}
            className="w-full h-full"
            style={{ border: 'none', background: '#1e1e2e' }}
            title="자산 추이"
          />
        )}
      </div>
    </div>
  )
}
