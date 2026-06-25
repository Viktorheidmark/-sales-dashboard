import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  variant?: 'default' | 'dashboard'
}

export function Card({ children, className = '', variant = 'default' }: CardProps) {
  const base = variant === 'dashboard' ? 'dashboard-panel' : 'surface-card'
  return (
    <div className={`${base} ${className}`.trim()}>
      {children}
    </div>
  )
}

export function CardHeader({ children, className = '' }: CardProps) {
  return (
    <div className={`px-5 pt-4 pb-3 dashboard-panel-head ${className}`}>
      {children}
    </div>
  )
}

export function CardBody({ children, className = '' }: CardProps) {
  return (
    <div className={`px-5 pb-5 dashboard-panel-body ${className}`}>
      {children}
    </div>
  )
}
