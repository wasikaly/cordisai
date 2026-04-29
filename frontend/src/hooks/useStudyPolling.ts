import { useState, useEffect, useRef, useCallback } from 'react'
import { getStudyStatus, getStudyResults } from '@/api/client'
import type { StudyStatus, AnalysisResult, StudyStatusValue } from '@/types/api'

interface UseStudyPollingResult {
  status: StudyStatus | null
  result: AnalysisResult | null
  error: string | null        // analysis failed error
  resultError: string | null  // result fetch error (analysis succeeded but results unavailable)
  isPolling: boolean
  currentStatus: StudyStatusValue | null
}

const POLL_INTERVAL_MS = 3000

export function useStudyPolling(studyId: string | null): UseStudyPollingResult {
  const [status, setStatus] = useState<StudyStatus | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [resultError, setResultError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeRef = useRef(true)

  const fetchStatus = useCallback(async (id: string) => {
    try {
      const s = await getStudyStatus(id)
      if (!activeRef.current) return
      setStatus(s)

      if (s.status === 'done') {
        setIsPolling(false)
        // Fetch full results
        try {
          const r = await getStudyResults(id)
          if (activeRef.current) setResult(r)
        } catch (e) {
          if (activeRef.current) setResultError((e as Error).message)
        }
      } else if (s.status === 'failed') {
        setIsPolling(false)
        setError(s.error ?? 'Analysis failed')
      } else {
        // Still pending/processing — poll again
        timerRef.current = setTimeout(() => fetchStatus(id), POLL_INTERVAL_MS)
      }
    } catch (e) {
      if (!activeRef.current) return
      const msg = (e as Error).message
      // Network error — keep polling with a delay
      if (msg.includes('fetch') || msg.includes('network') || msg.includes('Failed')) {
        timerRef.current = setTimeout(() => fetchStatus(id), POLL_INTERVAL_MS * 2)
      } else {
        setError(msg)
        setIsPolling(false)
      }
    }
  }, [])

  useEffect(() => {
    if (!studyId) return
    activeRef.current = true
    setError(null)
    setResultError(null)
    setResult(null)
    setStatus(null)
    setIsPolling(true)

    fetchStatus(studyId)

    return () => {
      activeRef.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [studyId, fetchStatus])

  return {
    status,
    result,
    error,
    resultError,
    isPolling,
    currentStatus: status?.status ?? null,
  }
}
