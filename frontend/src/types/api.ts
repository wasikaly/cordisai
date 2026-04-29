// ── API Response Types ─────────────────────────────────────────────────────

export type StudyStatusValue = 'pending' | 'processing' | 'done' | 'failed'

export interface StudyStatus {
  study_id: string
  status: StudyStatusValue
  created_at: string
  completed_at?: string | null
  error?: string | null
}

export interface MeasurementEntry {
  value: number
  unit: string
  flag: 'LOW' | 'HIGH' | null
}

export interface Measurements {
  // Core function
  LVEF?: MeasurementEntry
  LVEDV?: MeasurementEntry
  LVESV?: MeasurementEntry
  LVEDVi?: MeasurementEntry
  LVESVi?: MeasurementEntry
  LVSV?: MeasurementEntry
  // Dimensions
  IVSd?: MeasurementEntry
  LVIDd?: MeasurementEntry
  LVIDs?: MeasurementEntry
  LVPWd?: MeasurementEntry
  LVIDd_index?: MeasurementEntry
  LVIDs_index?: MeasurementEntry
  RWT?: MeasurementEntry
  // Mass
  LVM?: MeasurementEntry
  LVMi?: MeasurementEntry
  // LA
  LA_area?: MeasurementEntry
  LAV?: MeasurementEntry
  LAVi?: MeasurementEntry
  // Haemodynamics
  CO?: MeasurementEntry
  GLS?: MeasurementEntry
  BSA?: MeasurementEntry
  // GLS
  GLS_category?: string
  GLS_reliable?: boolean
  // Classifications
  EF_category?: string
  LV_geometry?: string
  // Frame info
  ed_frame?: number
  es_frame?: number
  lv_areas?: number[]
}

export interface DiseaseEntry {
  flag: boolean
  type?: string
  confidence?: string
}

export interface RiskAssessment {
  flag: boolean
  risk_factors?: string[]
  indicators?: string[]
}

export interface Diseases {
  heart_failure?: DiseaseEntry
  lv_hypertrophy?: DiseaseEntry
  lv_dilatation?: DiseaseEntry
  la_enlargement?: DiseaseEntry
  amyloidosis_suspicion?: DiseaseEntry
  diastolic_dysfunction_risk?: RiskAssessment
  valvular_disease_risk?: RiskAssessment
  notes?: string[]
  recommendations?: string[]
}

export interface ViewClassification {
  label?: string
  confidence?: number
  // pipeline may return {view: "A4C", confidence: 0.92} or {label: "A4C", ...}
  view?: string
  [key: string]: unknown
}

export interface AnalysisResult {
  study_id: string
  status: string
  mode: string
  view: ViewClassification
  measurements: Measurements
  diseases: Diseases
  report_path?: string | null
  frame_count?: number
}

export interface HealthStatus {
  status: string
  cuda_available: boolean
  active_jobs: number
}

// ── Local state types ────────────────────────────────────────────────────────

export interface RecentStudy {
  study_id: string
  patient_name: string
  patient_id: string
  created_at: string
  status: StudyStatusValue
  ef?: number
}

export interface UploadFormData {
  patient_name: string
  patient_id: string
  patient_dob: string
  study_date: string
  sex: 'M' | 'F' | ''
  height_cm: string
  weight_kg: string
  heart_rate: string
}
