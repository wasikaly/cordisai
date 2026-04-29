import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
} from 'recharts'
import { getEFColor, getEFZone } from '@/lib/utils'

interface EFGaugeProps {
  ef: number
}

export function EFGauge({ ef: rawEf }: EFGaugeProps) {
  const ef = Math.max(0, Math.min(100, rawEf))
  const color = getEFColor(ef)
  const zone = getEFZone(ef)

  const filled = ef
  const empty = 100 - ef

  const data = [
    { name: 'ef', value: filled },
    { name: 'empty', value: empty },
  ]

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-56 h-32">
        <ResponsiveContainer width="100%" height={160}>
          <PieChart>
            {/* Background ring */}
            <Pie
              data={[{ value: 100 }]}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={70}
              outerRadius={88}
              fill="#1e1e2a"
              strokeWidth={0}
              dataKey="value"
              isAnimationActive={false}
            />
            {/* EF arc */}
            <Pie
              data={data}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={70}
              outerRadius={88}
              strokeWidth={0}
              dataKey="value"
              animationBegin={0}
              animationDuration={800}
            >
              <Cell fill={color} />
              <Cell fill="transparent" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Center text overlay */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
          <span className="text-4xl font-bold" style={{ color }}>
            {ef.toFixed(0)}
            <span className="text-xl font-semibold text-slate-500">%</span>
          </span>
        </div>
      </div>

      {/* Zone label */}
      <div className={`mt-1 px-3 py-1 rounded-full text-sm font-semibold ${zone.bg} ${zone.color}`}>
        {zone.label}
      </div>

      {/* Scale labels */}
      <div className="flex justify-between w-52 mt-2 px-1">
        <span className="text-xs text-slate-600">0%</span>
        <span className="text-xs text-red-500">40%</span>
        <span className="text-xs text-amber-500">53%</span>
        <span className="text-xs text-slate-600">100%</span>
      </div>

      {/* Color legend */}
      <div className="flex items-center gap-4 mt-3 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span>
          &lt;40% Reduced
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-500 inline-block"></span>
          40–53% Border
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
          &gt;53% Normal
        </span>
      </div>
    </div>
  )
}
