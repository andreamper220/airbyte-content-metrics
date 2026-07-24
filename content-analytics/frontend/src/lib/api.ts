export type SummaryRow = {
  platform: string
  views: number
  videos: number
  likes: number
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
  web_sessions: number
  sessions_per_view?: number | null
}

export type ViralRow = {
  platform: string
  video_id: string
  title?: string | null
  views: number
  likes: number
  publish_day_sessions: number
}

export type VideoComment = {
  author: string
  text: string
  likes: number
}

export type VideoEmbed =
  | { type: "iframe"; src: string }
  | { type: "instagram"; url: string }
  | { type: "fallback" }

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
}

export type UtmMappingRow = {
  platform: string
  utm_source: string
}

export type UtmMappingResponse = {
  mappings: UtmMappingRow[]
  platforms: string[]
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    throw new Error(await res.text())
  }
  return res.json() as Promise<T>
}

export const api = {
  summary: (days: number) => fetchJson<SummaryRow[]>(`/api/summary?days=${days}`),
  trend: (days: number) => fetchJson<TrendRow[]>(`/api/trend?days=${days}`),
  correlation: (days: number) => fetchJson<CorrelationRow[]>(`/api/correlation?days=${days}`),
  viral: (days: number) => fetchJson<ViralRow[]>(`/api/viral?days=${days}`),
  video: (platform: string, videoId: string) =>
    fetchJson<VideoDetailResponse>(
      `/api/video/${encodeURIComponent(platform)}/${encodeURIComponent(videoId)}`,
    ),
  refresh: () => fetchJson<{ status: string }>("/api/refresh", { method: "POST" }),
  getUtmMap: () => fetchJson<UtmMappingResponse>("/api/settings/utm-map"),
  saveUtmMap: (mappings: UtmMappingRow[]) =>
    fetchJson<{ mappings: UtmMappingRow[] }>("/api/settings/utm-map", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mappings }),
    }),
}
