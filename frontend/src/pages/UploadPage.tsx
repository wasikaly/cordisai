import { useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Upload,
  FileVideo,
  FileX,
  X,
  AlertCircle,
  ArrowRight,
} from 'lucide-react'
import { Layout } from '@/components/Layout'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Alert } from '@/components/ui/Alert'
import { submitAnalysis } from '@/api/client'
import { saveStudy } from '@/lib/utils'
import type { UploadFormData } from '@/types/api'
import { cn } from '@/lib/utils'

const ACCEPTED = ['.avi', '.dcm']
const MAX_SIZE_MB = 500

function isValidFile(file: File): { ok: boolean; reason?: string } {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!ACCEPTED.includes(ext)) {
    return { ok: false, reason: `File type "${ext}" not supported. Use .avi or .dcm` }
  }
  if (file.size > MAX_SIZE_MB * 1024 * 1024) {
    return { ok: false, reason: `File is too large (max ${MAX_SIZE_MB} MB)` }
  }
  return { ok: true }
}

function FilePreview({ file, onRemove }: { file: File; onRemove: () => void }) {
  const ext = file.name.split('.').pop()?.toLowerCase()
  const sizeMB = (file.size / (1024 * 1024)).toFixed(1)

  return (
    <div className="flex items-center gap-3 p-4 bg-primary-600/10 border border-primary-600/30 rounded-xl">
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-primary-600">
        <FileVideo className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-slate-200 truncate">{file.name}</p>
        <p className="text-xs text-slate-500">
          {ext?.toUpperCase()} · {sizeMB} MB
        </p>
      </div>
      <button
        onClick={onRemove}
        className="p-1.5 rounded-lg hover:bg-surface-4 text-slate-500 hover:text-slate-300 transition-colors"
        aria-label="Remove file"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  )
}

