import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import {
  Download,
  FileText,
  FileJson,
  ArrowLeft,
  User,
  Brain,
  BarChart3,
  Activity,
  AlertTriangle,
  Heart,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Maximize2,
  Microscope,
} from 'lucide-react'
import { Layout } from '@/components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Alert } from '@/components/ui/Alert'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { EFGauge } from '@/components/EFGauge'
import { EchoViewer } from '@/components/EchoViewer'
import { LVAreaChart } from '@/components/LVAreaChart'
import { MeasurementsTable } from '@/components/MeasurementsTable'
import { getStudyResults, downloadReport, downloadFhir } from '@/api/client'
import { truncateId, updateStudyStatus } from '@/lib/utils'
import type { AnalysisResult, Diseases } from '@/types/api'

/* ── Compact disease row (for inline display) ── */
function CompactDiseaseRow({ diseases }: { diseases: Diseases }) {
  const items = [
    { key: 'heart_failure', label: 'Heart Failure', icon: Heart, data: diseases.heart_failure },
    { key: 'lv_hypertrophy', label: 'LV Hypertrophy', icon: Activity, data: diseases.lv_hypertrophy },
    { key: 'lv_dilatation', label: 'LV Dilatation', icon: Maximize2, data: diseases.lv_dilatation },
    { key: 'la_enlargement', label: 'LA Enlargement', icon: AlertTriangle, data: diseases.la_enlargement },
    { key: 'amyloidosis', label: 'Amyloidosis', icon: Microscope, data: diseases.amyloidosis_suspicion },
  ]

  const flaggedCount = items.filter(i => i.data?.flag).length

  return (
    <div className="space-y-3">
      {/* Summary banner */}
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium ${
        flaggedCount === 0
          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
          : 'bg-red-500/10 text-red-400 border border-red-500/20'
      }`}>
        {flaggedCount === 0 ? (
          <><CheckCircle2 className="w-4 h-4" /> No disease flags — all normal</>
        ) : (
          <><AlertTriangle className="w-4 h-4" /> {flaggedCount} condition{flaggedCount > 1 ? 's' : ''} flagged</>
        )}
      </div>

      {/* Compact disease list */}
      <div className="grid grid-cols-1 gap-2">
        {items.map(item => {
          const flagged = item.data?.flag ?? false
          const Icon = item.icon
          return (
            <div key={item.key} className={`flex items-center justify-between px-3 py-2 rounded-lg border ${
              flagged ? 'bg-red-500/8 border-red-500/20' : 'bg-surface-3 border-border'
            }`}>
              <div className="flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 ${flagged ? 'text-red-500' : 'text-green-500'}`} />
                <span className="text-sm text-slate-300">{item.label}</span>
                {flagged && item.data?.type && (
                  <span className="text-xs text-slate-500">({item.data.type})</span>
                )}
              </div>
              {flagged ? (
                <Badge variant="danger" className="text-xs">Flagged</Badge>
              ) : (
                <Badge variant="success" className="text-xs">Normal</Badge>
              )}
            </div>
          )
        })}
      </div>

      {/* Clinical notes */}
      {diseases.notes && diseases.notes.length > 0 && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
          <p className="text-xs font-semibold text-amber-400 mb-1">Clinical Notes</p>
          {diseases.notes.map((note, i) => (
            <p key={i} className="text-xs text-amber-300/80">- {note}</p>
          ))}
        </div>
      )}
    </div>
  )
}

function ModeBadge({ mode }: { mode: string }) {
  const map: Record<string, { label: string; variant: 'success' | 'warning' | 'secondary' }> = {
    segmentation: { label: 'Segmentation', variant: 'success' },
    ef_regressor: { label: 'EF Regressor', variant: 'warning' },
    random_weights: { label: 'Demo', variant: 'secondary' },
  }
  const cfg = map[mode] ?? { label: mode, variant: 'secondary' as const }
  return <Badge variant={cfg.variant} className="text-xs">{cfg.label}</Badge>
}

interface ResultsPageProps {
  prefetchedResult?: AnalysisResult
}

