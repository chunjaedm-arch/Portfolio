'use client'

import { useState } from 'react'

export interface AssetItem {
  name: string
  main: string
  sub: string
  ticker: string
  qty: number
  usd: number
  jpy: number
  krw: number
  row_val: number
  target_ratio: number
  note: string
  rebal_amt: number
  diff_str: string
  diff_color: 'red' | 'blue' | null
  unit_price_str: string
  market_status: string
  updated_at: string
}

interface EditForm {
  name: string
  대분류: string
  소분류: string
  티커: string
  수량: string
  '금액(달러)': string
  '금액(엔)': string
  '금액(원)': string
  목표비중: string
  비고: string
}

const EMPTY_FORM: EditForm = {
  name: '', 대분류: '', 소분류: '', 티커: '',
  수량: '', '금액(달러)': '', '금액(엔)': '', '금액(원)': '',
  목표비중: '', 비고: '',
}

function fmt(n: number) {
  return n.toLocaleString('ko-KR', { maximumFractionDigits: 0 })
}

function rowTextColor(item: AssetItem): string {
  if (item.qty <= 0) return '#666'
  return '#e0e0e0'
}

function rebalColor(amt: number): string {
  if (amt > 0) return '#4DABF7'
  if (amt < 0) return '#FF6B6B'
  return '#e0e0e0'
}

function diffColor(item: AssetItem): string {
  if (item.diff_color === 'red')  return '#FF6B6B'
  if (item.diff_color === 'blue') return '#4DABF7'
  return '#e0e0e0'
}

interface AssetViewProps {
  items: AssetItem[]
  onSave: (name: string, form: EditForm) => Promise<void>
  onDelete: (name: string) => Promise<void>
}