export function UploadPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const [form, setForm] = useState<UploadFormData>({
    patient_name: '',
    patient_id: '',
    patient_dob: '',
    study_date: new Date().toISOString().slice(0, 10),
    sex: '',
    height_cm: '',
    weight_kg: '',
    heart_rate: '',
  })

  const handleFile = useCallback((f: File) => {
    const check = isValidFile(f)
    if (!check.ok) {
      setFileError(check.reason ?? 'Invalid file')
      setFile(null)
    } else {
      setFileError(null)
      setFile(f)
    }
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragging(false)
      const dropped = e.dataTransfer.files[0]
      if (dropped) handleFile(dropped)
    },
    [handleFile],
  )

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => setIsDragging(false)

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) handleFile(f)
  }

  const handleFormChange = (field: keyof UploadFormData) => (
    e: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setForm(prev => ({ ...prev, [field]: e.target.value }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setFileError('Please select an echo file to upload')
      return
    }

    setSubmitting(true)
    setSubmitError(null)

    try {
      const status = await submitAnalysis(file, form)
      saveStudy({
        study_id: status.study_id,
        patient_name: form.patient_name || 'Anonymous',
        patient_id: form.patient_id || 'N/A',
        created_at: status.created_at,
        status: status.status,
      })
      navigate(`/studies/${status.study_id}`)
    } catch (err) {
      setSubmitError((err as Error).message)
      setSubmitting(false)
    }
  }

  return (
    <Layout title="New Analysis">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Upload area */}
        <Card>
          <CardHeader>
            <CardTitle>Upload Echo File</CardTitle>
            <p className="text-sm text-slate-500 mt-0.5">
              Supported formats: AVI video (.avi) or DICOM (.dcm)
            </p>
          </CardHeader>
          <CardContent>
            {file ? (
              <FilePreview file={file} onRemove={() => setFile(null)} />
            ) : (
              <div
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                className={cn(
                  'relative flex flex-col items-center justify-center gap-4',
                  'border-2 border-dashed rounded-xl p-10 cursor-pointer',
                  'transition-colors',
                  isDragging
                    ? 'border-primary-500 bg-primary-600/10'
                    : 'border-surface-4 hover:border-primary-600/50 hover:bg-surface-3',
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".avi,.dcm"
                  className="sr-only"
                  onChange={handleInputChange}
                />
                <div className="flex items-center justify-center w-14 h-14 rounded-full bg-primary-600/15 border-2 border-primary-600/30">
                  <Upload className="w-6 h-6 text-primary-400" />
                </div>
                <div className="text-center">
                  <p className="font-medium text-slate-300">
                    Drag & drop your echo file
                  </p>
                  <p className="text-sm text-slate-500 mt-1">
                    or click to browse — .avi or .dcm up to {MAX_SIZE_MB} MB
                  </p>
                </div>
              </div>
            )}

            {fileError && (
              <div className="flex items-center gap-2 mt-3 text-sm text-red-400">
                <FileX className="w-4 h-4 flex-shrink-0" />
                <span>{fileError}</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Patient info */}
        <form onSubmit={handleSubmit}>
          <Card>
            <CardHeader>
              <CardTitle>Patient Information</CardTitle>
              <p className="text-sm text-slate-500 mt-0.5">
                Optional — used in the generated PDF report
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Patient Name"
                  placeholder="Jane Smith"
                  value={form.patient_name}
                  onChange={handleFormChange('patient_name')}
                />
                <Input
                  label="Patient ID"
                  placeholder="PT-001"
                  value={form.patient_id}
                  onChange={handleFormChange('patient_id')}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Date of Birth"
                  type="date"
                  value={form.patient_dob}
                  onChange={handleFormChange('patient_dob')}
                />
                <Input
                  label="Study Date"
                  type="date"
                  value={form.study_date}
                  onChange={handleFormChange('study_date')}
                />
              </div>

              {/* Clinical parameters */}
              <div className="pt-2 border-t border-border">
                <p className="text-xs font-medium text-slate-500 mb-3 uppercase tracking-wide">
                  Clinical Parameters <span className="normal-case font-normal text-slate-600">(optional — enables indexed measurements)</span>
                </p>
                <div className="grid grid-cols-4 gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-sm font-medium text-slate-300">Sex</label>
                    <div className="flex gap-1">
                      {(['M', 'F'] as const).map(s => (
                        <button
                          key={s}
                          type="button"
                          onClick={() => setForm(prev => ({ ...prev, sex: prev.sex === s ? '' : s }))}
                          className={cn(
                            'flex-1 py-2 rounded-lg text-sm font-medium border transition-colors',
                            form.sex === s
                              ? 'bg-primary-600 text-white border-primary-600'
                              : 'bg-surface-3 text-slate-400 border-slate-600 hover:border-primary-600/50',
                          )}
                        >
                          {s === 'M' ? 'Male' : 'Female'}
                        </button>
                      ))}
                    </div>
                  </div>
                  <Input
                    label="Height (cm)"
                    type="number"
                    placeholder="170"
                    min={100}
                    max={220}
                    value={form.height_cm}
                    onChange={handleFormChange('height_cm')}
                  />
                  <Input
                    label="Weight (kg)"
                    type="number"
                    placeholder="70"
                    min={30}
                    max={250}
                    value={form.weight_kg}
                    onChange={handleFormChange('weight_kg')}
                  />
                  <Input
                    label="Heart Rate (bpm)"
                    type="number"
                    placeholder="72"
                    min={30}
                    max={200}
                    value={form.heart_rate}
                    onChange={handleFormChange('heart_rate')}
                  />
                </div>
              </div>

              {submitError && (
                <Alert variant="error" title="Submission Failed">
                  <div className="flex items-start gap-1.5">
                    <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                    <span>{submitError}</span>
                  </div>
                </Alert>
              )}

              <div className="flex items-center justify-between pt-2">
                <p className="text-xs text-slate-600">
                  Analysis typically takes 30–120 seconds
                </p>
                <Button
                  type="submit"
                  loading={submitting}
                  disabled={!file || submitting}
                  className="gap-2"
                >
                  Start Analysis
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </form>

        <Alert variant="info" title="What happens after upload?">
          <ol className="list-decimal list-inside space-y-1 text-sm">
            <li>File is uploaded to the CordisAI backend (FastAPI)</li>
            <li>U-Net segments LV cavity, myocardium, and LA per frame</li>
            <li>Simpson biplane computes LVEF, LVEDV, LVESV + 18 more measurements</li>
            <li>7 disease conditions flagged with clinical recommendations</li>
            <li>PDF, FHIR R4, and DICOM SR reports are generated</li>
          </ol>
        </Alert>
      </div>
    </Layout>
  )
}
