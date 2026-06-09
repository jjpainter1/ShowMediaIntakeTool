import type { ReactNode } from 'react'

type BannerProps = {
  icon?: string
  children: ReactNode
  onDismiss?: () => void
  expanded?: ReactNode
  expandedOpen?: boolean
  onToggleExpand?: () => void
  actionLabel?: string
}

export function Banner({
  icon = '⚠',
  children,
  onDismiss,
  expanded,
  expandedOpen = false,
  onToggleExpand,
  actionLabel,
}: BannerProps) {
  return (
    <div className="banner banner-warning">
      <div className="banner-row">
        <span className="banner-icon" aria-hidden>
          {icon}
        </span>
        <div className="banner-content">
          <span>{children}</span>
          {actionLabel && onToggleExpand && (
            <button type="button" className="banner-link" onClick={onToggleExpand}>
              {actionLabel}
            </button>
          )}
        </div>
        {onDismiss && (
          <button type="button" className="banner-dismiss" onClick={onDismiss} aria-label="Dismiss">
            ✕
          </button>
        )}
      </div>
      {expandedOpen && expanded && <div className="banner-expanded">{expanded}</div>}
    </div>
  )
}
