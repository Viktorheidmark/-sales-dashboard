import { formatDate } from '../../utils/format'

interface MetaFooterProps {
  source: string
  generatedAt: string
  rowCount?: number
  limitations?: string[]
}

export function MetaFooter({ source, generatedAt, rowCount, limitations }: MetaFooterProps) {
  return (
    <div className="mt-4 pt-3 border-t border-zinc-100 flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="inline-flex items-center gap-1.5 text-xs text-zinc-400">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0" />
        Live analytics · {source}
      </span>
      <span className="text-xs text-zinc-400">
        {formatDate(generatedAt)}
      </span>
      {rowCount !== undefined && (
        <span className="text-xs text-zinc-400">{rowCount} row{rowCount !== 1 ? 's' : ''}</span>
      )}
      {limitations && limitations.length > 0 && (
        <span className="text-xs text-amber-500 ml-auto">{limitations[0]}</span>
      )}
    </div>
  )
}
