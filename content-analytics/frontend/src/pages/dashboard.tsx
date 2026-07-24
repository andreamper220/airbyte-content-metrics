import { useCallback, useEffect, useState } from "react"

import { api, type CorrelationRow, type RefreshStatus, type SummaryRow, type VideoDetailResponse, type ViralRow } from "@/lib/api"
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

export function DashboardPage() {
  const [days, setDays] = useState("30")
  const [refreshing, setRefreshing] = useState(false)
  const [summary, setSummary] = useState<SummaryRow[]>([])
  const [trend, setTrend] = useState<Awaited<ReturnType<typeof api.trend>>>([])
  const [correlation, setCorrelation] = useState<CorrelationRow[]>([])
  const [viral, setViral] = useState<ViralRow[]>([])
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null)
  const [videoOpen, setVideoOpen] = useState(false)
  const [videoData, setVideoData] = useState<VideoDetailResponse | null>(null)

  const loadAll = useCallback(async () => {
    const daysNum = Number(days)
    const [summaryData, trendData, correlationData, viralData, statusData] = await Promise.all([
      api.summary(daysNum),
      api.trend(daysNum),
      api.correlation(daysNum),
      api.viral(daysNum),
      api.refreshStatus(),
    ])
    setSummary(summaryData)
    setTrend(trendData)
    setCorrelation(correlationData)
    setViral(viralData)
    setRefreshStatus(statusData)
  }, [days])

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
    const data = await api.video(platform, videoId)
    setVideoData(data)
    setVideoOpen(true)
  }

  return (
    <div className="mx-auto max-w-7xl p-6">
      <AppHeader
        title="Content Analytics"
        subtitle={`YouTube · TikTok · Instagram · Яндекс.Метрика · ${statusLine}`}
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
                {row.videos} видео · {fmt(row.likes)} лайков
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-6">
        <TrendChart data={trend} days={Number(days)} />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Корреляция: платформа → UTM source → сессии</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[330px] rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Дата</TableHead>
                  <TableHead>Платформа</TableHead>
                  <TableHead>Просмотры</TableHead>
                  <TableHead>Топ-видео</TableHead>
                  <TableHead>Сессии (web)</TableHead>
                  <TableHead>sessions/view</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {correlation.map((row) => (
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
                    <TableCell>{fmt(row.web_sessions)}</TableCell>
                    <TableCell>{row.sessions_per_view ?? "—"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Топ роликов («выстрелившие»)</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[330px] rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Платформа</TableHead>
                  <TableHead>Название</TableHead>
                  <TableHead>Просмотры</TableHead>
                  <TableHead>Лайки</TableHead>
                  <TableHead>Сессии в день публикации</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {viral.map((row) => (
                  <TableRow
                    key={`${row.platform}-${row.video_id}`}
                    className="cursor-pointer"
                    onClick={() => void openVideo(row.platform, row.video_id)}
                  >
                    <TableCell>
                      <Badge style={{ color: platformColor(row.platform) }}>{row.platform}</Badge>
                    </TableCell>
                    <TableCell>{row.title?.slice(0, 60) || "—"}</TableCell>
                    <TableCell>{fmt(row.views)}</TableCell>
                    <TableCell>{fmt(row.likes)}</TableCell>
                    <TableCell>{fmt(row.publish_day_sessions)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      <VideoDialog open={videoOpen} onOpenChange={setVideoOpen} data={videoData} />
    </div>
  )
}