export function ResultsPage({ prefetchedResult }: ResultsPageProps) {
  const { studyId } = useParams<{ studyId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const [result, setResult] = useState<AnalysisResult | null>(
    prefetchedResult ?? (location.state as { result?: AnalysisResult } | null)?.result ?? null,
  )
  const [loading, setLoading] = useState(!result)
  const [error, setError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<'pdf' | 'fhir' | null>(null)
  const [activeTab, setActiveTab] = useState<'diseases' | 'info' | 'chart'>('diseases')

  useEffect(() => {
    if (result || !studyId) return
    setLoading(true)
    getStudyResults(studyId)
      .then(setResult)
      .catch(e => setError((e as Error).message))
      .finally(() => setLoading(false))
  }, [studyId, result])

  useEffect(() => {
    if (result && studyId) updateStudyStatus(studyId, 'done')
  }, [result, studyId])

  const handleDownloadPDF = async () => {
    if (!studyId) return
    setDownloading('pdf')
    try { await downloadReport(studyId) } catch (e) { alert((e as Error).message) } finally { setDownloading(null) }
  }

  const handleDownloadFHIR = async () => {
    if (!studyId) return
    setDownloading('fhir')
    try { await downloadFhir(studyId) } catch (e) { alert((e as Error).message) } finally { setDownloading(null) }
  }

  const ef = result?.measurements?.LVEF?.value
  const lvAreas = result?.measurements?.lv_areas
  const edFrame = result?.measurements?.ed_frame
  const esFrame = result?.measurements?.es_frame

  return (
    <Layout title="Analysis Results">
      <div className="w-full mx-auto space-y-3">
        {/* ── Top bar ── */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')} className="gap-1.5">
            <ArrowLeft className="w-4 h-4" /> Dashboard
          </Button>
          {result && (
            <div className="flex items-center gap-3">
              {/* Inline quick stats */}
              <div className="hidden md:flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 rounded-lg border border-border">
                  <Heart className="w-3.5 h-3.5 text-primary-600" />
                  <span className="text-xs text-slate-500">LVEF</span>
                  <span className={`text-sm font-bold ${ef !== undefined && ef < 40 ? 'text-danger-600' : ef !== undefined && ef < 53 ? 'text-warning-500' : 'text-success-600'}`}>
                    {ef !== undefined ? `${ef.toFixed(0)}%` : '—'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 rounded-lg border border-border">
                  <Activity className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-500">LVEDV</span>
                  <span className="text-sm font-bold text-slate-100">
                    {result.measurements?.LVEDV?.value != null ? `${result.measurements.LVEDV.value.toFixed(0)} mL` : '—'}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 rounded-lg border border-border">
                  <span className="text-xs text-slate-500">Mode</span>
                  <ModeBadge mode={result.mode} />
                </div>
                {(() => {
                  const d = result.diseases
                  const count = [d?.heart_failure, d?.lv_hypertrophy, d?.lv_dilatation, d?.la_enlargement, d?.amyloidosis_suspicion]
                    .filter(x => x?.flag).length
                  return (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 rounded-lg border border-border">
                      <span className="text-xs text-slate-500">Findings</span>
                      <Badge variant={count > 0 ? 'danger' : 'success'} className="text-xs">
                        {count > 0 ? `${count} flagged` : 'all normal'}
                      </Badge>
                    </div>
                  )
                })()}
              </div>
              <Button variant="outline" size="sm" loading={downloading === 'fhir'} onClick={handleDownloadFHIR} className="gap-1.5">
                <FileJson className="w-4 h-4" /> FHIR
              </Button>
              <Button size="sm" loading={downloading === 'pdf'} onClick={handleDownloadPDF} className="gap-1.5">
                <FileText className="w-4 h-4" /> PDF
              </Button>
            </div>
          )}
        </div>

        {error && <Alert variant="error" title="Failed to load results">{error}</Alert>}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SkeletonCard /><SkeletonCard />
          </div>
        ) : result ? (
          <div className="space-y-3">
            {/* ═══════ ROW 1: Video (left) + Measurements (right) ═══════ */}
            <div className="grid grid-cols-1 lg:grid-cols-[1fr_420px] xl:grid-cols-[1fr_480px] gap-3 items-start">

              {/* ── Left: Echo Video ── */}
              <Card>
                <CardHeader className="py-2.5 px-4">
                  <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-primary-600" />
                    <CardTitle className="text-sm">Echo Video — AI Segmentation</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="px-3 pb-3">
                  {result.frame_count && result.frame_count > 0 && studyId ? (
                    <EchoViewer
                      studyId={studyId}
                      frameCount={result.frame_count}
                      edFrame={edFrame}
                      esFrame={esFrame}
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center py-16">
                      <Brain className="w-16 h-16 text-slate-200 mb-3" />
                      <p className="text-sm text-slate-400">No video frames available</p>
                      <p className="text-xs text-slate-300 mt-1">Upload a new study to see AI segmentation</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* ── Right: Measurements (scrollable) ── */}
              <div className="lg:max-h-[calc(100vh-180px)] lg:overflow-y-auto scrollbar-thin lg:sticky lg:top-4">
                <Card>
                  <CardHeader className="py-2.5 px-4 border-b border-border sticky top-0 bg-surface-2 z-10 rounded-t-xl">
                    <div className="flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-primary-600" />
                      <CardTitle className="text-sm">Cardiac Measurements</CardTitle>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">ASE 2015 guidelines</p>
                  </CardHeader>
                  <CardContent className="px-0 pb-3">
                    <MeasurementsTable measurements={result.measurements} />
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* ═══════ ROW 2: EF Gauge + Disease/Info/Chart tabs ═══════ */}
            <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-3">

              {/* ── EF Gauge (compact) ── */}
              <Card>
                <CardHeader className="py-2.5 px-4">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-primary-600" />
                    <CardTitle className="text-sm">Ejection Fraction</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="flex items-center justify-center pb-3">
                  {ef !== undefined ? (
                    <EFGauge ef={ef} />
                  ) : (
                    <div className="text-sm text-slate-400 py-6">EF not available</div>
                  )}
                </CardContent>
              </Card>

              {/* ── Tabbed panel: Diseases / Study Info / Cardiac Cycle ── */}
              <Card>
                <CardHeader className="py-0 px-0 flex-shrink-0">
                  <div className="flex border-b border-border">
                    {[
                      { id: 'diseases' as const, label: 'Disease Detection', icon: AlertTriangle },
                      { id: 'chart' as const, label: 'Cardiac Cycle', icon: Activity },
                      { id: 'info' as const, label: 'Study Info', icon: User },
                    ].map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                          activeTab === tab.id
                            ? 'border-primary-600 text-primary-600'
                            : 'border-transparent text-slate-500 hover:text-slate-300'
                        }`}
                      >
                        <tab.icon className="w-3.5 h-3.5" />
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </CardHeader>
                <CardContent className="p-4">
                  {activeTab === 'diseases' && (
                    <CompactDiseaseRow diseases={result.diseases} />
                  )}

                  {activeTab === 'chart' && (
                    <LVAreaChart
                      lvAreas={Array.isArray(lvAreas) ? lvAreas : []}
                      edFrame={edFrame}
                      esFrame={esFrame}
                    />
                  )}

                  {activeTab === 'info' && (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                          <p className="text-xs text-slate-500">Study ID</p>
                          <p className="text-sm font-mono text-slate-200 mt-0.5">{truncateId(result.study_id)}</p>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                          <p className="text-xs text-slate-500">Status</p>
                          <div className="mt-0.5"><Badge variant="success" className="text-xs">Complete</Badge></div>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                          <p className="text-xs text-slate-500">Pipeline Mode</p>
                          <div className="mt-0.5"><ModeBadge mode={result.mode} /></div>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                          <p className="text-xs text-slate-500">View Classification</p>
                          <p className="text-sm font-medium text-slate-200 mt-0.5">
                            {(result.view?.label as string) ?? (result.view?.view as string) ?? '—'}
                            {typeof result.view?.confidence === 'number' && (
                              <span className="text-xs text-slate-400 ml-1">
                                ({(result.view.confidence as number * 100).toFixed(0)}%)
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      {result.mode === 'random_weights' && (
                        <Alert variant="warning" className="text-xs">
                          Demo mode — train checkpoints for real results.
                        </Alert>
                      )}
                      {/* Classifications */}
                      {(result.measurements?.EF_category || result.measurements?.LV_geometry) && (
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                          {result.measurements.EF_category && (
                            <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                              <p className="text-xs text-slate-500">EF Category</p>
                              <p className="text-sm font-medium text-slate-200 mt-0.5">{result.measurements.EF_category}</p>
                            </div>
                          )}
                          {result.measurements.LV_geometry && (
                            <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                              <p className="text-xs text-slate-500">LV Geometry</p>
                              <p className="text-sm font-medium text-slate-200 mt-0.5">{result.measurements.LV_geometry}</p>
                            </div>
                          )}
                          {result.measurements.BSA && typeof result.measurements.BSA === 'object' && (
                            <div className="px-3 py-2 rounded-lg bg-surface-3 border border-border">
                              <p className="text-xs text-slate-500">BSA</p>
                              <p className="text-sm font-medium text-slate-200 mt-0.5">
                                {(result.measurements.BSA as { value: number }).value.toFixed(2)} m²
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* ── Disclaimer ── */}
            <div className="text-xs text-slate-400 px-1 pb-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 flex-shrink-0" />
              Research prototype — not validated for clinical use. All measurements are automatic and may contain errors.
            </div>
          </div>
        ) : !error ? (
          <Card className="p-12 text-center">
            <Brain className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">No results found for this study.</p>
            <Button variant="outline" className="mt-4" onClick={() => navigate(`/studies/${studyId}`)}>
              Check Status
            </Button>
          </Card>
        ) : null}
      </div>
    </Layout>
  )
}
