import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { DashboardPage } from "@/pages/dashboard"
import { SettingsPage } from "@/pages/settings"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
