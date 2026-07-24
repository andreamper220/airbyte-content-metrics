import type { TrendRow } from "@/lib/api"
import { DailyTrendChart } from "@/components/charts/daily-trend-chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

type TrendChartProps = {
  data: TrendRow[]
  days: number
}

export function TrendChart({ data, days }: TrendChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
          Динамика по дням — клик по легенде скрывает линию
        </CardTitle>
      </CardHeader>
      <CardContent>
        <DailyTrendChart data={data} days={days} />
      </CardContent>
    </Card>
  )
}
