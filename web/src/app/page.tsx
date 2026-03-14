'use client'

import { useState, useEffect, useCallback } from 'react'
import NavBar, { ActiveTab } from '@/components/NavBar'
import Dashboard, { DashboardData, MOCK_DATA } from '@/components/Dashboard'
import AssetView, { AssetItem } from '@/components/AssetView'
import HistoryView, { HistoryRow, YearlyRow } from '@/components/HistoryView'
import ChartView from '@/components/ChartView'
import AnalysisView, { AnalysisMetrics, MatrixRow } from '@/components/AnalysisView'

type FetchStatus = 'idle' | 'loading' | 'ok' | 'error'

export default function Home() {
  const [activeTab, setActiveTab]     = useState<ActiveTab>('asset')
  const [marketData, setMarketData]   = useState<DashboardData>(MOCK_DATA)
  const [status, setStatus]           = useState<FetchStatus>('idle')
  const [source, setSource]           = useState('목 데이터')
  const [lastUpdated, setLastUpdated] = useState('')

  // 자산 관리
  const [assetItems, setAssetItems]   = useState<AssetItem[]>([])
  const [assetLoaded, setAssetLoaded] = useState(false)

  // 히스토리
  const [historyRows, setHistoryRows]   = useState<HistoryRow[]>([])
  const [yearlyRows, setYearlyRows]     = useState<YearlyRow[]>([])
  const [historyLoaded, setHistoryLoaded] = useState(false)

  // 차트
  const [allocHtml, setAllocHtml]       = useState('')
  const [historyHtml, setHistoryHtml]   = useState('')
  const [chartsLoaded, setChartsLoaded] = useState(false)

  // 분석
  const [analysisMetrics, setAnalysisMetrics] = useState<AnalysisMetrics | null>(null)
  const [analysisChartHtml, setAnalysisChartHtml] = useState('')
  const [analysisMatrix, setAnalysisMatrix]   = useState<MatrixRow[]>([])
  const [analysisLoaded, setAnalysisLoaded]   = useState(false)

  // ─── 마켓 데이터 ────────────────────────────────────────
  const fetchMarket = useCallback(async () => {
    setStatus('loading')
    try {
      const raw = await (await fetch('/api/market')).json()
      setMarketData(prev => ({
        ...prev,
        usd_rate: raw.usd_rate, jpy_rate: raw.jpy_rate,
        cny_rate: raw.cny_rate, brl_rate: raw.brl_rate,
        indices: raw.indices,   gold_info: raw.gold_info,
        kimp: raw.kimp, krx_prem: raw.krx_prem,
        iau_prem: raw.iau_prem, gold_spread: raw.gold_spread,
      }))
      setSource(raw.source ?? '-')
      setLastUpdated(new Date().toLocaleTimeString('ko-KR'))
      setStatus('ok')
    } catch { setStatus('error') }
  }, [])

  // ─── 포트폴리오 ─────────────────────────────────────────
  const fetchPortfolio = useCallback(async () => {
    try {
      const raw = await (await fetch('/api/portfolio')).json()
      setAssetItems(raw.items ?? [])
      setAssetLoaded(true)
      setMarketData(prev => ({
        ...prev,
        f_total:   raw.f_total   ?? prev.f_total,
        all_total: raw.all_total ?? prev.all_total,
        roi:       raw.roi       ?? prev.roi,
        growth:    raw.growth    ?? prev.growth,
        peak_val:  raw.peak_val  ?? prev.peak_val,
        peak_date: raw.peak_date ?? prev.peak_date,
        mdd_val:   raw.mdd_val   ?? prev.mdd_val,
        mdd_pct:   raw.mdd_pct   ?? prev.mdd_pct,
      }))
      setLastUpdated(new Date().toLocaleTimeString('ko-KR'))
    } catch (e) { console.error(e) }
  }, [])

  // ─── 히스토리 ───────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      const raw = await (await fetch('/api/history')).json()
      setHistoryRows(raw.rows ?? [])
      setYearlyRows(raw.yearly ?? [])
      setHistoryLoaded(true)
    } catch (e) { console.error(e) }
  }, [])

  // ─── 차트 ───────────────────────────────────────────────
  const fetchCharts = useCallback(async () => {
    try {
      const raw = await (await fetch('/api/charts')).json()
      setAllocHtml(raw.alloc_html ?? '')
      setHistoryHtml(raw.history_html ?? '')
      setChartsLoaded(true)
    } catch (e) { console.error(e) }
  }, [])

  // ─── 분석 ───────────────────────────────────────────────
  const fetchAnalysis = useCallback(async () => {
    try {
      const raw = await (await fetch('/api/analysis')).json()
      setAnalysisMetrics(raw.metrics ?? null)
      setAnalysisChartHtml(raw.chart_html ?? '')
      setAnalysisMatrix(raw.matrix ?? [])
      setAnalysisLoaded(true)
    } catch (e) { console.error(e) }
  }, [])

  // ─── 탭 전환 시 지연 로드 ───────────────────────────────
  useEffect(() => {
    if (activeTab === 'history' && !historyLoaded) fetchHistory()
    if (activeTab === 'chart'   && !chartsLoaded)  fetchCharts()
    if (activeTab === 'analysis'&& !analysisLoaded) fetchAnalysis()
  }, [activeTab, historyLoaded, chartsLoaded, analysisLoaded, fetchHistory, fetchCharts, fetchAnalysis])

  // 최초 로드
  useEffect(() => {
    fetchMarket()
    fetchPortfolio()
  }, [fetchMarket, fetchPortfolio])

  // 새로고침
  const handleRefresh = useCallback(async () => {
    await fetchMarket()
    await fetchPortfolio()
    if (activeTab === 'history')  await fetchHistory()
    if (activeTab === 'chart')    await fetchCharts()
    if (activeTab === 'analysis') await fetchAnalysis()
  }, [fetchMarket, fetchPortfolio, fetchHistory, fetchCharts, fetchAnalysis, activeTab])

  // ─── 자산 CRUD ──────────────────────────────────────────
  async function handleAssetSave(name: string, form: Record<string, string>) {
    const res = await fetch(`/api/portfolio/${encodeURIComponent(name)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, fields: form }),
    })
    if (!res.ok) { alert('저장 실패'); return }
    await fetchPortfolio()
  }
  async function handleAssetDelete(name: string) {
    const res = await fetch(`/api/portfolio/${encodeURIComponent(name)}`, { method: 'DELETE' })
    if (!res.ok) { alert('삭제 실패'); return }
    await fetchPortfolio()
  }

  // ─── 히스토리 CRUD ──────────────────────────────────────
  async function handleHistorySave(date: string, fAsset: number, tAsset: number, deposit: number, memo: string) {
    const res = await fetch(`/api/history/${date}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, f_asset: fAsset, t_asset: tAsset, deposit, memo }),
    })
    if (!res.ok) { alert('저장 실패'); return }
    await fetchHistory()
  }
  async function handleHistoryDelete(date: string) {
    const res = await fetch(`/api/history/${date}`, { method: 'DELETE' })
    if (!res.ok) { alert('삭제 실패'); return }
    await fetchHistory()
  }

  const statusLabel =
    status === 'loading' ? '로딩 중...' :
    status === 'error'   ? '⚠️ 오류' :
    status === 'ok'      ? `업데이트: ${lastUpdated}` : '대기 중'

  return (
    <div className="flex flex-col min-h-screen" style={{ background: '#121212', color: '#e0e0e0' }}>
      <NavBar activeTab={activeTab} onTabChange={setActiveTab}
        onRefresh={handleRefresh} status={statusLabel} source={source} />

      <Dashboard data={marketData} />

      <div className="flex-1 p-2">
        {activeTab === 'asset' && (
          assetLoaded
            ? <AssetView items={assetItems} onSave={handleAssetSave} onDelete={handleAssetDelete} />
            : <Spinner />
        )}
        {activeTab === 'history' && (
          historyLoaded
            ? <HistoryView
                rows={historyRows} yearly={yearlyRows}
                currentFAsset={marketData.f_total} currentTAsset={marketData.all_total}
                onSave={handleHistorySave} onDelete={handleHistoryDelete} />
            : <Spinner />
        )}
        {activeTab === 'chart' && (
          chartsLoaded
            ? <ChartView allocHtml={allocHtml} historyHtml={historyHtml} />
            : <Spinner label="차트 생성 중... (시간이 걸릴 수 있습니다)" />
        )}
        {activeTab === 'analysis' && (
          analysisLoaded
            ? <AnalysisView metrics={analysisMetrics} chartHtml={analysisChartHtml} matrix={analysisMatrix} />
            : <Spinner label="분석 중... (SPY/KOSPI 데이터 로드 포함, 시간이 걸릴 수 있습니다)" />
        )}
      </div>
    </div>
  )
}

function Spinner({ label = '데이터 로딩 중...' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center h-40" style={{ color: '#9e9e9e' }}>
      <span className="text-sm">{label}</span>
    </div>
  )
}
