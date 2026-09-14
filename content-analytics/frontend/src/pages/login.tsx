import { useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuth } from "@/lib/auth-context"

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Доступ разрешён только для авторизованных аккаунтов.",
  oauth_failed: "Не удалось войти через Google. Попробуйте ещё раз.",
}

export function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { authEnabled, email, loading } = useAuth()

  const errorKey = searchParams.get("error")
  const errorMessage = errorKey ? ERROR_MESSAGES[errorKey] : null

  useEffect(() => {
    if (loading) return
    if (!authEnabled || email) {
      navigate("/", { replace: true })
    }
  }, [authEnabled, email, loading, navigate])

  if (loading || !authEnabled || email) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Загрузка…
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Content Analytics</CardTitle>
          <CardDescription>Войдите через Google, чтобы открыть дашборд.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {errorMessage ? (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {errorMessage}
            </p>
          ) : null}
          <Button asChild className="w-full">
            <a href="/auth/login">Войти через Google</a>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
