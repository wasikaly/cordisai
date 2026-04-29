import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from '@/pages/Dashboard'
import { UploadPage } from '@/pages/UploadPage'
import { StudyStatusPage } from '@/pages/StudyStatusPage'
import { ResultsPage } from '@/pages/ResultsPage'
import { StudiesPage } from '@/pages/StudiesPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/studies" element={<StudiesPage />} />
        <Route path="/studies/:studyId" element={<StudyStatusPage />} />
        <Route path="/studies/:studyId/results" element={<ResultsPage />} />
        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
