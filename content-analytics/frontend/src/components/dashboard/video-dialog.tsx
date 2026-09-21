import { useEffect, useRef, useState } from "react"

import { api, type VideoComment, type VideoDetailResponse, type VideoEmbed } from "@/lib/api"
import { fmt, commentParts } from "@/lib/format"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"

type VideoDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  data: VideoDetailResponse | null
  error?: string | null
}

function loadHls(): Promise<NonNullable<typeof window.Hls>> {
  if (window.Hls) return Promise.resolve(window.Hls)
  return new Promise((resolve, reject) => {
    const script = document.createElement("script")
    script.src = "https://cdn.jsdelivr.net/npm/hls.js@1.5.17/dist/hls.min.js"
    script.async = true
    script.onload = () => {
      if (window.Hls) resolve(window.Hls)
      else reject(new Error("hls.js failed to load"))
    }
    script.onerror = () => reject(new Error("hls.js failed to load"))
    document.body.appendChild(script)
  })
}

function HlsPlayer({ src, poster, url }: { src: string; poster?: string; url?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const el = videoRef.current
    if (!el) return
    let hls: { destroy: () => void } | null = null
    let cancelled = false

    if (el.canPlayType("application/vnd.apple.mpegurl")) {
      el.src = src
      return
    }

    void loadHls()
      .then((HlsCtor) => {
        if (cancelled || !HlsCtor.isSupported()) return
        const instance = new HlsCtor({ xhrSetup: (xhr) => { xhr.withCredentials = true } })
        instance.loadSource(src)
        instance.attachMedia(el)
        hls = instance
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
      hls?.destroy()
    }
  }, [src])

  return (
    <div className="mx-auto w-full max-w-[420px] space-y-2">
      <video
        ref={videoRef}
        className="aspect-[9/16] w-full bg-black"
        poster={poster}
        controls
        playsInline
      />
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="block text-center text-sm text-primary underline">
          Открыть в Дзене
        </a>
      ) : null}
    </div>
  )
}

function EmbedView({ embed, url }: { embed: VideoEmbed; url?: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (embed.type !== "instagram" || !containerRef.current) return
    const script = document.createElement("script")
    script.src = "https://www.instagram.com/embed.js"
    script.async = true
    document.body.appendChild(script)
    script.onload = () => {
      window.instgrm?.Embeds.process()
    }
    return () => {
      script.remove()
    }
  }, [embed])

  if (embed.type === "hls") {
    return <HlsPlayer src={embed.src} poster={embed.poster} url={embed.url || url || undefined} />
  }

  if (embed.type === "iframe") {
    const aspectClass =
      embed.aspect === "9/16"
        ? "mx-auto aspect-[9/16] max-h-[min(70vh,720px)] w-full max-w-[420px] border-0"
        : "aspect-video min-h-[400px] w-full border-0"
    return (
      <iframe
        src={embed.src}
        className={aspectClass}
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    )
  }

  if ((embed.type === "link" || embed.type === "fallback") && (embed.url || url)) {
    const href = embed.url || url || ""
    const image = "image" in embed ? embed.image : undefined
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="relative mx-auto flex min-h-[360px] w-full max-w-[420px] aspect-[9/16] items-center justify-center overflow-hidden bg-zinc-950 text-white"
      >
        {image ? (
          <img src={image} alt="" className="absolute inset-0 h-full w-full object-cover opacity-70" />
        ) : null}
        <span className="relative z-10 rounded-full bg-white px-5 py-3 text-sm font-medium text-black">
          {href.includes("dzen.ru") ? "Смотреть в Дзене" : "Открыть на платформе"}
        </span>
      </a>
    )
  }

  if (embed.type === "instagram" && embed.url) {
    return (
      <div ref={containerRef} className="flex justify-center">
        <blockquote
          className="instagram-media mx-auto w-full max-w-[540px]"
          data-instgrm-permalink={embed.url}
          data-instgrm-version="14"
        />
      </div>
    )
  }

  return (
    <div className="flex min-h-[200px] items-center justify-center p-6 text-center text-muted-foreground">
      {url ? (
        <p>
          Просмотр встроенного плеера недоступен.{" "}
          <a href={url} target="_blank" rel="noopener noreferrer" className="text-primary underline">
            Открыть на платформе
          </a>
        </p>
      ) : (
        <p>Ссылка на ролик недоступна</p>
      )}
    </div>
  )
}

function CommentText({ text }: { text: string }) {
  const parts = commentParts(text)
  return (
    <div className="whitespace-pre-wrap break-words">
      {parts.map((part, index) =>
        part.type === "link" ? (
          <a
            key={`${part.href}-${index}`}
            href={part.href}
            target="_blank"
            rel="noopener noreferrer"
            className="break-all text-primary underline underline-offset-2"
          >
            {part.label}
          </a>
        ) : (
          <span key={index}>{part.value}</span>
        ),
      )}
    </div>
  )
}

