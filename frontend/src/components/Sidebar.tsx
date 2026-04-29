import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  Upload,
  ClipboardList,
  Activity,
  ChevronRight,
} from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: React.ElementType
  exact?: boolean
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { to: '/upload', label: 'New Analysis', icon: Upload },
  { to: '/studies', label: 'Recent Studies', icon: ClipboardList },
]

export function Sidebar() {
  const location = useLocation()

  return (
    <aside className="fixed inset-y-0 left-0 w-64 bg-sidebar flex flex-col z-30 border-r border-border">
      {/* Brand */}
      <div className="flex items-center justify-center px-6 py-5 border-b border-border">
        <span className="text-2xl font-bold text-white tracking-tight">
          CORDIS <span className="text-primary-500">AI</span>
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <p className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
          Workspace
        </p>
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = item.exact
            ? location.pathname === item.to
            : location.pathname.startsWith(item.to)

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors group',
                isActive
                  ? 'bg-primary-600/20 text-primary-400'
                  : 'text-slate-400 hover:bg-surface-3 hover:text-slate-200',
              )}
            >
              <Icon
                className={cn(
                  'w-4.5 h-4.5 flex-shrink-0',
                  isActive ? 'text-primary-400' : 'text-slate-500 group-hover:text-slate-300',
                )}
              />
              <span className="flex-1">{item.label}</span>
              {isActive && (
                <ChevronRight className="w-3.5 h-3.5 text-primary-400" />
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-6 py-4 border-t border-border">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-slate-500" />
          <span className="text-xs text-slate-500">API: localhost:8002</span>
        </div>
        <p className="text-xs text-slate-600 mt-1">CordisAI v0.1 — MVP</p>
      </div>
    </aside>
  )
}
