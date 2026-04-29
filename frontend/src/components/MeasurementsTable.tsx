import { Badge } from '@/components/ui/Badge'
import type { Measurements } from '@/types/api'

interface MeasRow {
  key: keyof Measurements
  label: string
  fullLabel: string
  normalRange: string
}

const SECTIONS: { title: string; rows: MeasRow[] }[] = [
  {
    title: 'LV Systolic Function',
    rows: [
      { key: 'LVEF',    label: 'LVEF',          fullLabel: 'LV Ejection Fraction (biplane)',   normalRange: '53–73 %' },
      { key: 'LVEDV',   label: 'LVEDV',          fullLabel: 'LV End-Diastolic Volume',          normalRange: '56–104 mL' },
      { key: 'LVESV',   label: 'LVESV',          fullLabel: 'LV End-Systolic Volume',           normalRange: '19–49 mL' },
      { key: 'LVEDVi',  label: 'LVEDVi',         fullLabel: 'LVEDV indexed to BSA',             normalRange: '34–74 mL/m²' },
      { key: 'LVESVi',  label: 'LVESVi',         fullLabel: 'LVESV indexed to BSA',             normalRange: '11–31 mL/m²' },
      { key: 'LVSV',    label: 'LVSV',           fullLabel: 'LV Stroke Volume',                 normalRange: '—' },
      { key: 'CO',      label: 'CO',             fullLabel: 'Cardiac Output',                   normalRange: '4–8 L/min' },
    ],
  },
  {
    title: 'LV Dimensions & Wall Thickness',
    rows: [
      { key: 'IVSd',         label: 'IVSd',          fullLabel: 'Interventricular Septum (diastole)',  normalRange: '0.6–1.0 cm' },
      { key: 'LVIDd',        label: 'LVIDd',         fullLabel: 'LV Internal Diameter (diastole)',     normalRange: '3.9–5.3 cm' },
      { key: 'LVIDs',        label: 'LVIDs',         fullLabel: 'LV Internal Diameter (systole)',      normalRange: '2.5–4.0 cm' },
      { key: 'LVIDd_index',  label: 'LVIDd index',   fullLabel: 'LVIDd indexed to BSA',               normalRange: 'M: 2.2–3.1 · F: 2.0–2.9 cm/m²' },
      { key: 'LVIDs_index',  label: 'LVIDs index',   fullLabel: 'LVIDs indexed to BSA',               normalRange: 'M: 1.2–2.1 · F: 1.1–1.9 cm/m²' },
      { key: 'LVPWd',        label: 'LVPWd',         fullLabel: 'LV Posterior Wall (diastole)',        normalRange: '0.6–1.0 cm' },
      { key: 'RWT',          label: 'RWT',           fullLabel: 'Relative Wall Thickness',             normalRange: '≤ 0.42' },
    ],
  },
  {
    title: 'LV Mass',
    rows: [
      { key: 'LVM',  label: 'LV mass',    fullLabel: 'LV Mass (ASE cubed)',      normalRange: 'M: 88–224 g · F: 67–162 g' },
      { key: 'LVMi', label: 'LVM index',  fullLabel: 'LV Mass indexed to BSA',  normalRange: 'M: 49–115 g/m² · F: 43–95 g/m²' },
    ],
  },
  {
    title: 'Global Strain',
    rows: [
      { key: 'GLS', label: 'GLS', fullLabel: 'Global Longitudinal Strain', normalRange: '-20 to -16 %' },
    ],
  },
  {
    title: 'Left Atrium',
    rows: [
      { key: 'LA_area', label: 'LA area',  fullLabel: 'Left Atrial Area',               normalRange: '≤ 20 cm²' },
      { key: 'LAV',     label: 'LAV',      fullLabel: 'Left Atrial Volume',             normalRange: 'M: ≤ 58 mL · F: ≤ 52 mL' },
      { key: 'LAVi',    label: 'LAVi',     fullLabel: 'Left Atrial Volume indexed',     normalRange: '≤ 34 mL/m²' },
    ],
  },
]

