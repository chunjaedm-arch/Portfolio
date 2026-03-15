'use client'

export type ActiveTab = 'asset' | 'history' | 'chart' | 'analysis'

const TABS: { id: ActiveTab; label: string }[] = [
  { id: 'asset', label: '📊 자산 관리' },
  { id: 'history', label: '📜 히스토리' },
  { id: 'chart', label: '📈 차트' },
  { id: 'analysis', label: '📉 분석' },
]

interface NavBarProps {
  activeTab: ActiveTab
  onTabChange: (tab: ActiveTab) => void
  onRefresh?: () => void
  onExport?: () => void
  status?: string
  source?: string
}

export default function NavBar({ activeTab, onTabChange, onRefresh, onExport, status, source }: NavBarProps) {
  return (
    <nav className="flex items-center gap-1 px-2 py-1.5 border-b"
      style={{ background: '#1a1a2e', borderColor: '#2d2d3f' }}>

      {/* 탭 버튼 */}
      {TABS.map(tab => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className="px-4 rounded text-sm font-medium transition-colors"
          style={{
            minHeight: '44px',
            background: activeTab === tab.id ? '#4DABF7' : 'transparent',
            color: activeTab === tab.id ? '#000' : '#e0e0e0',
          }}
        >
          {tab.label}
        </button>
      ))}

      <div className="flex-1" />

      {/* 상태/소스 표시 */}
      {source && (
        <span className="text-xs mr-2" style={{ color: '#9e9e9e' }}>
          {source}
        </span>
      )}
      {status && (
        <span className="text-xs mr-3" style={{ color: '#9e9e9e' }}>
          {status}
        </span>
      )}

      {/* 액션 버튼 */}
      <button
        onClick={onRefresh}
        className="px-3 rounded text-sm transition-colors hover:bg-white/10"
        style={{ minHeight: '44px', color: '#e0e0e0' }}
      >
        🔄 새로고침
      </button>
      <button
        onClick={onExport}
        className="px-3 rounded text-sm transition-colors hover:bg-white/10"
        style={{ minHeight: '44px', color: '#e0e0e0' }}
      >
        📥 내보내기
      </button>
      <button
        className="px-3 rounded text-sm transition-colors hover:bg-white/10"
        style={{ minHeight: '44px', color: '#888' }}
      >
        ⚙️
      </button>
    </nav>
  )
}
