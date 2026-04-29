import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  ArrowRight,
  RotateCcw,
} from 'lucide-react'
import { Layout } from '@/components/Layout'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Alert } from '@/components/ui/Alert'
import { useStudyPolling } from '@/hooks/useStudyPolling'
import { updateStudyStatus, formatDate } from '@/lib/utils'
import type { StudyStatusValue } from '@/types/api'

interface Step {
  id: StudyStatusValue | 'results'
  label: string
  description: string
}

const STEPS: Step[] = [
  {
    id: 'pending',
    label: 'Queued',
    description: 'Job submitted, waiting for GPU worker',
  },
  {
    id: 'processing',
    label: 'Analyzing',
    description: 'Segmenting LV, computing measurements',
  },
  {
    id: 'done',
    label: 'Complete',
    description: 'All measurements and reports ready',
  },
]

function stepIndex(status: StudyStatusValue | null): number {
  switch (status) {
    case 'pending': return 0
    case 'processing': return 1
    case 'done': return 2
    default: return -1
  }
}

export function StudyStatusPage() {
  const { studyId } = useParams<{ studyId: string }>()
  const navigate = useNavigate()
  const { status, result, error, resultError, isPolling, currentStatus } = useStudyPolling(
    studyId ?? null,
  )

  useEffect(() => {
    if (studyId && currentStatus) {
      updateStudyStatus(studyId, currentStatus)
    }
  }, [studyId, currentStatus])

  useEffect(() => {
    if (result && currentStatus === 'done') {
      navigate(`/studies/${studyId}/results`, { state: { result }, replace: true })
    }
  }, [result, currentStatus, studyId, navigate])

  const active = stepIndex(currentStatus)
  const isFailed = currentStatus === 'failed' || !!error
  const isResultFetchError = currentStatus === 'done' && !!resultError && !result

  return (
    <Layout title="Analysis Status">
      <div className="max-w-xl mx-auto space-y-6">
        {/* Study info */}
        <Card className="p-6">
          <div className="flex items-start gap-4">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-primary-600/15 flex-shrink-0">
              <Activity className="w-6 h-6 text-primary-400" />
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="font-semibold text-slate-100 text-lg">
                Study Analysis
              </h2>
              <p className="text-sm text-slate-500 font-mono mt-0.5 truncate">
                {studyId}
              </p>
              {status?.created_at && (
                <p className="text-xs text-slate-600 mt-1">
                  Submitted {formatDate(status.created_at)}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Progress steps */}
        {!isFailed && (
          <Card className="p-6">
            <h3 className="font-semibold text-slate-200 mb-6">Processing Pipeline</h3>
            <div className="space-y-0">
              {STEPS.map((step, i) => {
                const isDone = active > i
                const isCurrent = active === i
                const isPending = active < i

                return (
                  <div key={step.id} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div
                        className={[
                          'flex items-center justify-center w-8 h-8 rounded-full border-2 z-10 flex-shrink-0 transition-all',
                          isDone
                            ? 'border-emerald-500 bg-emerald-500'
                            : isCurrent
                              ? 'border-primary-500 bg-primary-600/20'
                              : 'border-surface-4 bg-surface-2',
                        ].join(' ')}
                      >
                        {isDone ? (
                          <CheckCircle2 className="w-4 h-4 text-white" />
                        ) : isCurrent ? (
                          <div className="w-2.5 h-2.5 rounded-full bg-primary-400 animate-pulse" />
                        ) : (
                          <div className="w-2.5 h-2.5 rounded-full bg-slate-600" />
                        )}
                      </div>
                      {i < STEPS.length - 1 && (
                        <div
                          className={[
                            'w-0.5 h-10 mt-1',
                            isDone ? 'bg-emerald-500/40' : 'bg-surface-4',
                          ].join(' ')}
                        />
                      )}
                    </div>

                    <div className="pb-10 flex-1">
                      <p
                        className={[
                          'font-medium text-sm',
                          isDone
                            ? 'text-emerald-400'
                            : isCurrent
                              ? 'text-primary-400'
                              : 'text-slate-600',
                        ].join(' ')}
                      >
                        {step.label}
                        {isCurrent && (
                          <span className="ml-2 inline-flex items-center gap-1 text-xs text-primary-400">
                            <Activity className="w-3 h-3 animate-spin" />
                            In progress...
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-slate-600 mt-0.5">
                        {step.description}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>

            {isPolling && (
              <div className="flex items-center gap-2 mt-2 text-xs text-slate-600">
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                Polling every 3 seconds...
              </div>
            )}
          </Card>
        )}

        {/* Detailed processing stages */}
        {currentStatus === 'processing' && (
          <Card className="p-5">
            <h4 className="text-sm font-semibold text-slate-300 mb-3">
              Analysis Steps
            </h4>
            <div className="space-y-2">
              {[
                'Loading and normalizing frames',
                'Running U-Net segmentation',
                'Computing LVEF (Simpson biplane)',
                'Measuring wall thickness',
                'Detecting cardiac conditions',
                'Generating PDF + FHIR reports',
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <div className="w-4 h-4 flex-shrink-0">
                    <Activity className="w-4 h-4 text-primary-400 animate-pulse" />
                  </div>
                  <span className="text-slate-400">{step}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Error state */}
        {isFailed && (
          <div className="space-y-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-red-500/10 mx-auto">
              <XCircle className="w-8 h-8 text-red-400" />
            </div>
            <Alert variant="error" title="Analysis Failed">
              {error ?? status?.error ?? 'An unexpected error occurred during analysis.'}
            </Alert>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" onClick={() => navigate('/')}>
                Back to Dashboard
              </Button>
              <Button onClick={() => navigate('/upload')}>
                Try Again
              </Button>
            </div>
          </div>
        )}

        {currentStatus === 'pending' && (
          <Alert variant="info">
            Your study is queued. Analysis will begin shortly when a GPU worker
            is available. This page will automatically update.
          </Alert>
        )}

        {!isFailed && !currentStatus && (
          <Card className="p-8 flex flex-col items-center gap-4 text-center">
            <Clock className="w-10 h-10 text-slate-500 animate-pulse" />
            <p className="text-slate-500">Connecting to CordisAI backend...</p>
          </Card>
        )}

        {isResultFetchError && (
          <Alert variant="error" title="Could not load results">
            {resultError} — analysis completed, try viewing results directly.
          </Alert>
        )}

        {currentStatus === 'done' && (
          <Button
            className="w-full gap-2"
            onClick={() => navigate(`/studies/${studyId}/results`)}
          >
            View Results <ArrowRight className="w-4 h-4" />
          </Button>
        )}
      </div>
    </Layout>
  )
}
