import type { AuthUser } from '../api/types'
import { PageHeader } from '../components/layout/PageHeader'
import { ChatPanel } from '../components/sections/ChatPanel'
import { presetToDates } from '../utils/dateRange'

interface AssistantPageProps {
  user: AuthUser
}

const FOCUS_AREAS = [
  'Produkter i nedgång',
  'Regionala trender',
  'Marknadsandel',
  'Säsongseffekter',
  'Toppsäljare',
  'Kategorianalys',
]

export function AssistantPage({ user }: AssistantPageProps) {
  const { startDate, endDate } = presetToDates('90d')

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analysassistent"
        subtitle="Ställ frågor om försäljning, produkter, regioner och marknadsandel."
      />
      <div className="flex gap-6 items-start">
        <div className="flex-1 min-w-0">
          <ChatPanel
            supplierName={user.supplier_name}
            startDate={startDate}
            endDate={endDate}
          />
        </div>

        {/* Secondary sidebar — visible only on xl+ */}
        <aside className="hidden xl:flex flex-col w-60 shrink-0 gap-4">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-5">
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-widest mb-3">Analysområden</p>
            <ul className="space-y-1.5">
              {FOCUS_AREAS.map(area => (
                <li
                  key={area}
                  className="flex items-center gap-2 text-sm text-slate-600"
                >
                  <span className="w-1 h-1 rounded-full bg-brand-400 shrink-0" />
                  {area}
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-slate-900 rounded-xl p-5">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest mb-2">Datakälla</p>
            <p className="text-xs text-slate-400 leading-relaxed">
              Svar grundas i MCP-analyserad syntetisk försäljningsdata för <span className="text-slate-200 font-medium">{user.supplier_name}</span>.
            </p>
            <p className="mt-3 text-xs text-slate-500">
              Konkurrentdata visas enbart aggregerat.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
