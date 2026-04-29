import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

interface LVAreaChartProps {
  lvAreas: number[]
  edFrame?: number
  esFrame?: number
}

export function LVAreaChart({ lvAreas, edFrame, esFrame }: LVAreaChartProps) {
  if (!lvAreas || lvAreas.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
        No cardiac cycle data available
      </div>
    )
  }

  const data = lvAreas.map((area, i) => ({
    frame: i,
    area: typeof area === 'number' ? parseFloat(area.toFixed(2)) : 0,
  }))

  const maxArea = Math.max(...lvAreas)
  const minArea = Math.min(...lvAreas)

  return (
    <div>
      <div className="flex items-center gap-4 mb-3 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="w-3 h-0.5 bg-primary-500 inline-block"></span>
          LV Area
        </span>
        {edFrame !== undefined && (
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-emerald-500 border-dashed inline-block"></span>
            ED frame
          </span>
        )}
        {esFrame !== undefined && (
          <span className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-red-500 border-dashed inline-block"></span>
            ES frame
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2a" />
          <XAxis
            dataKey="frame"
            tick={{ fontSize: 11, fill: '#475569' }}
            tickLine={false}
            axisLine={false}
            label={{ value: 'Frame', position: 'insideBottom', offset: -2, fontSize: 11, fill: '#475569' }}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#475569' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}`}
            domain={[Math.max(0, minArea - 5), maxArea + 5]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#141419',
              border: '1px solid #1e1e2a',
              borderRadius: '8px',
              padding: '8px 12px',
              color: '#e2e8f0',
              fontSize: '12px',
            }}
            formatter={(val: number) => [`${val.toFixed(1)} px²`, 'LV Area']}
            labelFormatter={(label) => `Frame ${label}`}
          />
          {edFrame !== undefined && (
            <ReferenceLine
              x={edFrame}
              stroke="#22c55e"
              strokeDasharray="4 2"
              label={{ value: 'ED', position: 'top', fontSize: 10, fill: '#22c55e' }}
            />
          )}
          {esFrame !== undefined && (
            <ReferenceLine
              x={esFrame}
              stroke="#ef4444"
              strokeDasharray="4 2"
              label={{ value: 'ES', position: 'top', fontSize: 10, fill: '#ef4444' }}
            />
          )}
          <Line
            type="monotone"
            dataKey="area"
            stroke="#e11d48"
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, fill: '#e11d48' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
