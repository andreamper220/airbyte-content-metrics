import { Navigate } from "react-router-dom"
import type { ReactNode } from "react"

import { useAuth } from "@/lib/auth-context"

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { authEnabled, email, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Загрузка…
      </div>
    )
  }

  if (authEnabled && !email) {
    return <Navigate to="/login" replace />
  }

  return children
}
