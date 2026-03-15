'use client'

export interface IndexData {
  price: number
  change: number
}

export interface GoldInfo {
  int_spot: number
  int_future: number
  krx_spot: number
  iau_krw_g: number
  domestic_spot: number
}

export interface DashboardData {
  usd_rate: number
  jpy_rate: number
  cny_rate: number
  brl_rate: number
  indices: Record<string, IndexData>
  gold_info: GoldInfo
  kimp: number | null
  krx_prem: number | null
  iau_prem: number | null
  gold_spread: number | null
  f_total: number
  all_total: number
  roi: number | null
  growth: number | null
  peak_val: number
  peak_date: string
  mdd_val: number
  mdd_pct: number
}


// ─── 색상 헬퍼 ───────────────────────────────────────────
function indexColor(change: number) {
  if (change > 0) return '#FF6B6B'
  if (change < 0) return '#4DABF7'
  return '#e0e0e0'
}

function premColor(val: number, highThresh: number, lowThresh: number) {
  if (val > highThresh) return '#FF6B6B'
  if (val < lowThresh)  return '#4DABF7'
  return '#e0e0e0'
}

function fmt(n: number, decimals = 0) {
  return n.toLocaleString('ko-KR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function signStr(n: number) {
  return n >= 0 ? `+${n.toFixed(2)}%` : `${n.toFixed(2)}%`
}

// ─── 패널 래퍼 ───────────────────────────────────────────
function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg p-3 flex flex-col gap-2"
      style={{ background: '#1e1e2e', border: '1px solid #2d2d3f', minWidth: 0 }}>
      <div className="text-xs font-bold mb-1" style={{ color: '#9e9e9e' }}>{title}</div>
      {children}
    </div>
  )
}

// ─── 1. 거래 지표 ─────────────────────────────────────────
function TradingPanel({ data }: { data: DashboardData }) {
  const INDEX_GROUPS = [
    ['KOSPI', 'KOSDAQ'],
    ['S&P500', 'NASDAQ'],
    ['Nikkei225', 'HangSeng'],
    ['VIX', 'US10Y'],
  ]

  return (
    <Panel title="💱 거래 지표">
      {/* 환율 */}
      <div className="text-xs" style={{ color: '#b0c4de' }}>
        <span className="mr-3">$ {data.usd_rate.toLocaleString('ko-KR', { minimumFractionDigits: 2 })}</span>
        <span className="mr-3">¥100 {(data.jpy_rate * 100).toLocaleString('ko-KR', { minimumFractionDigits: 2 })}</span>
        <span className="mr-3">CN¥ {data.cny_rate.toFixed(2)}</span>
        <span>R$ {data.brl_rate.toFixed(2)}</span>
      </div>

      {/* 주요 지수 */}
      <div className="flex flex-col gap-1">
        {INDEX_GROUPS.map((group, gi) => (
          <div key={gi} className="flex gap-3">
            {group.map(name => {
              const idx = data.indices[name]
              if (!idx) return null
              const col = indexColor(idx.change)
              return (
                <span key={name} className="text-xs">
                  <span style={{ color: '#9e9e9e' }}>{name} </span>
                  <span style={{ color: col, fontWeight: 'bold' }}>
                    {idx.price.toLocaleString('ko-KR', { minimumFractionDigits: 2 })}
                  </span>
                  <span style={{ color: col }}> ({signStr(idx.change)})</span>
                </span>
              )
            })}
          </div>
        ))}
      </div>
    </Panel>
  )
}

// ─── 2. 차익 거래 ─────────────────────────────────────────
function ArbitragePanel({ data }: { data: DashboardData }) {
  const items = [
    {
      label: '코인 김치 프리미엄',
      val: data.kimp,
      color: data.kimp != null ? premColor(data.kimp, 6.0, 0.5) : '#9e9e9e',
    },
    {
      label: 'KRX 금 프리미엄',
      val: data.krx_prem,
      color: data.krx_prem != null ? premColor(data.krx_prem, 3.0, 0.3) : '#9e9e9e',
    },
    {
      label: 'IAU 금 프리미엄',
      val: data.iau_prem,
      color: data.iau_prem != null ? premColor(data.iau_prem, 1.0, -1.0) : '#9e9e9e',
    },
    {
      label: '국제 금 스프레드',
      val: data.gold_spread,
      color: data.gold_spread != null ? premColor(data.gold_spread, 3.0, 0.3) : '#9e9e9e',
    },
  ]

  return (
    <Panel title="📊 차익 거래">
      {items.map(({ label, val, color }) => (
        <div key={label} className="flex justify-between items-center text-xs">
          <span style={{ color: '#9e9e9e' }}>{label}</span>
          <span style={{ color, fontWeight: val != null ? 'bold' : 'normal' }}>
            {val != null ? signStr(val) : '-'}
          </span>
        </div>
      ))}
    </Panel>
  )
}

