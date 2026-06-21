import type { SupplierItem } from '../../api/types'

export type DatePreset = '30d' | '90d' | '180d' | 'all'

interface HeaderProps {
  suppliers: SupplierItem[]
  selectedSupplierId: string
  onSupplierChange: (id: string) => void
  datePreset: DatePreset
  onDatePresetChange: (p: DatePreset) => void
  onRefresh: () => void
  loading: boolean
}

const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: '30d',  label: 'Last 30 days' },
  { value: '90d',  label: 'Last 90 days' },
  { value: '180d', label: 'Last 180 days' },
  { value: 'all',  label: 'All time' },
]

export function Header({
  suppliers,
  selectedSupplierId,
  onSupplierChange,
  datePreset,
  onDatePresetChange,
  onRefresh,
  loading,
}: HeaderProps) {
  return (
    <header className="bg-slate-900 text-white shadow-lg sticky top-0 z-30">
      <div className="max-w-screen-xl mx-auto px-6 py-4">
        {/* Top row */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-brand-500 text-lg font-bold tracking-tight">◈</span>
              <span className="text-lg font-semibold tracking-tight">Solvigo Sales Intelligence</span>
            </div>
            <p className="text-slate-400 text-xs mt-0.5">Supplier performance overview</p>
          </div>

          <button
            onClick={onRefresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-sm font-medium transition-colors disabled:opacity-50"
          >
            <span className={loading ? 'animate-spin inline-block' : 'inline-block'}>↻</span>
            Refresh
          </button>
        </div>

        {/* Controls row */}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {/* Supplier selector */}
          <div className="flex items-center gap-2">
            <label className="text-slate-400 text-xs font-medium whitespace-nowrap">Supplier</label>
            <select
              value={selectedSupplierId}
              onChange={e => onSupplierChange(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-brand-500 min-w-[180px]"
            >
              {suppliers.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          {/* Date preset tabs */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
            {DATE_PRESETS.map(p => (
              <button
                key={p.value}
                onClick={() => onDatePresetChange(p.value)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  datePreset === p.value
                    ? 'bg-brand-500 text-white shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </header>
  )
}
