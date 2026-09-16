import { useMemo, useState } from "react"
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { format, parseISO } from "date-fns"

import type { TrendRow } from "@/lib/api"
import { fmt, platformColor } from "@/lib/format"
import { cn } from "@/lib/utils"

type DailyTrendChartProps = {
  data: TrendRow[]
  days: number
  className?: string
}

type SeriesConfig = {
  key: string
  name: string
  color: string
  dashed: boolean
  yAxisId: "left" | "right"
}

function buildDayLabels(days: number): string[] {
  const end = new Date()
  end.setHours(0, 0, 0, 0)
  const start = new Date(end)
  start.setDate(start.getDate() - (days - 1))

  const labels: string[] = []
  const cur = new Date(start)
  while (cur <= end) {
    labels.push(format(cur, "yyyy-MM-dd"))
    cur.setDate(cur.getDate() + 1)
  }
  return labels
}

function buildSeries(data: TrendRow[]): SeriesConfig[] {
  const platforms = [...new Set(data.map((row) => row.platform))]

  return [
    ...platforms.flatMap((platform) => [
      {
        key: `${platform}_views`,
        name: `${platform} · просмотры`,
        color: platformColor(platform),
        dashed: false,
        yAxisId: "left" as const,
      },
      {
        key: `${platform}_likes`,
        name: `${platform} · лайки`,
        color: platformColor(platform),
        dashed: true,
        yAxisId: "left" as const,
      },
    ]),
    {
      key: "web_sessions",
      name: "клики на сайт",
      color: "#34d399",
      dashed: true,
      yAxisId: "right" as const,
    },
  ]
}

export function DailyTrendChart({ data, days, className }: DailyTrendChartProps) {
  const [hidden, setHidden] = useState<Record<string, boolean>>({})
  const series = useMemo(() => buildSeries(data), [data])

  const chartData = useMemo(() => {
    const dayLabels = buildDayLabels(days)
    const platforms = [...new Set(data.map((row) => row.platform))]

    return dayLabels.map((date) => {
      const point: Record<string, string | number> = {
        date,
        label: format(parseISO(date), "dd.MM"),
      }

      for (const platform of platforms) {
        const row = data.find((item) => item.date === date && item.platform === platform)
        point[`${platform}_views`] = row?.views ?? 0
        point[`${platform}_likes`] = row?.likes ?? 0
      }

      point.web_sessions = data
        .filter((item) => item.date === date)
        .reduce((sum, item) => sum + (item.web_sessions || 0), 0)

      return point
    })
  }, [data, days])

  function toggleSeries(dataKey: string) {
    setHidden((prev) => ({ ...prev, [dataKey]: !prev[dataKey] }))
  }

  return (
    <div className={cn("h-[360px] w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid stroke="oklch(1 0 0 / 10%)" />
          <XAxis dataKey="label" tick={{ fill: "#9aa0a6", fontSize: 12 }} />
          <YAxis
            yAxisId="left"
            tick={{ fill: "#9aa0a6", fontSize: 12 }}
            tickFormatter={(value) => fmt(Number(value))}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fill: "#9aa0a6", fontSize: 12 }}
            tickFormatter={(value) => fmt(Number(value))}
          />
          <Tooltip
            formatter={(value) => fmt(Number(value ?? 0))}
            labelFormatter={(label) => String(label)}
            contentStyle={{
              background: "oklch(0.205 0 0)",
              border: "1px solid oklch(1 0 0 / 10%)",
              borderRadius: "8px",
            }}
          />
          <Legend
            onClick={(entry) => {
              const dataKey = entry?.dataKey
              if (typeof dataKey !== "string") return
              toggleSeries(dataKey)
            }}
            formatter={(value, entry) => {
              const dataKey = String(entry?.dataKey ?? "")
              const isHidden = Boolean(hidden[dataKey])
              return (
                <span
                  className={cn(
                    "cursor-pointer select-none text-xs",
                    isHidden && "text-muted-foreground line-through opacity-50",
                  )}
                >
                  {value}
                </span>
              )
            }}
          />
          {series.map((line) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.name}
              stroke={line.color}
              strokeDasharray={line.dashed ? "4 4" : undefined}
              dot={false}
              yAxisId={line.yAxisId}
              strokeWidth={2}
              hide={Boolean(hidden[line.key])}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
