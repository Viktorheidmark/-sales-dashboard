import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

interface ChatStateContextValue {
  hasMessages: boolean
  setHasMessages: (v: boolean) => void
  onNewChat: (() => void) | null
  setOnNewChat: (fn: (() => void) | null) => void
}

const ChatStateContext = createContext<ChatStateContextValue>({
  hasMessages: false,
  setHasMessages: () => {},
  onNewChat: null,
  setOnNewChat: () => {},
})

export function ChatStateProvider({ children }: { children: ReactNode }) {
  const [hasMessages, setHasMessages] = useState(false)
  const [onNewChat, setOnNewChatRaw] = useState<(() => void) | null>(null)

  const setOnNewChat = useCallback((fn: (() => void) | null) => {
    setOnNewChatRaw(() => fn)
  }, [])

  return (
    <ChatStateContext.Provider value={{ hasMessages, setHasMessages, onNewChat, setOnNewChat }}>
      {children}
    </ChatStateContext.Provider>
  )
}

export function useChatState() {
  return useContext(ChatStateContext)
}