// ─── 3. 현물 지표 ─────────────────────────────────────────
function SpotPanel({ data }: { data: DashboardData }) {
  const g = data.gold_info
  const items = [
    { label: '국제 금 현물(g)', val: g.int_spot },
    { label: '국제 금 선물(g)', val: g.int_future },
    { label: 'KRX 금 현물(g)',  val: g.krx_spot },
    { label: 'IAU 금 현물(g)',  val: g.iau_krw_g },
    { label: '국내 금 현물(g)', val: g.domestic_spot },
  ]

  return (
    <Panel title="🏅 현물 지표">
      {items.map(({ label, val }) => (
        <div key={label} className="flex justify-between items-center text-xs">
          <span style={{ color: '#9e9e9e' }}>{label}</span>
          <span style={{ color: '#e0e0e0' }}>{val > 0 ? `${fmt(val, 1)}원` : '로드 실패'}</span>
        </div>
      ))}
    </Panel>
  )
}

// ─── 4. 자산 요약 ─────────────────────────────────────────
function AssetSummaryPanel({ data }: { data: DashboardData }) {
  const roiColor  = data.roi  != null ? (data.roi  >= 0 ? '#FF6B6B' : '#4DABF7') : '#9e9e9e'
  const growColor = data.growth != null ? (data.growth >= 0 ? '#FF6B6B' : '#4DABF7') : '#9e9e9e'

  return (
    <Panel title="💰 자산 요약">
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div>
          <span style={{ color: '#9e9e9e' }}>금융자산  </span>
          <span style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{fmt(data.f_total)}</span>
        </div>
        <div>
          <span style={{ color: '#9e9e9e' }}>수익률  </span>
          <span style={{ color: roiColor, fontWeight: 'bold' }}>
            {data.roi != null ? signStr(data.roi) : '-'}
          </span>
        </div>
        <div>
          <span style={{ color: '#9e9e9e' }}>총자산  </span>
          <span style={{ color: '#e0e0e0', fontWeight: 'bold' }}>{fmt(data.all_total)}</span>
        </div>
        <div>
          <span style={{ color: '#9e9e9e' }}>증감률  </span>
          <span style={{ color: growColor, fontWeight: 'bold' }}>
            {data.growth != null ? signStr(data.growth) : '-'}
          </span>
        </div>

        <div className="col-span-2 mt-1 border-t" style={{ borderColor: '#2d2d3f' }} />

        <div>
          <span style={{ color: '#9e9e9e' }}>MAX  </span>
          <span style={{ color: '#e0e0e0' }}>{data.peak_date}</span>
        </div>
        <div>
          <span style={{ color: '#e0e0e0' }}>₩{fmt(data.peak_val)}</span>
        </div>
        <div>
          <span style={{ color: '#9e9e9e' }}>DD액  </span>
          <span style={{ color: '#FF6B6B' }}>{fmt(data.mdd_val)}</span>
        </div>
        <div>
          <span style={{ color: '#9e9e9e' }}>DD%  </span>
          <span style={{ color: '#FF6B6B', fontWeight: 'bold' }}>{data.mdd_pct.toFixed(2)}%</span>
        </div>
      </div>
    </Panel>
  )
}

// ─── 로딩 스켈레톤 ───────────────────────────────────────
function LoadingPanel({ title }: { title: string }) {
  return (
    <Panel title={title}>
      <div className="flex items-center justify-center py-4 text-xs" style={{ color: '#9e9e9e' }}>
        로딩중...
      </div>
    </Panel>
  )
}

// ─── 메인 Dashboard ───────────────────────────────────────
export default function Dashboard({ data }: { data: DashboardData | null }) {
  if (data === null) {
    return (
      <div className="grid gap-2 p-2"
        style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <LoadingPanel title="💱 거래 지표" />
        <LoadingPanel title="📊 차익 거래" />
        <LoadingPanel title="🏅 현물 지표" />
        <LoadingPanel title="💰 자산 요약" />
      </div>
    )
  }

  return (
    <div className="grid gap-2 p-2"
      style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
      <TradingPanel    data={data} />
      <ArbitragePanel  data={data} />
      <SpotPanel       data={data} />
      <AssetSummaryPanel data={data} />
    </div>
  )
}
