import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Wifi, WifiOff, Plus } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { getHealth } from '@/api/client'
import type { HealthStatus } from '@/types/api'

export function Header({ title }: { title: string }) {
  const navigate = useNavigate()
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [healthError, setHealthError] = useState(false)

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const h = await getHealth()
        if (!cancelled) {
          setHealth(h)
          setHealthError(false)
        }
      } catch {
        if (!cancelled) setHealthError(true)
      }
    }

    check()
    const id = setInterval(check, 15_000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-6 py-3 bg-surface-1/80 backdrop-blur-xl border-b border-border">
      <div>
        <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
      </div>

      <div className="flex items-center gap-4">
        {/* API health indicator */}
        <div className="flex items-center gap-2 text-sm">
          {healthError ? (
            <>
              <WifiOff className="w-4 h-4 text-danger-400" />
              <span className="text-danger-400 font-medium">API offline</span>
            </>
          ) : health ? (
            <>
              <Wifi className="w-4 h-4 text-emerald-400" />
              <span className="text-slate-400">
                API online
                {health.cuda_available && (
                  <span className="ml-1 text-xs text-primary-400 font-semibold">
                    · CUDA
                  </span>
                )}
              </span>
              {health.active_jobs > 0 && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-600/20 text-primary-400 text-xs font-semibold">
                  <Activity className="w-3 h-3 animate-pulse" />
                  {health.active_jobs} active
                </span>
              )}
            </>
          ) : (
            <>
              <div className="w-4 h-4 rounded-full bg-surface-4 animate-pulse" />
              <span className="text-slate-500 text-sm">Checking...</span>
            </>
          )}
        </div>

        <Button
          size="sm"
          onClick={() => navigate('/upload')}
          className="gap-1.5"
        >
          <Plus className="w-4 h-4" />
          New Analysis
        </Button>
      </div>
    </header>
  )
}
