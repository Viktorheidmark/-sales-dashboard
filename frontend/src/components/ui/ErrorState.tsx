interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
      <div className="text-2xl" aria-hidden>⚠️</div>
      <p className="text-sm text-slate-400 max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs text-brand-400 hover:text-brand-300 font-medium underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/50 rounded"
        >
          Försök igen
        </button>
      )}
    </div>
  )
}
