import type { ReactNode } from 'react'

type StatCardProps = {
  title: string
  variant?: 'default' | 'warning' | 'danger' | 'success'
  children: ReactNode
}

export function StatCard({ title, variant = 'default', children }: StatCardProps) {
  return (
    <div className={`stat-card stat-card-${variant}`}>
      <h3 className="stat-card-title">{title}</h3>
      <div className="stat-card-body">{children}</div>
    </div>
  )
}
