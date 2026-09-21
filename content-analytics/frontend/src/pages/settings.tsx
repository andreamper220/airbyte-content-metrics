import { useEffect, useState } from "react"
import { Plus, Trash2 } from "lucide-react"

import { api, type CommentingStatus, type UtmMappingRow } from "@/lib/api"
import { AppHeader } from "@/components/layout/app-header"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function SettingsPage() {
  const [platforms, setPlatforms] = useState<string[]>([])
  const [rows, setRows] = useState<UtmMappingRow[]>([])
  const [status, setStatus] = useState<{ type: "ok" | "err" | "idle"; text: string }>({
    type: "idle",
    text: "",
  })
  const [saving, setSaving] = useState(false)
  const [commenting, setCommenting] = useState<Record<string, CommentingStatus>>({})

  useEffect(() => {
    void api.getUtmMap().then((data) => {
      setPlatforms(data.platforms)
      setRows(data.mappings)
    })
    void api.commentingStatus().then((data) => setCommenting(data.platforms)).catch(() => undefined)
  }, [])

  function updateRow(index: number, field: keyof UtmMappingRow, value: string) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    )
  }

  function addRow() {
    setRows((prev) => [...prev, { platform: platforms[0] ?? "youtube", utm_source: "" }])
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  async function save() {
    setSaving(true)
    setStatus({ type: "idle", text: "Сохраняю…" })
    try {
      const data = await api.saveUtmMap(rows)
      setRows(data.mappings)
      setStatus({ type: "ok", text: "Сохранено. Обновите дашборд для применения." })
    } catch (error) {
      setStatus({
        type: "err",
        text: `Ошибка: ${error instanceof Error ? error.message : "неизвестная"}`,
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <AppHeader
        title="Настройки"
        backHref="/"
        backLabel="← Дашборд"
      />

      <Card>
        <CardHeader>
          <CardTitle>Комментарии от аккаунта</CardTitle>
          <CardDescription>
            YouTube, VK и Дзен: ответы из карточки ролика публикуются от имени канала. Токены
            задаются в <code className="rounded bg-muted px-1">.env</code>, после изменения нужен
            перезапуск приложения.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-sm">
            {["youtube", "vk", "dzen"].map((platform) => {
              const item = commenting[platform]
              return (
                <li key={platform} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
                  <span className="font-medium uppercase tracking-wide">{platform}</span>
                  <span className={item?.enabled ? "text-emerald-400" : "text-muted-foreground"}>
                    {item?.enabled ? `включено · ${item.as || "аккаунт"}` : "токены не заданы"}
                  </span>
                </li>
              )
            })}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Настройки UTM</CardTitle>
          <CardDescription>
            Связь платформы с <code className="rounded bg-muted px-1">utm_source</code> в
            Яндекс.Метрике. Одна платформа может иметь несколько значений (например,{" "}
            <code className="rounded bg-muted px-1">tiktok</code> и{" "}
            <code className="rounded bg-muted px-1">tt</code>).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Платформа</TableHead>
                <TableHead>utm_source</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row, index) => (
                <TableRow key={`${row.platform}-${index}`}>
                  <TableCell>
                    <Select
                      value={row.platform}
                      onValueChange={(value) => updateRow(index, "platform", value)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {platforms.map((platform) => (
                          <SelectItem key={platform} value={platform}>
                            {platform}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Input
                      value={row.utm_source}
                      placeholder="youtube"
                      onChange={(event) =>
                        updateRow(index, "utm_source", event.target.value)
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Button
                      variant="destructive"
                      size="icon"
                      onClick={() => removeRow(index)}
                      aria-label="Удалить строку"
                    >
                      <Trash2 />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={addRow}>
              <Plus />
              Добавить
            </Button>
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? "Сохраняю…" : "Сохранить"}
            </Button>
          </div>

          {status.text ? (
            <p
              className={
                status.type === "ok"
                  ? "text-sm text-emerald-400"
                  : status.type === "err"
                    ? "text-sm text-destructive"
                    : "text-sm text-muted-foreground"
              }
            >
              {status.text}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
