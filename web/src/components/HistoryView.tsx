'use client'

import { useState } from 'react'

export interface HistoryRow {
  date: string
  f_asset: number
  t_asset: number
  deposit: number
  profit: number
  roi: number
  growth: number
  memo: string
}

export interface YearlyRow {
  year: string
  deposit: string
  profit: string
  roi: string
  roi_val: number | null
}

interface HistoryViewProps {
  rows: HistoryRow[]
  yearly: YearlyRow[]
  currentFAsset: number
  currentTAsset: number
  onSave: (date: string, fAsset: number, tAsset: number, deposit: number, memo: string) => Promise<void>
  onDelete: (date: string) => Promise<void>
}

function fmt(n: number) {
  return n.toLocaleString('ko-KR', { maximumFractionDigits: 0 })
}
function signFmt(n: number) {
  return (n >= 0 ? '+' : '') + n.toLocaleString('ko-KR', { maximumFractionDigits: 0 })
}

function roiColor(roi: number | null): string {
  if (roi === null) return '#e0e0e0'
  if (roi < 0) return '#FF6B6B'
  if (roi >= 10) return '#4DABF7'
  return '#e0e0e0'
}

export default function HistoryView({ rows, yearly, currentFAsset, currentTAsset, onSave, onDelete }: HistoryViewProps) {
  const today = new Date().toISOString().slice(0, 10)
  const defaultForm = {
    date: today,
    f_asset: currentFAsset > 0 ? String(Math.round(currentFAsset)) : '',
    t_asset: currentTAsset > 0 ? String(Math.round(currentTAsset)) : '',
    deposit: '',
    memo: '',
  }
  const [form, setForm] = useState(defaultForm)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  function selectRow(row: HistoryRow) {
    setForm({
      date:    row.date,
      f_asset: String(Math.round(row.f_asset)),
      t_asset: String(Math.round(row.t_asset)),
      deposit: String(Math.round(row.deposit)),
      memo:    row.memo,
    })
    setIsEditing(true)
  }

  function parseForm() {
    return {
      date: form.date,
      fAsset: parseFloat(form.f_asset.replace(/,/g, '')) || 0,
      tAsset: parseFloat(form.t_asset.replace(/,/g, '')) || 0,
      deposit: parseFloat(form.deposit.replace(/,/g, '')) || 0,
      memo: form.memo,
    }
  }

  async function handleNew() {
    const { date, fAsset, tAsset, deposit, memo } = parseForm()
    setSaving(true)
    await onSave(date, fAsset, tAsset, deposit, memo)
    setForm(defaultForm)
    setIsEditing(false)
    setSaving(false)
  }

  async function handleUpdate() {
    const { date, fAsset, tAsset, deposit, memo } = parseForm()
    setSaving(true)
    await onSave(date, fAsset, tAsset, deposit, memo)
    setSaving(false)
  }

  async function handleDelete() {
    if (!form.date) return
    if (!confirm(`[${form.date}] 기록을 삭제하시겠습니까?`)) return
    setSaving(true)
    await onDelete(form.date)
    setForm(defaultForm)
    setIsEditing(false)
    setSaving(false)
  }

  const inp = (key: keyof typeof form, placeholder = '') => (
    <input
      value={form[key]}
      onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
      placeholder={placeholder}
      className="rounded px-2 py-1 text-sm w-full"
      style={{ background: '#121212', border: '1px solid #3d3d4f', color: '#e0e0e0', minHeight: '36px' }}
    />
  )

  return (
    <div className="flex gap-2 h-full">
      {/* ─── 왼쪽 70% ─── */}
      <div className="flex flex-col gap-2" style={{ flex: 7 }}>
        {/* 히스토리 테이블 */}
        <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid #2d2d3f' }}>
          <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#2d2d3f', color: '#9e9e9e' }}>
                {['날짜','금융자산','총자산','순입고','투자손익','수익률','증감율','비고'].map(h => (
                  <th key={h} className="px-3 py-2 text-center whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => {
                const profitColor = row.profit < 0 ? '#FF6B6B' : row.roi >= 2 ? '#4DABF7' : '#e0e0e0'
                const selected = form.date === row.date
                return (
                  <tr key={row.date} onClick={() => selectRow(row)} className="cursor-pointer"
                    style={{ background: selected ? '#2a2a4a' : idx % 2 === 0 ? '#1e1e2e' : '#22223a' }}>
                    <td className="px-3 py-2 text-center">{row.date}</td>
                    <td className="px-3 py-2 text-right">{fmt(row.f_asset)}</td>
                    <td className="px-3 py-2 text-right">{fmt(row.t_asset)}</td>
                    <td className="px-3 py-2 text-right"
                      style={{ color: row.deposit < 0 ? '#FF6B6B' : '#e0e0e0' }}>
                      {signFmt(row.deposit)}
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: profitColor, fontWeight: row.roi >= 2 ? 'bold' : 'normal' }}>
                      {signFmt(row.profit)}
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: profitColor, fontWeight: row.roi >= 2 ? 'bold' : 'normal' }}>
                      {row.roi !== 0 ? `${row.roi >= 0 ? '+' : ''}${row.roi.toFixed(2)}%` : '-'}
                    </td>
                    <td className="px-3 py-2 text-right" style={{ color: '#e0e0e0' }}>
                      {row.growth !== 0 ? `${row.growth >= 0 ? '+' : ''}${row.growth.toFixed(2)}%` : '-'}
                    </td>
                    <td className="px-3 py-2" style={{ color: '#9e9e9e' }}>{row.memo}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* 편집 폼 */}
        <div className="rounded-lg p-3" style={{ background: '#1e1e2e', border: '1px solid #2d2d3f' }}>
          <div className="text-xs font-bold mb-2" style={{ color: '#9e9e9e' }}>📝 기록 관리</div>
          <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
            <div><label className="text-xs" style={{ color: '#9e9e9e' }}>날짜</label>{inp('date')}</div>
            <div><label className="text-xs" style={{ color: '#9e9e9e' }}>금융자산</label>{inp('f_asset', '0')}</div>
            <div><label className="text-xs" style={{ color: '#9e9e9e' }}>총자산</label>{inp('t_asset', '0')}</div>
            <div><label className="text-xs" style={{ color: '#9e9e9e' }}>순입고</label>{inp('deposit', '0')}</div>
            <div className="col-span-2"><label className="text-xs" style={{ color: '#9e9e9e' }}>비고</label>{inp('memo', '비고')}</div>
          </div>
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={handleDelete} disabled={!isEditing || saving}
              className="px-4 py-2 rounded text-sm font-bold"
              style={{ background: '#C62828', color: 'white', minHeight: '40px', opacity: !isEditing ? 0.5 : 1 }}>
              🗑️ 삭제
            </button>
            <button onClick={handleNew} disabled={saving}
              className="px-4 py-2 rounded text-sm font-bold"
              style={{ background: '#1565C0', color: 'white', minHeight: '40px' }}>
              {saving ? '저장 중...' : '➕ 신규등록'}
            </button>
            <button onClick={handleUpdate} disabled={!isEditing || saving}
              className="px-4 py-2 rounded text-sm font-bold"
              style={{ background: '#1976D2', color: 'white', minHeight: '40px', opacity: !isEditing ? 0.5 : 1 }}>
              {saving ? '저장 중...' : '✏️ 수정'}
            </button>
          </div>
        </div>
      </div>

      {/* ─── 오른쪽 30% — 연도별 수익률 ─── */}
      <div className="rounded-lg overflow-hidden" style={{ flex: 3, border: '1px solid #2d2d3f' }}>
        <div className="px-3 py-2 text-xs font-bold text-center"
          style={{ background: '#2d2d3f', color: '#9e9e9e' }}>
          연도별 수익률
        </div>
        <div className="overflow-auto" style={{ height: 'calc(100% - 36px)' }}>
          <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#2d2d3f', color: '#9e9e9e' }}>
                {['연도','순입고','투자수익','수익률'].map(h => (
                  <th key={h} className="px-2 py-1 text-center whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {yearly.map((y, idx) => (
                <tr key={y.year} style={{ background: idx % 2 === 0 ? '#1e1e2e' : '#22223a' }}>
                  <td className="px-2 py-1.5 text-center">{y.year}</td>
                  <td className="px-2 py-1.5 text-right" style={{ color: y.deposit.startsWith('-') ? '#FF6B6B' : '#e0e0e0' }}>{y.deposit}</td>
                  <td className="px-2 py-1.5 text-right" style={{ color: y.profit.startsWith('-') ? '#FF6B6B' : '#e0e0e0' }}>{y.profit}</td>
                  <td className="px-2 py-1.5 text-right font-bold" style={{ color: roiColor(y.roi_val) }}>{y.roi}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
