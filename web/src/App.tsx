import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { TaskListPage } from './pages/TaskListPage'
import { TaskDetailPage } from './pages/TaskDetailPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-background text-foreground bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-background to-background">
        <main>
          <Routes>
            <Route path="/" element={<TaskListPage />} />
            <Route path="/task/:taskId" element={<TaskDetailPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