export function VideoDialog({ open, onOpenChange, data, error }: VideoDialogProps) {
  const video = data?.video
  const commenting = data?.commenting
  const [comments, setComments] = useState<VideoComment[]>([])
  const [text, setText] = useState("")
  const [replyTo, setReplyTo] = useState<{ id: string; author: string } | null>(null)
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  useEffect(() => {
    setComments(data?.comments ?? [])
    setText("")
    setReplyTo(null)
    setSendError(null)
  }, [data])

  async function copyUrl() {
    if (!video?.url) return
    await navigator.clipboard.writeText(video.url)
  }

  async function submitComment() {
    if (!video?.platform || !video.video_id || sending) return
    const body = text.trim()
    if (!body) return
    setSending(true)
    setSendError(null)
    try {
      const result = await api.postComment(video.platform, video.video_id, body, replyTo?.id)
      setComments((prev) => [result.comment, ...prev])
      setText("")
      setReplyTo(null)
    } catch (err) {
      setSendError(err instanceof Error ? err.message : "Не удалось отправить комментарий")
    } finally {
      setSending(false)
    }
  }

  const maxLength = commenting?.max_length || 10000
  const canReply = Boolean(commenting?.supported)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{video?.title || "Ролик"}</DialogTitle>
          <DialogDescription>{data?.description || "—"}</DialogDescription>
        </DialogHeader>

        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : null}

        {!data && !error ? (
          <p className="text-sm text-muted-foreground">Загрузка ролика…</p>
        ) : null}

        {data ? (
          <div className="space-y-4">
            <div className="overflow-hidden rounded-lg bg-black">
              <EmbedView embed={data.embed} url={video?.url} />
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Input readOnly value={video?.url || ""} className="flex-1" />
              <Button variant="outline" onClick={copyUrl}>
                Копировать ссылку
              </Button>
            </div>

            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Просмотры: </span>
                <strong>{fmt(video?.views)}</strong>
              </div>
              <div>
                <span className="text-muted-foreground">Лайки: </span>
                <strong>{fmt(video?.likes)}</strong>
              </div>
              <div>
                <span className="text-muted-foreground">Комментариев: </span>
                <strong>{fmt(video?.comment_count)}</strong>
              </div>
            </div>

            {data.clicks ? (
              <div className="rounded-md border bg-muted/40 p-3 text-sm">
                <h3 className="mb-1 font-medium">Клики на сайт</h3>
                <div className="flex flex-wrap gap-4">
                  <div>
                    <span className="text-muted-foreground">Уникальных: </span>
                    <strong>{fmt(data.clicks.unique_clicks)}</strong>
                  </div>
                  {data.clicks.mode === "weekly_bio" && data.clicks.week_start && !data.clicks.week_start.startsWith("1970") ? (
                    <div>
                      <span className="text-muted-foreground">Неделя: </span>
                      <strong>
                        {data.clicks.week_start} — {data.clicks.week_end}
                      </strong>
                    </div>
                  ) : null}
                  {data.clicks.utm_content ? (
                    <div>
                      <span className="text-muted-foreground">utm_content: </span>
                      <strong>{data.clicks.utm_content}</strong>
                    </div>
                  ) : null}
                  {data.clicks.amount_rub != null ? (
                    <div>
                      <span className="text-muted-foreground">К оплате: </span>
                      <strong>{fmt(data.clicks.amount_rub)} ₽</strong>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}

            <div>
              <h3 className="mb-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                Комментарии (по популярности)
              </h3>
              {canReply ? (
                <form
                  className="mb-3 space-y-2"
                  onSubmit={(event) => {
                    event.preventDefault()
                    void submitComment()
                  }}
                >
                  {replyTo ? (
                    <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/40 px-3 py-2 text-xs">
                      <span>
                        Ответ для <strong>{replyTo.author}</strong>
                      </span>
                      <Button type="button" variant="ghost" size="sm" onClick={() => setReplyTo(null)}>
                        Отмена
                      </Button>
                    </div>
                  ) : null}
                  <textarea
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    maxLength={maxLength}
                    disabled={!commenting?.enabled || sending}
                    placeholder={
                      commenting?.enabled
                        ? `Комментарий от имени ${commenting.as || "аккаунта"}`
                        : "Не настроены токены аккаунта для этой площадки"
                    }
                    onKeyDown={(event) => {
                      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                        event.preventDefault()
                        void submitComment()
                      }
                    }}
                    className="min-h-[88px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-muted-foreground">
                      {commenting?.enabled
                        ? `От имени ${commenting.as || "аккаунта"} · Ctrl+Enter`
                        : "Добавьте токены YouTube / VK / Дзена в .env и перезапустите приложение"}
                    </p>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {text.length}/{maxLength}
                      </span>
                      <Button type="submit" disabled={!commenting?.enabled || sending || !text.trim()}>
                        {sending ? "Отправляю…" : replyTo ? "Ответить" : "Отправить"}
                      </Button>
                    </div>
                  </div>
                  {sendError ? <p className="text-sm text-destructive">{sendError}</p> : null}
                </form>
              ) : null}
              <ScrollArea className="h-48 rounded-md border">
                <ul className="divide-y p-2">
                  {!comments.length ? (
                    <li className="p-2 text-sm text-muted-foreground">Нет комментариев</li>
                  ) : (
                    comments.map((comment, index) => (
                      <li key={comment.comment_id || `${comment.author}-${index}`} className="py-3 text-sm">
                        <div className="mb-1 flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{comment.author}</span>
                          {comment.from_account ? (
                            <span className="rounded bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-primary">
                              аккаунт
                            </span>
                          ) : null}
                          <span className="text-xs text-muted-foreground">♥ {fmt(comment.likes)}</span>
                          {canReply && commenting?.enabled && comment.comment_id ? (
                            <button
                              type="button"
                              className="ml-auto text-xs text-primary underline-offset-4 hover:underline"
                              onClick={() =>
                                setReplyTo({ id: comment.comment_id || "", author: comment.author })
                              }
                            >
                              Ответить
                            </button>
                          ) : null}
                        </div>
                        <CommentText text={comment.text} />
                      </li>
                    ))
                  )}
                </ul>
              </ScrollArea>
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

declare global {
  interface Window {
    instgrm?: { Embeds: { process: () => void } }
    Hls?: {
      isSupported: () => boolean
      new (config?: { xhrSetup?: (xhr: XMLHttpRequest) => void }): {
        loadSource: (src: string) => void
        attachMedia: (el: HTMLVideoElement) => void
        destroy: () => void
      }
    }
  }
}
