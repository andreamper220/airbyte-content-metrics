export function fmt(n: number | null | undefined): string {
  const value = n ?? 0
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

export type CommentPart = { type: "text"; value: string } | { type: "link"; href: string; label: string }

function decodeEntities(raw: string): string {
  return raw
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
}

function stripTags(raw: string): string {
  return decodeEntities(raw.replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]+>/g, ""))
}

export function stripHtml(raw: string | null | undefined): string {
  return stripTags(raw || "").trim()
}

function safeHref(href: string): string | null {
  const trimmed = href.trim()
  if (!trimmed) return null
  try {
    const url = new URL(trimmed.startsWith("http://") || trimmed.startsWith("https://") ? trimmed : `https://${trimmed}`)
    if (url.protocol === "http:" || url.protocol === "https:") return url.href
  } catch {
    return null
  }
  return null
}

export function commentParts(raw: string | null | undefined): CommentPart[] {
  const source = (raw || "").replace(/<br\s*\/?>/gi, "\n")
  const stored: Array<{ href: string; label: string }> = []
  const marked = source.replace(/<a\s+[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi, (_match, href, inner) => {
    const safe = safeHref(String(href))
    const label = stripTags(String(inner)) || String(href)
    if (!safe) return label
    stored.push({ href: safe, label })
    return `\u0001${stored.length - 1}\u0001`
  })
  const text = stripTags(marked)
  const parts: CommentPart[] = []
  const tokenRe = /\u0001(\d+)\u0001|https?:\/\/[^\s<>"'()]+/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = tokenRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) })
    }
    if (match[1] != null) {
      const item = stored[Number(match[1])]
      if (item) parts.push({ type: "link", href: item.href, label: item.label })
    } else {
      const rawUrl = match[0].replace(/[),.;]+$/g, "")
      const href = safeHref(rawUrl)
      if (href) parts.push({ type: "link", href, label: rawUrl })
      else parts.push({ type: "text", value: match[0] })
    }
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) })
  }
  return parts.length ? parts : [{ type: "text", value: "" }]
}

export function platformColor(platform: string): string {
  switch (platform) {
    case "youtube":
      return "#ff4444"
    case "tiktok":
      return "#69c9d0"
    case "instagram":
      return "#e1306c"
    case "vk":
      return "#0077ff"
    case "dzen":
      return "#ffaa00"
    default:
      return "#7c5cff"
  }
}
