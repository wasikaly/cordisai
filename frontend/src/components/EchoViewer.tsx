import { useState, useEffect, useRef, useCallback } from 'react'
import { Play, Pause, SkipBack, SkipForward, Eye, EyeOff } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'

const BASE_URL = 'http://localhost:8002'

interface EchoViewerProps {
  studyId: string
  frameCount: number
  edFrame?: number
  esFrame?: number
}

export function EchoViewer({ studyId, frameCount, edFrame, esFrame }: EchoViewerProps) {
  const [currentFrame, setCurrentFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [fps, setFps] = useState(25)
  const [loadedFrames, setLoadedFrames] = useState<Map<number, HTMLImageElement>>(new Map())
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Preload frames in batches
  useEffect(() => {
    if (frameCount === 0) return
    const map = new Map<number, HTMLImageElement>()
    let loaded = 0

    for (let i = 0; i < frameCount; i++) {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.src = `${BASE_URL}/api/v1/studies/${studyId}/frames/${i}`
      img.onload = () => {
        map.set(i, img)
        loaded++
        if (loaded === frameCount || loaded % 20 === 0) {
          setLoadedFrames(new Map(map))
        }
      }
    }

    return () => { map.clear() }
  }, [studyId, frameCount])

  // Autoplay when enough frames loaded (>50%)
  useEffect(() => {
    if (!playing && loadedFrames.size > frameCount * 0.5 && frameCount > 0) {
      setPlaying(true)
    }
  }, [loadedFrames.size, frameCount])

  // Draw current frame
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = loadedFrames.get(currentFrame)
    if (img) {
      canvas.width = img.width
      canvas.height = img.height
      ctx.drawImage(img, 0, 0)

      // Draw ED/ES markers
      if (currentFrame === edFrame) {
        drawLabel(ctx, 'ED', canvas.width - 50, 30, '#22c55e')
      } else if (currentFrame === esFrame) {
        drawLabel(ctx, 'ES', canvas.width - 50, 30, '#ef4444')
      }

      // Frame counter
      ctx.fillStyle = 'rgba(0,0,0,0.5)'
      ctx.fillRect(8, canvas.height - 30, 70, 22)
      ctx.font = '13px monospace'
      ctx.fillStyle = '#fff'
      ctx.fillText(`${currentFrame + 1}/${frameCount}`, 14, canvas.height - 13)
    } else {
      // Loading placeholder
      canvas.width = 448
      canvas.height = 448
      ctx.fillStyle = '#1e293b'
      ctx.fillRect(0, 0, 448, 448)
      ctx.font = '14px sans-serif'
      ctx.fillStyle = '#64748b'
      ctx.textAlign = 'center'
      ctx.fillText(`Loading frames (${loadedFrames.size}/${frameCount})...`, 224, 224)
    }
  }, [currentFrame, loadedFrames, frameCount, edFrame, esFrame])

  // Playback timer
  useEffect(() => {
    if (playing && frameCount > 0) {
      timerRef.current = setInterval(() => {
        setCurrentFrame(prev => (prev + 1) % frameCount)
      }, 1000 / fps)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [playing, fps, frameCount])

  const togglePlay = useCallback(() => setPlaying(p => !p), [])
  const goToED = useCallback(() => { if (edFrame !== undefined) { setCurrentFrame(edFrame); setPlaying(false) } }, [edFrame])
  const goToES = useCallback(() => { if (esFrame !== undefined) { setCurrentFrame(esFrame); setPlaying(false) } }, [esFrame])
  const stepBack = useCallback(() => { setPlaying(false); setCurrentFrame(p => (p - 1 + frameCount) % frameCount) }, [frameCount])
  const stepForward = useCallback(() => { setPlaying(false); setCurrentFrame(p => (p + 1) % frameCount) }, [frameCount])

  const progress = loadedFrames.size / Math.max(frameCount, 1)

  return (
    <div className="space-y-3">
      {/* Canvas */}
      <div className="relative bg-slate-900 rounded-xl overflow-hidden flex items-center justify-center"
           style={{ minHeight: 350 }}>
        <canvas
          ref={canvasRef}
          className="max-w-full max-h-[500px] rounded-lg"
          style={{ imageRendering: 'auto' }}
        />

        {/* Loading overlay */}
        {progress < 1 && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/60">
            <div className="text-center text-white">
              <div className="w-48 h-1.5 bg-slate-700 rounded-full mx-auto mb-2">
                <div className="h-full bg-primary-500 rounded-full transition-all"
                     style={{ width: `${progress * 100}%` }} />
              </div>
              <p className="text-xs text-slate-400">Loading frames... {loadedFrames.size}/{frameCount}</p>
            </div>
          </div>
        )}
      </div>

      {/* Timeline scrubber */}
      <div className="relative">
        <input
          type="range"
          min={0}
          max={Math.max(frameCount - 1, 0)}
          value={currentFrame}
          onChange={e => { setCurrentFrame(+e.target.value); setPlaying(false) }}
          className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
        />
        {/* ED/ES markers on timeline */}
        {edFrame !== undefined && frameCount > 0 && (
          <div className="absolute top-0 w-1.5 h-2 bg-green-500 rounded-full pointer-events-none"
               style={{ left: `${(edFrame / (frameCount - 1)) * 100}%` }} />
        )}
        {esFrame !== undefined && frameCount > 0 && (
          <div className="absolute top-0 w-1.5 h-2 bg-red-500 rounded-full pointer-events-none"
               style={{ left: `${(esFrame / (frameCount - 1)) * 100}%` }} />
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button onClick={stepBack}
                  className="p-2 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors">
            <SkipBack className="w-4 h-4" />
          </button>
          <button onClick={togglePlay}
                  className="p-2.5 rounded-xl bg-primary-600 text-white hover:bg-primary-700 transition-colors">
            {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
          </button>
          <button onClick={stepForward}
                  className="p-2 rounded-lg hover:bg-slate-100 text-slate-600 transition-colors">
            <SkipForward className="w-4 h-4" />
          </button>
        </div>

        {/* Speed selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">Speed:</span>
          {[10, 25, 50].map(f => (
            <button
              key={f}
              onClick={() => setFps(f)}
              className={`px-2 py-1 text-xs rounded-md transition-colors ${
                fps === f
                  ? 'bg-primary-600 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {f === 10 ? '0.5x' : f === 25 ? '1x' : '2x'}
            </button>
          ))}
        </div>

        {/* Jump to ED/ES */}
        <div className="flex items-center gap-2">
          {edFrame !== undefined && (
            <button onClick={goToED}
                    className="px-2.5 py-1 text-xs rounded-md bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors">
              ED (#{edFrame})
            </button>
          )}
          {esFrame !== undefined && (
            <button onClick={goToES}
                    className="px-2.5 py-1 text-xs rounded-md bg-red-50 text-red-700 border border-red-200 hover:bg-red-100 transition-colors">
              ES (#{esFrame})
            </button>
          )}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-slate-500 pt-1">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(220,60,60,0.6)' }} />
          LV Cavity
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(220,200,40,0.6)' }} />
          Myocardium
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: 'rgba(60,160,220,0.6)' }} />
          Left Atrium
        </span>
      </div>
    </div>
  )
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, color: string) {
  ctx.fillStyle = 'rgba(0,0,0,0.6)'
  ctx.fillRect(x - 4, y - 16, 40, 24)
  ctx.font = 'bold 16px sans-serif'
  ctx.fillStyle = color
  ctx.fillText(text, x, y)
}