function fmt(value: number, unit: string): string {
  if (unit === '%') return value.toFixed(1)
  if (unit === '' || unit === 'ratio') return value.toFixed(2)
  if (unit === 'L/min') return value.toFixed(1)
  return value.toFixed(1)
}

interface MeasurementsTableProps {
  measurements: Measurements
}

export function MeasurementsTable({ measurements }: MeasurementsTableProps) {
  return (
    <div className="space-y-0">
      {SECTIONS.map((section) => {
        const visibleRows = section.rows
          .map((r) => {
            const entry = measurements[r.key]
            if (!entry || typeof entry !== 'object' || !('value' in entry)) return null
            const m = entry as { value: number | null; unit: string; flag: 'LOW' | 'HIGH' | null }
            if (m.value === null || m.value === undefined) return null
            return { ...r, value: m.value, unit: m.unit, flag: m.flag }
          })
          .filter(Boolean) as Array<MeasRow & { value: number; unit: string; flag: 'LOW' | 'HIGH' | null }>

        if (visibleRows.length === 0) return null

        return (
          <div key={section.title}>
            <div className="px-4 py-2 bg-surface-3 border-b border-t border-border">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {section.title}
              </span>
            </div>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-border">
                {visibleRows.map((row) => (
                  <tr key={row.key} className="hover:bg-surface-3 transition-colors">
                    <td className="py-2.5 px-4">
                      <span className="font-medium text-slate-200">{row.label}</span>
                      <span className="hidden sm:inline text-xs text-slate-500 ml-2">
                        {row.fullLabel}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span className={`font-semibold tabular-nums ${row.flag ? 'text-red-400' : 'text-slate-100'}`}>
                        {fmt(row.value, row.unit)}
                      </span>
                      {row.unit && (
                        <span className="ml-1 text-slate-500 text-xs">{row.unit}</span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-center w-24">
                      {row.flag === 'HIGH' ? (
                        <Badge variant="danger">HIGH</Badge>
                      ) : row.flag === 'LOW' ? (
                        <Badge variant="warning">LOW</Badge>
                      ) : (
                        <Badge variant="success">Normal</Badge>
                      )}
                    </td>
                    <td className="py-2.5 px-4 text-right text-slate-600 text-xs whitespace-nowrap">
                      {row.normalRange}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      })}

      {/* Classifications footer */}
      {(measurements.EF_category || measurements.LV_geometry) && (
        <div className="flex gap-3 mt-3 px-4 pb-1">
          {measurements.EF_category && (
            <div className="flex-1 px-3 py-2 rounded-lg bg-surface-3 border border-border">
              <span className="text-xs text-slate-500">EF Class: </span>
              <span className="text-sm font-medium text-slate-200">{measurements.EF_category}</span>
            </div>
          )}
          {measurements.LV_geometry && (
            <div className="flex-1 px-3 py-2 rounded-lg bg-surface-3 border border-border">
              <span className="text-xs text-slate-500">LV Geometry: </span>
              <span className="text-sm font-medium text-slate-200">{measurements.LV_geometry}</span>
            </div>
          )}
          {measurements.GLS_category && (
            <div className="flex-1 px-3 py-2 rounded-lg bg-surface-3 border border-border">
              <span className="text-xs text-slate-500">GLS: </span>
              <span className="text-sm font-medium text-slate-200">{measurements.GLS_category}</span>
              {measurements.GLS_reliable === false && (
                <span className="ml-2 text-xs text-amber-400">⚠ low reliability</span>
              )}
            </div>
          )}
          {measurements.BSA && typeof measurements.BSA === 'object' && (
            <div className="flex-1 px-3 py-2 rounded-lg bg-surface-3 border border-border">
              <span className="text-xs text-slate-500">BSA: </span>
              <span className="text-sm font-medium text-slate-200">
                {(measurements.BSA as { value: number; unit: string }).value.toFixed(2)} m²
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
