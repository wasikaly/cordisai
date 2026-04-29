import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity,
  Clock,
  CheckCircle2,
  XCircle,
  Upload,
  ArrowRight,
} from 'lucide-react'
import { Layout } from '@/components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { getStoredStudies, formatDate, truncateId, type StoredStudy } from '@/lib/utils'

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  color: string
}) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl ${color}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-2xl font-bold text-slate-100">{value}</p>
        </div>
      </div>
    </Card>
  )
}

function statusBadge(status: string) {
  switch (status) {
    case 'done':
      return <Badge variant="success">Done</Badge>
    case 'processing':
      return <Badge variant="default">Processing</Badge>
    case 'pending':
      return <Badge variant="secondary">Pending</Badge>
    case 'failed':
      return <Badge variant="danger">Failed</Badge>
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

export function Dashboard() {
  const navigate = useNavigate()
  const [studies, setStudies] = useState<StoredStudy[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const stored = getStoredStudies()
    setStudies(stored)
    setLoading(false)
  }, [])

  const total = studies.length
  const done = studies.filter(s => s.status === 'done').length
  const active = studies.filter(s => s.status === 'processing' || s.status === 'pending').length
  const failed = studies.filter(s => s.status === 'failed').length
  const recent = studies.slice(0, 8)

  return (
    <Layout title="Dashboard">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Welcome banner */}
        <div className="rounded-2xl bg-gradient-to-r from-primary-700 to-primary-600 p-6 text-white shadow-glow border border-primary-700/50">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-white/70 text-xs font-semibold tracking-widest uppercase">CordisAI Platform</span>
              </div>
              <h2 className="text-2xl font-bold mb-1">Echocardiography Analysis</h2>
              <p className="text-primary-200 text-sm max-w-lg">
                AI-powered LV segmentation · 21 cardiac measurements · 7 disease flags ·
                Clinical recommendations · FHIR/PDF reports
              </p>
            </div>
            <Button
              className="bg-white text-primary-700 hover:bg-slate-100 shadow-md gap-2"
              onClick={() => navigate('/upload')}
            >
              <Upload className="w-4 h-4" />
              Upload Echo
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard icon={Activity} label="Total Studies" value={total} color="bg-primary-600" />
          <StatCard icon={CheckCircle2} label="Completed" value={done} color="bg-emerald-600" />
          <StatCard icon={Clock} label="Active" value={active} color="bg-amber-600" />
          <StatCard icon={XCircle} label="Failed" value={failed} color="bg-red-600" />
        </div>

        {/* Recent studies */}
        <Card>
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent Studies</CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/studies')}
              className="gap-1 text-primary-400"
            >
              View all <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="p-6 space-y-3">
                {[1, 2, 3].map(i => (
                  <Skeleton key={i} className="h-14 w-full" />
                ))}
              </div>
            ) : recent.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-16 h-16 rounded-full bg-surface-4 flex items-center justify-center mb-4">
                  <Upload className="w-7 h-7 text-slate-500" />
                </div>
                <p className="text-slate-400 font-medium mb-1">No studies yet</p>
                <p className="text-slate-500 text-sm mb-4">
                  Upload an echo video to get started
                </p>
                <Button onClick={() => navigate('/upload')}>
                  Upload First Study
                </Button>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {recent.map((study) => (
                  <div
                    key={study.study_id}
                    className="flex items-center gap-4 px-6 py-4 hover:bg-surface-3 cursor-pointer transition-colors"
                    onClick={() => navigate(`/studies/${study.study_id}`)}
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary-600/15 flex-shrink-0">
                      <Activity className="w-5 h-5 text-primary-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-200 truncate">
                        {study.patient_name || 'Anonymous'}
                      </p>
                      <p className="text-xs text-slate-500">
                        ID: {study.patient_id} · {formatDate(study.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      {statusBadge(study.status)}
                      <span className="text-xs text-slate-600 font-mono">
                        {truncateId(study.study_id)}
                      </span>
                      <ArrowRight className="w-4 h-4 text-slate-600" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Model status */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Segmentation</span>
            </div>
            <p className="font-semibold text-slate-200">U-Net 2D</p>
            <p className="text-sm text-slate-500 mt-1">Val LV Dice = 0.9153</p>
            <Badge variant="success" className="mt-2">Done ✓</Badge>
          </Card>
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-amber-500"></div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">EF Regressor</span>
            </div>
            <p className="font-semibold text-slate-200">EfficientNet-B0</p>
            <p className="text-sm text-slate-500 mt-1">Best MAE = 5.60% · epoch 11/30</p>
            <Badge variant="warning" className="mt-2">Paused</Badge>
          </Card>
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">View Classifier</span>
            </div>
            <p className="font-semibold text-slate-200">A4C / A2C</p>
            <p className="text-sm text-slate-500 mt-1">Val acc = 93.3% · 20 epochs</p>
            <Badge variant="success" className="mt-2">Done ✓</Badge>
          </Card>
        </div>

        {/* Platform capabilities */}
        <Card>
          <CardHeader>
            <CardTitle>Platform Capabilities</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="space-y-1">
                <p className="font-semibold text-slate-300">Measurements</p>
                <p className="text-slate-500">21 parameters: LVEF, volumes, LVM, GLS, BSA-indexed, wall thickness, RWT</p>
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-slate-300">Disease Detection</p>
                <p className="text-slate-500">7 conditions: HF, LVH, dilatation, LA enlargement, amyloidosis, diastolic dysfunction, valvular risk</p>
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-slate-300">Input Formats</p>
                <p className="text-slate-500">AVI (EchoNet), DICOM single/multi-frame, CAMUS NIfTI</p>
              </div>
              <div className="space-y-1">
                <p className="font-semibold text-slate-300">Export</p>
                <p className="text-slate-500">PDF report + recommendations, FHIR R4 bundle, DICOM SR, JSON API</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </Layout>
  )
}
