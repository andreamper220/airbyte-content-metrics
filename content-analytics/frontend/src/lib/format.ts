export function fmt(n: number | null | undefined): string {
  const value = n ?? 0
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
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
