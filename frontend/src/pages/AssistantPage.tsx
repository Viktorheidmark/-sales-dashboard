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
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <ChatPanel
        supplierName={user.supplier_name}
        startDate={startDate}
        endDate={endDate}
        initialPrompt={initialPrompt}
      />
    </div>
  )
}
