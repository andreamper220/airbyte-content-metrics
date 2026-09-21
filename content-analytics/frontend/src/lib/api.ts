export type SummaryRow = {
  platform: string
  views: number
  videos: number
  likes: number
  unique_clicks?: number
}

export type TrendRow = {
  date: string
  platform: string
  views: number
  likes: number
  web_sessions: number
}

export type CorrelationRow = {
  date: string
  platform: string
  total_views: number
  top_video_id?: string | null
  top_video_title?: string | null
  top_video_views?: number
  week_start?: string
  week_end?: string
  clicks_scope?: "week" | "day"
  unique_clicks?: number
  web_sessions?: number
}

export type ViralRow = {
  platform: string
  video_id: string
  title?: string | null
  views: number
  likes: number
  publish_day_sessions: number
  unique_clicks?: number
  clicks_scope?: "video" | "week"
}

export type VideoComment = {
  comment_id?: string
  author: string
  text: string
  likes: number
  reply_to?: string
  from_account?: boolean
}

export type CommentingStatus = {
  enabled: boolean
  as?: string | null
  max_length: number
  supported?: boolean
}

export type RecentComment = {
  platform: string
  video_id: string
  comment_id: string
  author: string
  text: string
  likes: number
  published_at: string | null
  video_title?: string | null
}

export type RecentCommentsResponse = {
  comments: RecentComment[]
}

export type VideoEmbed =
  | { type: "iframe"; src: string; aspect?: "16/9" | "9/16" }
  | { type: "hls"; src: string; poster?: string; url?: string }
  | { type: "instagram"; url: string }
  | { type: "link"; url?: string; image?: string }
  | { type: "fallback"; url?: string }

export type VideoClicks = {
  mode: "weekly_bio" | "per_video"
  utm_content: string
  week_start: string
  week_end: string
  unique_clicks: number
  sessions: number
  amount_rub: number | null
}

export type VideoDetailResponse = {
  video: {
    platform: string
    video_id: string
    title?: string | null
    url?: string | null
    views: number
    likes: number
    comment_count: number
  }
  description: string
  embed: VideoEmbed
  comments: VideoComment[]
  commenting?: CommentingStatus
  clicks?: VideoClicks
}

export type RefreshStatus = {
  in_progress: boolean
  last_refresh_at: string | null
  last_refresh_ok: boolean | null
  last_error: string | null
  last_airbyte_sync_at: string | null
  last_airbyte_sync_ok: boolean | null
  last_airbyte_error: string | null
  auto_refresh_enabled: boolean
  mart_refresh_interval_minutes: number
  airbyte_sync_enabled: boolean
  airbyte_sync_interval_minutes: number
}

export type UtmMappingRow = {
  platform: string
  utm_source: string
}

export type UtmMappingResponse = {
  mappings: UtmMappingRow[]
  platforms: string[]
}

export type AuthMeResponse = {
  email: string | null
  auth_enabled: boolean
}

export type MetrikaStatus = {
  raw_sessions: number
  utm_sessions: number
  utm_sessions_period: number
  last_extracted_at: string | null
  error?: string
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { credentials: "include", ...init })
  if (res.status === 401) {
    if (!url.startsWith("/auth/me")) {
      window.location.href = "/login"
    }
    throw new Error("Unauthorized")
  }
  if (!res.ok) {
    const body = await res.text()
    throw new Error(apiErrorMessage(body))
  }
  return res.json() as Promise<T>
}

function apiErrorMessage(body: string): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown }
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail
    if (Array.isArray(parsed.detail)) {
      const parts = parsed.detail.map((item) => {
        if (item && typeof item === "object" && "msg" in item) return String(item.msg)
        return String(item)
      })
      if (parts.length) return parts.join("; ")
    }
  } catch {
    /* not JSON */
  }
  return body || "Request failed"
}

export const api = {
  me: () => fetchJson<AuthMeResponse>("/auth/me"),
  logout: () => fetchJson<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  summary: (days: number) => fetchJson<SummaryRow[]>(`/api/summary?days=${days}`),
  trend: (days: number) => fetchJson<TrendRow[]>(`/api/trend?days=${days}`),
  correlation: (days: number) => fetchJson<CorrelationRow[]>(`/api/correlation?days=${days}`),
  viral: (days: number) => fetchJson<ViralRow[]>(`/api/viral?days=${days}`),
  video: (platform: string, videoId: string) =>
    fetchJson<VideoDetailResponse>(
      `/api/video/${encodeURIComponent(platform)}/${encodeURIComponent(videoId)}`,
    ),
  postComment: (platform: string, videoId: string, text: string, replyTo?: string) =>
    fetchJson<{ comment: VideoComment }>(
      `/api/video/${encodeURIComponent(platform)}/${encodeURIComponent(videoId)}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, reply_to: replyTo || "" }),
      },
    ),
  commentingStatus: () =>
    fetchJson<{ platforms: Record<string, CommentingStatus> }>("/api/settings/commenting"),
  recentComments: (days = 30, limit = 50) =>
    fetchJson<RecentCommentsResponse>(`/api/comments/recent?days=${days}&limit=${limit}`),
  refresh: () => fetchJson<RefreshStatus>("/api/refresh", { method: "POST" }),
  refreshStatus: () => fetchJson<RefreshStatus>("/api/refresh/status"),
  getUtmMap: () => fetchJson<UtmMappingResponse>("/api/settings/utm-map"),
  saveUtmMap: (mappings: UtmMappingRow[]) =>
    fetchJson<{ mappings: UtmMappingRow[] }>("/api/settings/utm-map", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    }),
  metrikaStatus: (days: number) => fetchJson<MetrikaStatus>(`/api/web/metrika-status?days=${days}`),
}