export default function AssetView({ items, onSave, onDelete }: AssetViewProps) {
  const [form, setForm] = useState<EditForm>(EMPTY_FORM)
  const [isEditing, setIsEditing] = useState(false)
  const [saving, setSaving] = useState(false)

  function selectRow(item: AssetItem) {
    setForm({
      name:        item.name,
      대분류:      item.main,
      소분류:      item.sub,
      티커:        item.ticker,
      수량:        item.qty > 0 ? String(item.qty) : '',
      '금액(달러)': item.usd > 0 ? String(item.usd) : '',
      '금액(엔)':   item.jpy > 0 ? String(item.jpy) : '',
      '금액(원)':   item.krw > 0 ? String(item.krw) : '',
      목표비중:    item.target_ratio > 0 ? String(item.target_ratio) : '',
      비고:        item.note,
    })
    setIsEditing(true)
  }

  async function handleNew() {
    if (!form.name) return
    setSaving(true)
    await onSave(form.name, form)
    setForm(EMPTY_FORM)
    setIsEditing(false)
    setSaving(false)
  }

  async function handleUpdate() {
    if (!form.name) return
    setSaving(true)
    await onSave(form.name, form)
    setSaving(false)
  }

  async function handleDelete() {
    if (!form.name) return
    if (!confirm(`"${form.name}"을(를) 삭제하시겠습니까?`)) return
    setSaving(true)
    await onDelete(form.name)
    setForm(EMPTY_FORM)
    setIsEditing(false)
    setSaving(false)
  }

  const inp = (key: keyof EditForm, placeholder = '') => (
    <input
      value={form[key]}
      onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
      placeholder={placeholder}
      className="rounded px-2 py-1 text-sm w-full"
      style={{ background: '#121212', border: '1px solid #3d3d4f', color: '#e0e0e0', minHeight: '36px' }}
    />
  )

  return (
    <div className="flex flex-col gap-2">
      {/* ─── 자산 테이블 ─── */}
      <div className="overflow-x-auto rounded-lg" style={{ border: '1px solid #2d2d3f' }}>
        <table className="w-full text-xs" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#2d2d3f', color: '#9e9e9e' }}>
              {['대분류','소분류','품명','리밸런싱','평가액','전일대비','단가','수량','티커','목표비중','비고'].map(h => (
                <th key={h} className="px-2 py-2 text-center whitespace-nowrap">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => (
              <tr
                key={item.name}
                onClick={() => selectRow(item)}
                className="cursor-pointer"
                style={{
                  background: form.name === item.name ? '#2a2a4a' : idx % 2 === 0 ? '#1e1e2e' : '#22223a',
                  color: rowTextColor(item),
                  minHeight: '44px',
                }}
              >
                <td className="px-2 py-2 text-center whitespace-nowrap">{item.main}</td>
                <td className="px-2 py-2 text-center whitespace-nowrap">{item.sub}</td>
                <td className="px-2 py-2 whitespace-nowrap font-medium">{item.name}</td>
                <td className="px-2 py-2 text-right whitespace-nowrap"
                  style={{ color: item.rebal_amt !== 0 ? rebalColor(item.rebal_amt) : '#666', fontWeight: item.rebal_amt > 0 ? 'bold' : 'normal' }}>
                  {item.rebal_amt !== 0 ? fmt(item.rebal_amt) : ''}
                </td>
                <td className="px-2 py-2 text-right whitespace-nowrap">{fmt(item.row_val)}</td>
                <td className="px-2 py-2 text-right whitespace-nowrap"
                  style={{ color: diffColor(item) }}>
                  {item.diff_str}
                </td>
                <td className="px-2 py-2 text-right whitespace-nowrap">{item.unit_price_str}</td>
                <td className="px-2 py-2 text-right whitespace-nowrap">
                  {item.qty > 0 ? item.qty.toLocaleString('ko-KR', { maximumFractionDigits: 2 }) : ''}
                </td>
                <td className="px-2 py-2 text-center whitespace-nowrap" style={{ color: '#9e9e9e' }}>{item.ticker}</td>
                <td className="px-2 py-2 text-right whitespace-nowrap">
                  {item.target_ratio > 0 ? `${item.target_ratio.toFixed(2)}%` : ''}
                </td>
                <td className="px-2 py-2" style={{ color: '#9e9e9e', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ─── 편집 폼 ─── */}
      <div className="rounded-lg p-3" style={{ background: '#1e1e2e', border: '1px solid #2d2d3f' }}>
        <div className="text-xs font-bold mb-2" style={{ color: '#9e9e9e' }}>
          자산 상세 입력 {form.name && <span style={{ color: '#4DABF7' }}>— {form.name}</span>}
        </div>

        <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>품명</label>{inp('name', '품명')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>대분류</label>{inp('대분류', '대분류')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>소분류</label>{inp('소분류', '소분류')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>티커</label>{inp('티커', '티커')}</div>

          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>수량</label>{inp('수량', '0')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>금액(달러)</label>{inp('금액(달러)', '0')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>금액(엔)</label>{inp('금액(엔)', '0')}</div>
          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>금액(원)</label>{inp('금액(원)', '0')}</div>

          <div><label className="text-xs" style={{ color: '#9e9e9e' }}>목표비중(%)</label>{inp('목표비중', '0')}</div>
          <div className="col-span-3"><label className="text-xs" style={{ color: '#9e9e9e' }}>비고</label>{inp('비고', '비고')}</div>
        </div>

        <div className="flex justify-end gap-2 mt-3">
          <button
            onClick={() => { setForm(EMPTY_FORM); setIsEditing(false) }}
            className="px-4 py-2 rounded text-sm"
            style={{ background: '#2d2d3f', color: '#9e9e9e', minHeight: '40px' }}
          >
            초기화
          </button>
          <button
            onClick={handleDelete}
            disabled={!isEditing || saving}
            className="px-4 py-2 rounded text-sm font-bold"
            style={{ background: '#C62828', color: 'white', minHeight: '40px', opacity: !isEditing ? 0.5 : 1 }}
          >
            🗑️ 삭제
          </button>
          <button
            onClick={handleNew}
            disabled={!form.name || saving}
            className="px-4 py-2 rounded text-sm font-bold"
            style={{ background: '#1565C0', color: 'white', minHeight: '40px', opacity: !form.name ? 0.5 : 1 }}
          >
            {saving ? '저장 중...' : '➕ 신규등록'}
          </button>
          <button
            onClick={handleUpdate}
            disabled={!isEditing || saving}
            className="px-4 py-2 rounded text-sm font-bold"
            style={{ background: '#2E7D32', color: 'white', minHeight: '40px', opacity: !isEditing ? 0.5 : 1 }}
          >
            {saving ? '저장 중...' : '✏️ 수정'}
          </button>
        </div>
      </div>
    </div>
  )
}
