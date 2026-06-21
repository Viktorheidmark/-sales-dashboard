interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse bg-zinc-100 rounded ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  )
}

export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div className="bg-white rounded-xl border border-zinc-200 shadow-sm p-6">
      <Skeleton className="h-4 w-1/4 mb-4" />
      <div
        className="w-full rounded-lg animate-pulse bg-zinc-100"
        style={{ height }}
      />
    </div>
  )
}
