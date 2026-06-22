interface ErrorStateProps {
  message: string
  onRetry?: () => void
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-10 gap-3 text-center">
      <div className="text-2xl">⚠️</div>
      <p className="text-sm text-zinc-500 max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="text-xs text-brand-600 hover:text-brand-700 font-medium underline underline-offset-2"
        >
          Försök igen
        </button>
      )}
    </div>
  )
}
