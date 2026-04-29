import {
  Heart,
  AlertTriangle,
  Activity,
  Maximize2,
  Microscope,
  CheckCircle2,
  XCircle,
  Stethoscope,
  HeartPulse,
  ClipboardList,
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import type { Diseases } from '@/types/api'

interface DiseaseCardProps {
  icon: React.ElementType
  title: string
  flagged: boolean
  subtype?: string
  confidence?: string
}

function DiseaseCard({ icon: Icon, title, flagged, subtype, confidence }: DiseaseCardProps) {
  return (
    <div
      className={[
        'flex items-start gap-3 p-3 rounded-xl border transition-colors',
        flagged
          ? 'bg-red-500/8 border-red-500/20'
          : 'bg-surface-3 border-border',
      ].join(' ')}
    >
      <div
        className={[
          'flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0',
          flagged ? 'bg-red-500/15' : 'bg-surface-4',
        ].join(' ')}
      >
        <Icon className={`w-4 h-4 ${flagged ? 'text-red-400' : 'text-slate-500'}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium text-sm text-slate-200">{title}</p>
          {flagged ? (
            <Badge variant="danger">Flagged</Badge>
          ) : (
            <Badge variant="success">Normal</Badge>
          )}
        </div>
        {flagged && subtype && (
          <p className="text-xs text-slate-400 mt-0.5">{subtype}</p>
        )}
        {confidence && (
          <p className="text-xs text-slate-600 mt-0.5">
            Confidence: {confidence}
          </p>
        )}
      </div>
      <div className="flex-shrink-0">
        {flagged ? (
          <XCircle className="w-4 h-4 text-red-400" />
        ) : (
          <CheckCircle2 className="w-4 h-4 text-emerald-500" />
        )}
      </div>
    </div>
  )
}

interface DiseaseFlagsProps {
  diseases: Diseases
}

export function DiseaseFlags({ diseases }: DiseaseFlagsProps) {
  const cards = [
    {
      icon: Heart,
      title: 'Heart Failure',
      flagged: diseases.heart_failure?.flag ?? false,
      subtype: diseases.heart_failure?.type,
      confidence: diseases.heart_failure?.confidence,
    },
    {
      icon: Activity,
      title: 'LV Hypertrophy',
      flagged: diseases.lv_hypertrophy?.flag ?? false,
      subtype: diseases.lv_hypertrophy?.type,
    },
    {
      icon: Maximize2,
      title: 'LV Dilatation',
      flagged: diseases.lv_dilatation?.flag ?? false,
    },
    {
      icon: AlertTriangle,
      title: 'LA Enlargement',
      flagged: diseases.la_enlargement?.flag ?? false,
    },
    {
      icon: Microscope,
      title: 'Amyloidosis Suspicion',
      flagged: diseases.amyloidosis_suspicion?.flag ?? false,
      confidence: diseases.amyloidosis_suspicion?.confidence,
    },
    {
      icon: HeartPulse,
      title: 'Diastolic Dysfunction Risk',
      flagged: diseases.diastolic_dysfunction_risk?.flag ?? false,
      subtype: diseases.diastolic_dysfunction_risk?.risk_factors?.join(', '),
    },
    {
      icon: Stethoscope,
      title: 'Valvular Disease Risk',
      flagged: diseases.valvular_disease_risk?.flag ?? false,
      subtype: diseases.valvular_disease_risk?.indicators?.join('; '),
    },
  ]

  const flaggedCount = cards.filter(c => c.flagged).length

  return (
    <div className="space-y-3">
      {/* Summary */}
      <div className={`flex items-center gap-3 p-3 rounded-lg border ${
        flaggedCount === 0
          ? 'bg-emerald-500/8 border-emerald-500/20'
          : 'bg-orange-500/8 border-orange-500/20'
      }`}>
        {flaggedCount === 0 ? (
          <>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
            <span className="text-sm text-slate-300">
              <strong className="text-emerald-400">No disease flags detected</strong> — all parameters within normal range
            </span>
          </>
        ) : (
          <>
            <AlertTriangle className="w-5 h-5 text-orange-400" />
            <span className="text-sm text-slate-300">
              <strong className="text-orange-400">{flaggedCount} condition{flaggedCount > 1 ? 's' : ''} flagged</strong> — clinical review recommended
            </span>
          </>
        )}
      </div>

      {/* Disease cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {cards.map((card) => (
          <DiseaseCard key={card.title} {...card} />
        ))}
      </div>

      {/* Clinical notes */}
      {diseases.notes && diseases.notes.length > 0 && (
        <div className="mt-3 p-3 bg-slate-700/30 border border-slate-500/20 rounded-xl">
          <p className="text-sm font-semibold text-slate-200 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            Clinical Notes
          </p>
          <ul className="space-y-1">
            {diseases.notes.map((note, i) => (
              <li key={i} className="text-sm text-slate-300 flex items-start gap-2">
                <span className="mt-1.5 w-1 h-1 rounded-full bg-orange-400 flex-shrink-0"></span>
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* AI-Assisted Recommendations */}
      {diseases.recommendations && diseases.recommendations.length > 0 && (
        <div className="mt-3 p-3 bg-blue-500/8 border border-blue-500/20 rounded-xl">
          <p className="text-sm font-semibold text-blue-400 mb-2 flex items-center gap-2">
            <ClipboardList className="w-4 h-4" />
            AI-Assisted Clinical Recommendations
          </p>
          <ol className="space-y-2">
            {diseases.recommendations.map((rec: string, i: number) => (
              <li key={i} className="text-sm text-blue-300/80 flex items-start gap-2">
                <span className="font-semibold text-blue-500 flex-shrink-0 min-w-[20px]">{i + 1}.</span>
                {rec}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
