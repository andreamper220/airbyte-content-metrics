import { useCallback, useEffect, useMemo, useState } from "react"

import {
  api,
  type CorrelationRow,
  type MetrikaStatus,
  type RefreshStatus,
  type SummaryRow,
  type VideoDetailResponse,
} from "@/lib/api"
import { fmt, platformColor } from "@/lib/format"
import { AppHeader } from "@/components/layout/app-header"
import { TrendChart } from "@/components/dashboard/trend-chart"
import { VideoDialog } from "@/components/dashboard/video-dialog"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const WEEKLY_PLATFORMS = new Set(["youtube", "tiktok", "instagram"])

function clickRowSpans(rows: CorrelationRow[]): number[] {
  const spans = Array.from({ length: rows.length }, () => 1)
  let i = 0
  while (i < rows.length) {
    const row = rows[i]
    const weekKey = WEEKLY_PLATFORMS.has(row.platform) ? `${row.platform}:${row.week_start}` : ""
    if (!weekKey) {
      i += 1
      continue
    }
    let j = i + 1
    while (j < rows.length && `${rows[j].platform}:${rows[j].week_start}` === weekKey) {
      spans[j] = 0
      j += 1
    }
    spans[i] = j - i
    i = j
  }
  return spans
}

export function DashboardPage() {
  const [days, setDays] = useState("30")
  const [refreshing, setRefreshing] = useState(false)
  const [summary, setSummary] = useState<SummaryRow[]>([])
  const [trend, setTrend] = useState<Awaited<ReturnType<typeof api.trend>>>([])
  const [correlation, setCorrelation] = useState<CorrelationRow[]>([])
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null)
  const [metrikaStatus, setMetrikaStatus] = useState<MetrikaStatus | null>(null)
  const [videoOpen, setVideoOpen] = useState(false)
  const [videoData, setVideoData] = useState<VideoDetailResponse | null>(null)
  const [videoError, setVideoError] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    const daysNum = Number(days)
    const [summaryData, trendData, correlationData, statusData, metrikaData] = await Promise.all([
      api.summary(daysNum),
      api.trend(daysNum),
      api.correlation(daysNum),
      api.refreshStatus(),
      api.metrikaStatus(daysNum),
    ])
    setSummary(summaryData)
    setTrend(trendData)
    setCorrelation(correlationData)
    setRefreshStatus(statusData)
    setMetrikaStatus(metrikaData)
  }, [days])

  const clickSpans = useMemo(() => clickRowSpans(correlation), [correlation])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadAll()
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [loadAll])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const status = await api.refresh()
      setRefreshStatus(status)
      await loadAll()
    } finally {
      setRefreshing(false)
    }
  }

  const statusLine = refreshStatus?.last_refresh_at
    ? `Обновлено: ${new Date(refreshStatus.last_refresh_at).toLocaleString("ru-RU")}${
        refreshStatus.auto_refresh_enabled
          ? ` · авто каждые ${refreshStatus.mart_refresh_interval_minutes} мин`
          : ""
      }`
    : "Загрузка…"

  async function openVideo(platform: string, videoId: string) {
    const id = videoId.trim()
    if (!id) return
    setVideoError(null)
    setVideoData(null)
    setVideoOpen(true)
    try {
      const data = await api.video(platform, id)
      setVideoData(data)
    } catch (err) {
      setVideoError(err instanceof Error ? err.message : "Не удалось загрузить ролик")
    }
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <AppHeader
        title="Content Analytics"
        subtitle={`YouTube · TikTok · Instagram · VK · Dzen · Яндекс.Метрика · ${statusLine}`}
        days={days}
        onDaysChange={setDays}
        onRefresh={handleRefresh}
        refreshing={refreshing}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summary.map((row) => (
          <Card key={row.platform}>
            <CardHeader className="pb-2">
              <CardTitle
                className="text-sm font-medium uppercase tracking-wide"
                style={{ color: platformColor(row.platform) }}
              >
                {row.platform}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{fmt(row.views)}</div>
              <p className="text-sm text-muted-foreground">
                {row.videos} видео · {fmt(row.likes)} лайков · {fmt(row.unique_clicks)} кликов
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-6">
        <TrendChart data={trend} days={Number(days)} />
      </div>

      {metrikaStatus && (
        <p className="mb-3 text-sm text-muted-foreground">
          Метрика: {fmt(metrikaStatus.raw_sessions)} визитов всего, {fmt(metrikaStatus.utm_sessions)} с UTM,{" "}
          {fmt(metrikaStatus.utm_sessions_period)} с UTM за выбранный период.
          {metrikaStatus.utm_sessions > 0 && metrikaStatus.utm_sessions_period === 0
            ? " Клики есть, но старше фильтра дат — поставьте 90 дней."
            : ""}
          {metrikaStatus.error ? ` ${metrikaStatus.error}` : ""}
        </p>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Площадка по дням</CardTitle>
          <p className="text-sm text-muted-foreground">
            YouTube / TikTok / Instagram: колонка «Клики» общая на всю неделю (ссылка в bio), даже если роликов несколько.
            VK / Дзен: клики за этот день. Цифра по ролику — откройте строку.
          </p>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[480px] rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Дата</TableHead>
                  <TableHead>Платформа</TableHead>
                  <TableHead>Просмотры</TableHead>
                  <TableHead>Топ-видео дня</TableHead>
                  <TableHead>Клики</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {correlation.map((row, index) => (
                  <TableRow
                    key={`${row.date}-${row.platform}-${row.top_video_id ?? "none"}`}
                    className={row.top_video_id ? "cursor-pointer" : undefined}
                    onClick={() => {
                      if (row.top_video_id) {
                        void openVideo(row.platform, row.top_video_id)
                      }
                    }}
                  >
                    <TableCell>{row.date}</TableCell>
                    <TableCell>
                      <Badge style={{ color: platformColor(row.platform) }}>{row.platform}</Badge>
                    </TableCell>
                    <TableCell>{fmt(row.total_views)}</TableCell>
                    <TableCell>{row.top_video_title || "—"}</TableCell>
                    {clickSpans[index] > 0 ? (
                      <TableCell rowSpan={clickSpans[index]} className="align-middle">
                        <div className="font-medium">{fmt(row.unique_clicks)}</div>
                        {row.clicks_scope === "week" && row.week_start ? (
                          <div className="text-xs text-muted-foreground">
                            неделя {row.week_start} — {row.week_end}
                          </div>
                        ) : (
                          <div className="text-xs text-muted-foreground">за день</div>
                        )}
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      <VideoDialog
        open={videoOpen}
        onOpenChange={(open) => {
          setVideoOpen(open)
          if (!open) {
            setVideoData(null)
            setVideoError(null)
          }
        }}
        data={videoData}
        error={videoError}
      />
    </div>
  )
}
