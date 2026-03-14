'use client'

interface ChartViewProps {
  allocHtml: string
  historyHtml: string
}

export default function ChartView({ allocHtml, historyHtml }: ChartViewProps) {
  if (!allocHtml && !historyHtml) {
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
        <iframe
          srcDoc={allocHtml}
          className="w-full h-full"
          style={{ border: 'none', background: '#1e1e2e' }}
          title="자산 배분"
        />
      </div>

      {/* 히스토리 차트 */}
      <div className="rounded-lg overflow-hidden" style={{ flex: 6, border: '1px solid #2d2d3f' }}>
        <iframe
          srcDoc={historyHtml}
          className="w-full h-full"
          style={{ border: 'none', background: '#1e1e2e' }}
          title="자산 추이"
        />
      </div>
    </div>
  )
}
