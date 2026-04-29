import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Search, Trash2, RefreshCw, Activity } from 'lucide-react'
import { Layout } from '@/components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Input } from '@/components/ui/Input'
import {
  getStoredStudies,
  formatDate,
  truncateId,
  type StoredStudy,
} from '@/lib/utils'

function statusBadge(status: string) {
  switch (status) {
    case 'done': return <Badge variant="success">Done</Badge>
    case 'processing': return <Badge variant="default">Processing</Badge>
    case 'pending': return <Badge variant="secondary">Pending</Badge>
    case 'failed': return <Badge variant="danger">Failed</Badge>
    default: return <Badge variant="outline">{status}</Badge>
  }
}

export function StudiesPage() {
  const navigate = useNavigate()
  const [studies, setStudies] = useState<StoredStudy[]>([])
  const [query, setQuery] = useState('')

  const load = () => setStudies(getStoredStudies())

  useEffect(() => { load() }, [])

  const clearAll = () => {
    if (confirm('Clear all stored studies?')) {
      localStorage.removeItem('cordisai_recent_studies')
      setStudies([])
    }
  }

  const filtered = studies.filter(
    (s) =>
      !query ||
      s.patient_name.toLowerCase().includes(query.toLowerCase()) ||
      s.patient_id.toLowerCase().includes(query.toLowerCase()) ||
      s.study_id.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <Layout title="Recent Studies">
      <div className="max-w-4xl mx-auto space-y-6">
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-4">
            <div>
              <CardTitle>All Studies</CardTitle>
              <p className="text-xs text-slate-500 mt-0.5">
                {studies.length} studies stored locally
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={load} className="gap-1.5">
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh
              </Button>
              {studies.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={clearAll}
                  className="gap-1.5 text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Clear All
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="px-6 pb-2">
            <Input
              placeholder="Search by name, ID or study ID..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mb-0"
            />
          </CardContent>
          <CardContent className="p-0">
            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="w-14 h-14 rounded-full bg-surface-4 flex items-center justify-center mb-4">
                  <Activity className="w-6 h-6 text-slate-500" />
                </div>
                <p className="text-slate-400 font-medium">
                  {query ? 'No studies match your search' : 'No studies yet'}
                </p>
                {!query && (
                  <Button
                    className="mt-4"
                    size="sm"
                    onClick={() => navigate('/upload')}
                  >
                    Upload First Study
                  </Button>
                )}
              </div>
            ) : (
              <div className="divide-y divide-border">
                {/* Table header */}
                <div className="grid grid-cols-12 px-6 py-2 bg-surface-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <div className="col-span-1">#</div>
                  <div className="col-span-3">Patient</div>
                  <div className="col-span-2">Patient ID</div>
                  <div className="col-span-3">Submitted</div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-1"></div>
                </div>

                {filtered.map((study, i) => (
                  <div
                    key={study.study_id}
                    className="grid grid-cols-12 items-center px-6 py-3.5 hover:bg-surface-3 cursor-pointer transition-colors"
                    onClick={() =>
                      navigate(
                        study.status === 'done'
                          ? `/studies/${study.study_id}/results`
                          : `/studies/${study.study_id}`,
                      )
                    }
                  >
                    <div className="col-span-1 text-xs text-slate-600 font-mono">
                      {i + 1}
                    </div>
                    <div className="col-span-3">
                      <p className="font-medium text-slate-200 text-sm truncate">
                        {study.patient_name || 'Anonymous'}
                      </p>
                      <p className="text-xs text-slate-600 font-mono">
                        {truncateId(study.study_id)}
                      </p>
                    </div>
                    <div className="col-span-2 text-sm text-slate-400 truncate">
                      {study.patient_id || 'N/A'}
                    </div>
                    <div className="col-span-3 text-sm text-slate-500">
                      {formatDate(study.created_at)}
                    </div>
                    <div className="col-span-2">{statusBadge(study.status)}</div>
                    <div className="col-span-1 flex justify-end">
                      <ArrowRight className="w-4 h-4 text-slate-600" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Layout>
  )
}
