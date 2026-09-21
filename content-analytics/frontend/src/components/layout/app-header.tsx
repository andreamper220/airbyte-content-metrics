import { Link } from "react-router-dom"
import { LogOut, Settings2 } from "lucide-react"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { CommentBell } from "@/components/layout/comment-bell"
import { useAuth } from "@/lib/auth-context"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

type AppHeaderProps = {
  title: string
  subtitle?: string
  days?: string
  onDaysChange?: (days: string) => void
  onRefresh?: () => void
  refreshing?: boolean
  backHref?: string
  backLabel?: string
  actions?: ReactNode
  onOpenVideo?: (platform: string, videoId: string) => void
}

export function AppHeader({
  title,
  subtitle,
  days,
  onDaysChange,
  onRefresh,
  refreshing,
  backHref,
  backLabel,
  actions,
  onOpenVideo,
}: AppHeaderProps) {
  const { authEnabled, email, logout } = useAuth()

  return (
    <header className="relative z-20 mb-6 flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {backHref ? (
          <Button variant="ghost" asChild>
            <Link to={backHref}>{backLabel ?? "← Назад"}</Link>
          </Button>
        ) : (
          <Button variant="outline" size="sm" asChild>
            <Link to="/settings">
              <Settings2 />
              UTM
            </Link>
          </Button>
        )}
        {days !== undefined && onDaysChange ? (
          <Select value={days} onValueChange={onDaysChange}>
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">7 дней</SelectItem>
              <SelectItem value="30">30 дней</SelectItem>
              <SelectItem value="90">90 дней</SelectItem>
            </SelectContent>
          </Select>
        ) : null}
        {onRefresh ? (
          <Button onClick={onRefresh} disabled={refreshing}>
            {refreshing ? "Обновляю…" : "Обновить данные"}
          </Button>
        ) : null}
        {actions}
        <CommentBell onOpenVideo={onOpenVideo} />
        {authEnabled && email ? (
          <>
            <span className="hidden text-sm text-muted-foreground sm:inline">{email}</span>
            <Button variant="outline" size="sm" onClick={() => void logout()}>
              <LogOut />
              Выйти
            </Button>
          </>
        ) : null}
      </div>
    </header>
  )
}
