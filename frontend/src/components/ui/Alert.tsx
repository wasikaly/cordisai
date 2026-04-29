import { cn } from '@/lib/utils'
import { AlertCircle, CheckCircle2, Info, XCircle } from 'lucide-react'

type AlertVariant = 'info' | 'success' | 'warning' | 'error'

interface AlertProps {
  variant?: AlertVariant
  title?: string
  children: React.ReactNode
  className?: string
}

const config: Record<AlertVariant, { icon: React.ElementType; classes: string }> = {
  info: {
    icon: Info,
    classes: 'bg-blue-500/10 border-blue-500/25 text-blue-300',
  },
  success: {
    icon: CheckCircle2,
    classes: 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300',
  },
  warning: {
    icon: AlertCircle,
    classes: 'bg-amber-500/10 border-amber-500/25 text-amber-300',
  },
  error: {
    icon: XCircle,
    classes: 'bg-red-500/10 border-red-500/25 text-red-300',
  },
}

export function Alert({ variant = 'info', title, children, className }: AlertProps) {
  const { icon: Icon, classes } = config[variant]
  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-4',
        classes,
        className,
      )}
      role="alert"
    >
      <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
      <div className="flex-1 text-sm">
        {title && <p className="font-semibold mb-1">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}
