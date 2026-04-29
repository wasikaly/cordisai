import type {
  StudyStatus,
  AnalysisResult,
  HealthStatus,
  UploadFormData,
} from '@/types/api'

const BASE_URL = 'http://localhost:8002'

// ── Generic fetch wrapper ────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      detail = body?.detail ?? detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>('/api/v1/health')
}

export async function submitAnalysis(
  file: File,
  form: UploadFormData,
): Promise<StudyStatus> {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('patient_name', form.patient_name || 'Anonymous')
  fd.append('patient_id', form.patient_id || 'N/A')
  fd.append('patient_dob', form.patient_dob || 'N/A')
  fd.append('study_date', form.study_date || '')
  fd.append('sex', form.sex || '')
  fd.append('height_cm', form.height_cm || '0')
  fd.append('weight_kg', form.weight_kg || '0')
  fd.append('heart_rate', form.heart_rate || '0')

  return apiFetch<StudyStatus>('/api/v1/analyze', {
    method: 'POST',
    body: fd,
  })
}

export async function getStudyStatus(studyId: string): Promise<StudyStatus> {
  return apiFetch<StudyStatus>(`/api/v1/studies/${studyId}/status`)
}

export async function getStudyResults(studyId: string): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(`/api/v1/studies/${studyId}`)
}

export function getReportUrl(studyId: string): string {
  return `${BASE_URL}/api/v1/studies/${studyId}/report`
}

export function getFhirUrl(studyId: string): string {
  return `${BASE_URL}/api/v1/studies/${studyId}/fhir`
}

export async function downloadFhir(studyId: string): Promise<void> {
  const res = await fetch(getFhirUrl(studyId))
  if (!res.ok) throw new Error('Failed to download FHIR bundle')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cordisai_fhir_${studyId}.json`
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadReport(studyId: string): Promise<void> {
  const res = await fetch(getReportUrl(studyId))
  if (!res.ok) throw new Error('Failed to download PDF report')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `cordisai_report_${studyId}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
