import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { formatDistanceToNow } from "date-fns"
import { ru } from "date-fns/locale"
import { Bell } from "lucide-react"

import { api, type RecentComment } from "@/lib/api"
import { platformColor } from "@/lib/format"
import { Button } from "@/components/ui/button"

const LAST_SEEN_KEY = "content-analytics:comments:last-seen"
const POLL_MS = 60_000
const FIRST_VISIT_UNREAD_MS = 24 * 60 * 60 * 1000

type CommentBellProps = {
  onOpenVideo?: (platform: string, videoId: string) => void
}

function loadLastSeen(): string | null {
  try {
    return localStorage.getItem(LAST_SEEN_KEY)
  } catch {
    return null
  }
}

function saveLastSeen(value: string) {
  try {
    localStorage.setItem(LAST_SEEN_KEY, value)
  } catch {
    /* ignore quota / private mode */
  }
}

function commentTime(comment: RecentComment): number {
  if (!comment.published_at) return 0
  const ms = new Date(comment.published_at).getTime()
  return Number.isNaN(ms) ? 0 : ms
}

function isUnread(comment: RecentComment, lastSeen: string | null): boolean {
  const ts = commentTime(comment)
  if (!ts) return false
  if (lastSeen) {
    const seen = new Date(lastSeen).getTime()
    return !Number.isNaN(seen) && ts > seen
  }
  return Date.now() - ts < FIRST_VISIT_UNREAD_MS
}

function previewText(raw: string): string {
  return raw
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ")
    .trim()
}

function relativeTime(iso: string | null): string {
  if (!iso) return ""
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  return formatDistanceToNow(date, { addSuffix: true, locale: ru })
}

function notifyBrowser(newcomers: RecentComment[]) {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return
  if (document.visibilityState === "visible") return
  const first = newcomers[0]
  const title =
    newcomers.length === 1
      ? `Новый комментарий · ${first.platform}`
      : `${newcomers.length} новых комментариев`
  const body =
    newcomers.length === 1
      ? `${first.author}: ${previewText(first.text)}`
      : newcomers.map((item) => item.author).filter(Boolean).join(", ")
  try {
    new Notification(title, { body, silent: false })
  } catch {
    /* browser may still block */
  }
}

export function CommentBell({ onOpenVideo }: CommentBellProps) {
  const navigate = useNavigate()
  const rootRef = useRef<HTMLDivElement>(null)
  const knownIdsRef = useRef<Set<string>>(new Set())
  const initializedRef = useRef(false)
  const [open, setOpen] = useState(false)
  const [comments, setComments] = useState<RecentComment[]>([])
  const [lastSeen, setLastSeen] = useState<string | null>(() => loadLastSeen())
  const [highlighted, setHighlighted] = useState<Set<string>>(new Set())
  const [browserPermission, setBrowserPermission] = useState<NotificationPermission | "unsupported">(
    () => (typeof Notification === "undefined" ? "unsupported" : Notification.permission),
  )

  const unread = useMemo(
    () => comments.filter((comment) => isUnread(comment, lastSeen)),
    [comments, lastSeen],
  )
  const unreadCount = unread.length

  const loadComments = useCallback(async () => {
    try {
      const data = await api.recentComments()
      const next = data.comments
      if (initializedRef.current) {
        const lastSeenNow = loadLastSeen()
        const newcomers = next.filter(
          (comment) => !knownIdsRef.current.has(comment.comment_id) && isUnread(comment, lastSeenNow),
        )
        if (newcomers.length) notifyBrowser(newcomers)
      }
      initializedRef.current = true
      knownIdsRef.current = new Set(next.map((comment) => comment.comment_id))
      setComments(next)
    } catch {
      /* keep previous list */
    }
  }, [])

  useEffect(() => {
    void loadComments()
    const timer = window.setInterval(() => {
      void loadComments()
    }, POLL_MS)
    const onFocus = () => {
      void loadComments()
    }
    window.addEventListener("focus", onFocus)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener("focus", onFocus)
    }
  }, [loadComments])

  useEffect(() => {
    if (!open) return
    function onDocClick(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onDocClick)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onDocClick)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  function markAllRead() {
    const newest = comments.reduce((acc, comment) => Math.max(acc, commentTime(comment)), 0)
    const value = new Date(Math.max(Date.now(), newest)).toISOString()
    saveLastSeen(value)
    setLastSeen(value)
  }

  function toggleOpen() {
    const next = !open
    setOpen(next)
    if (next) {
      setHighlighted(new Set(unread.map((comment) => comment.comment_id)))
      markAllRead()
    }
  }

  function openVideo(platform: string, videoId: string) {
    if (!platform || !videoId) return
    setOpen(false)
    if (onOpenVideo) {
      onOpenVideo(platform, videoId)
      return
    }
    navigate("/", { state: { openVideo: { platform, videoId } } })
  }

  async function enableBrowserNotifications() {
    if (typeof Notification === "undefined") return
    const permission = await Notification.requestPermission()
    setBrowserPermission(permission)
  }

  const badgeLabel = unreadCount > 99 ? "99+" : String(unreadCount)

  return (
    <div className="relative z-50" ref={rootRef}>
      <Button
        type="button"
        variant="outline"
        size="icon"
        aria-label={unreadCount ? `Комментарии, непрочитанных: ${unreadCount}` : "Комментарии"}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={toggleOpen}
        className="relative"
      >
        <Bell />
        {unreadCount > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-none text-primary-foreground">
            {badgeLabel}
          </span>
        ) : null}
      </Button>
      {open ? (
        <div
          role="dialog"
          aria-label="Новые комментарии"
          className="absolute right-0 z-50 mt-2 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-lg"
        >
          <div className="flex items-center justify-between border-b px-3 py-2">
            <p className="text-sm font-medium">Комментарии</p>
            <p className="text-xs text-muted-foreground">
              {highlighted.size ? `${highlighted.size} новых` : "за 30 дней"}
            </p>
          </div>
          {!comments.length ? (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              Пока нет новых комментариев
            </p>
          ) : (
            <ul className="max-h-[min(28rem,70vh)] overflow-y-auto">
              {comments.map((comment) => {
                const unreadRow = highlighted.has(comment.comment_id)
                const title = comment.video_title?.trim() || comment.video_id
                return (
                  <li
                    key={`${comment.platform}:${comment.video_id}:${comment.comment_id}`}
                    className="border-b last:border-b-0"
                  >
                    <button
                      type="button"
                      className={`w-full px-3 py-3 text-left transition-colors hover:bg-accent ${unreadRow ? "bg-accent/40" : ""}`}
                      onClick={() => openVideo(comment.platform, comment.video_id)}
                    >
                      <div className="mb-1 flex items-center gap-2 text-xs">
                        <span
                          className="font-medium uppercase tracking-wide"
                          style={{ color: platformColor(comment.platform) }}
                        >
                          {comment.platform}
                        </span>
                        <span className="truncate text-muted-foreground">{title}</span>
                        <span className="ml-auto shrink-0 text-muted-foreground">
                          {relativeTime(comment.published_at)}
                        </span>
                      </div>
                      <div className="text-sm font-medium">{comment.author || "Без имени"}</div>
                      <div className="line-clamp-2 text-sm text-muted-foreground">
                        {previewText(comment.text) || "—"}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
          {browserPermission === "default" ? (
            <div className="border-t px-3 py-2">
              <button
                type="button"
                className="text-xs text-primary underline-offset-4 hover:underline"
                onClick={() => void enableBrowserNotifications()}
              >
                Включить уведомления браузера
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
