import { useEffect, useRef } from "react"

import type { VideoDetailResponse, VideoEmbed } from "@/lib/api"
import { fmt } from "@/lib/format"
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

  if (embed.type === "iframe") {
    return (
      <iframe
        src={embed.src}
        className="aspect-video min-h-[400px] w-full border-0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
      />
    )
  }

  if ((embed.type === "link" || embed.type === "fallback") && (embed.url || url)) {
    const href = embed.url || url || ""
    return (
      <div className="flex min-h-[200px] items-center justify-center p-6 text-center text-muted-foreground">
        <p>
          Просмотр встроенного плеера недоступен.{" "}
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
            Открыть на платформе
          </a>
        </p>
      </div>
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

export function VideoDialog({ open, onOpenChange, data, error }: VideoDialogProps) {
  const video = data?.video

  async function copyUrl() {
    if (!video?.url) return
    await navigator.clipboard.writeText(video.url)
  }

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
                {data.clicks.mode === "per_video" ? (
                  <p className="mb-2 text-muted-foreground">
                    У VK и Дзен клики считаются по ссылке в описании именно этого ролика
                    {data.clicks.utm_content ? ` (${data.clicks.utm_content})` : ""}.
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-4">
                  <div>
                    <span className="text-muted-foreground">Уникальных: </span>
                    <strong>{fmt(data.clicks.unique_clicks)}</strong>
                  </div>
                  {data.clicks.mode === "weekly_bio" && data.clicks.week_start ? (
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
              <ScrollArea className="h-48 rounded-md border">
                <ul className="divide-y p-2">
                  {!data.comments.length ? (
                    <li className="p-2 text-sm text-muted-foreground">Нет комментариев</li>
                  ) : (
                    data.comments.map((comment, index) => (
                      <li key={`${comment.author}-${index}`} className="py-3 text-sm">
                        <div className="mb-1">
                          <span className="font-semibold">{comment.author}</span>
                          <span className="ml-2 text-xs text-muted-foreground">
                            ♥ {fmt(comment.likes)}
                          </span>
                        </div>
                        <div>{comment.text}</div>
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
  }
}
