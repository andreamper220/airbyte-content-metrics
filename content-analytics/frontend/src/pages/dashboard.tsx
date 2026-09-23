import { useCallback, useEffect, useMemo, useState } from "react"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"
import { useLocation, useNavigate } from "react-router-dom"

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
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const WEEKLY_PLATFORMS = new Set(["youtube", "tiktok", "instagram", "dzen"])

type SortKey = "date" | "platform" | "views" | "title" | "clicks"
type SortDir = "asc" | "desc"

type ColumnFilters = {
  date: string
  platform: string
  views: string
  title: string
  clicks: string
}

const EMPTY_FILTERS: ColumnFilters = {
  date: "",
  platform: "",
  views: "",
  title: "",
  clicks: "",
}

const SORT_COLUMNS: { key: SortKey; label: string }[] = [
  { key: "date", label: "Дата" },
  { key: "platform", label: "Платформа" },
  { key: "views", label: "Просмотры" },
  { key: "title", label: "Заголовок" },
  { key: "clicks", label: "Клики" },
]

function rowViews(row: CorrelationRow): number {
  return row.platform === "vk" ? row.total_views : (row.top_video_views ?? row.total_views)
}

function rowTitle(row: CorrelationRow): string {
  return row.platform === "vk" ? "" : row.top_video_title || ""
}

function rowClicks(row: CorrelationRow): number {
  return row.unique_clicks ?? 0
}

function matchesNumber(value: number, query: string): boolean {
  const needle = query.trim().toLowerCase().replace(/\s/g, "")
  if (!needle) return true
  return String(value).includes(needle) || fmt(value).toLowerCase().includes(needle)
}

function compareRows(a: CorrelationRow, b: CorrelationRow, key: SortKey): number {
  switch (key) {
    case "date":
      return a.date.localeCompare(b.date)
    case "platform":
      return a.platform.localeCompare(b.platform)
    case "views":
      return rowViews(a) - rowViews(b)
    case "title":
      return rowTitle(a).localeCompare(rowTitle(b), "ru")
    case "clicks":
      return rowClicks(a) - rowClicks(b)
  }
}

function rowMatchesFilters(row: CorrelationRow, filters: ColumnFilters): boolean {
  if (filters.date && !row.date.includes(filters.date.trim())) return false
  if (filters.platform && row.platform !== filters.platform) return false
  if (!matchesNumber(rowViews(row), filters.views)) return false
  if (filters.title && !rowTitle(row).toLowerCase().includes(filters.title.trim().toLowerCase())) {
    return false
  }
  return matchesNumber(rowClicks(row), filters.clicks)
}

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
  const [sortKey, setSortKey] = useState<SortKey>("date")
  const [sortDir, setSortDir] = useState<SortDir>("desc")
  const [filters, setFilters] = useState<ColumnFilters>(EMPTY_FILTERS)
  const location = useLocation()
  const navigate = useNavigate()

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

  const platforms = useMemo(
    () => Array.from(new Set(correlation.map((row) => row.platform))).sort(),
    [correlation],
  )

  const visibleRows = useMemo(() => {
    const rows = correlation.filter((row) => rowMatchesFilters(row, filters))
    const dir = sortDir === "asc" ? 1 : -1
    rows.sort((a, b) => {
      const primary = compareRows(a, b, sortKey)
      if (primary !== 0) return primary * dir
      const byDate = b.date.localeCompare(a.date)
      if (byDate !== 0) return byDate
      return a.platform.localeCompare(b.platform)
    })
    return rows
  }, [correlation, filters, sortDir, sortKey])

  const clickSpans = useMemo(() => clickRowSpans(visibleRows), [visibleRows])
  const filtersActive = Object.values(filters).some((value) => value.trim() !== "")

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"))
      return
    }
    setSortKey(key)
    setSortDir(key === "platform" || key === "title" ? "asc" : "desc")
  }

  function setFilter<K extends keyof ColumnFilters>(key: K, value: ColumnFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }))
  }

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

  const openVideo = useCallback(async (platform: string, videoId: string) => {
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
  }, [])

  useEffect(() => {
    const payload = (location.state as { openVideo?: { platform: string; videoId: string } } | null)
      ?.openVideo
    if (!payload?.platform || !payload.videoId) return
    void openVideo(payload.platform, payload.videoId)
    navigate(".", { replace: true, state: {} })
  }, [location.state, navigate, openVideo])

  return (
    <div className="mx-auto max-w-7xl p-6">
      <AppHeader
        title="Content Analytics"
        subtitle={`YouTube · TikTok · Instagram · VK · Dzen · Яндекс.Метрика · ${statusLine}`}
        days={days}
        onDaysChange={setDays}
        onRefresh={handleRefresh}
        refreshing={refreshing}
        onOpenVideo={(platform, videoId) => {
          void openVideo(platform, videoId)
        }}
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
          <div className="flex items-start justify-between gap-3">
            <CardTitle>Площадка по дням</CardTitle>
            {filtersActive ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setFilters(EMPTY_FILTERS)}
              >
                Сбросить фильтры
              </Button>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            YouTube / TikTok / Instagram / Дзен: колонка «Клики» общая на всю неделю (ссылка в bio), даже если роликов несколько.
            В Дзене ссылки в комментариях некликабельны, поэтому учитываем как у YouTube.
            VK: клики за этот день. Цифра по ролику — откройте строку.
            Сортировка по умолчанию — дата по убыванию. Показано {visibleRows.length} из {correlation.length}.
          </p>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-[480px] rounded-md border">
            <Table containerClassName="overflow-visible">
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  {SORT_COLUMNS.map((column) => (
                    <TableHead
                      key={column.key}
                      aria-sort={
                        sortKey === column.key
                          ? sortDir === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      className="sticky top-0 z-20 h-auto bg-card px-2 py-2 align-top"
                    >
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 text-left hover:text-foreground"
                        onClick={() => toggleSort(column.key)}
                      >
                        {column.label}
                        {sortKey === column.key ? (
                          sortDir === "asc" ? (
                            <ArrowUp className="size-3.5" />
                          ) : (
                            <ArrowDown className="size-3.5" />
                          )
                        ) : (
                          <ArrowUpDown className="size-3.5 opacity-40" />
                        )}
                      </button>
                      {column.key === "platform" ? (
                        <Select
                          value={filters.platform || "all"}
                          onValueChange={(value) => setFilter("platform", value === "all" ? "" : value)}
                        >
                          <SelectTrigger className="mt-1.5 h-8 px-2 text-xs">
                            <SelectValue placeholder="Все" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">Все</SelectItem>
                            {platforms.map((platform) => (
                              <SelectItem key={platform} value={platform}>
                                {platform}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      ) : (
                        <Input
                          value={filters[column.key]}
                          onChange={(event) => setFilter(column.key, event.target.value)}
                          placeholder={
                            column.key === "date"
                              ? "2026-09"
                              : column.key === "title"
                                ? "текст"
                                : "число"
                          }
                          className="mt-1.5 h-8 px-2 text-xs"
                          aria-label={`Фильтр: ${column.label}`}
                        />
                      )}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {visibleRows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                      {correlation.length === 0
                        ? "Нет данных за выбранный период"
                        : "Нет строк по текущим фильтрам"}
                    </TableCell>
                  </TableRow>
                ) : null}
                {visibleRows.map((row, index) => (
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
                    <TableCell>
                      {fmt(row.platform === "vk" ? row.total_views : (row.top_video_views ?? row.total_views))}
                    </TableCell>
                    <TableCell>
                      {row.platform === "vk" ? "—" : row.top_video_title || "—"}
                    </TableCell>
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
