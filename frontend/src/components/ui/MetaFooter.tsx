interface MetaFooterProps {
  source: string
  generatedAt?: string
  rowCount?: number
  limitations?: string[]
}

export function MetaFooter({ source }: MetaFooterProps) {
  return (
    <div className="mt-3 pt-2 border-t border-workspace-border flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />
      <span className="text-xs text-theme-muted" title={source}>Syntetisk försäljningsdata</span>
    </div>
  )
}
