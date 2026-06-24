import { useLocation } from 'react-router-dom'
import type { AuthUser } from '../api/types'
import { ChatPanel } from '../components/sections/ChatPanel'
import { presetToDates } from '../utils/dateRange'

interface AssistantPageProps {
  user: AuthUser
}

export function AssistantPage({ user }: AssistantPageProps) {
  const { startDate, endDate } = presetToDates('90d')
  const location = useLocation()
  const initialPrompt = (location.state as { initialPrompt?: string } | null)?.initialPrompt

  return (
    <div className="flex flex-col min-h-[calc(100dvh-4rem)]">
      <ChatPanel
        supplierName={user.supplier_name}
        startDate={startDate}
        endDate={endDate}
        initialPrompt={initialPrompt}
      />
    </div>
  )
}
