interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`animate-pulse bg-workspace-border/60 rounded ${className}`} />
}

export function CardSkeleton() {
  return (
    <div className="surface-card p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-2/3" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  )
}

export function ChartSkeleton({ height = 240 }: { height?: number }) {
  return (
    <div className="surface-card p-5">
      <Skeleton className="h-4 w-1/4 mb-4" />
      <div
        className="w-full rounded-lg animate-pulse bg-workspace-border/40"
        style={{ height }}
      />
    </div>
  )
}
