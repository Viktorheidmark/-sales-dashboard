interface MetaFooterProps {
  source: string
  generatedAt?: string
  rowCount?: number
  limitations?: string[]
}

export function MetaFooter({ source }: MetaFooterProps) {
  return (
    <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-1.5">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
      <span className="text-xs text-slate-400" title={source}>Syntetisk försäljningsdata</span>
    </div>
  )
}
