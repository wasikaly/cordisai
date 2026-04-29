import { cn } from '@/lib/utils'

interface BadgeProps {
  children: React.ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'outline' | 'secondary'
  className?: string
}

const variantClasses: Record<string, string> = {
  default: 'bg-primary-600/20 text-primary-400 border-primary-600/30',
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  warning: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  danger: 'bg-red-500/15 text-red-400 border-red-500/25',
  outline: 'bg-transparent text-slate-400 border-slate-600',
  secondary: 'bg-slate-700/50 text-slate-300 border-slate-600',
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border',
        variantClasses[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}
