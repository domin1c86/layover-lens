import { useState } from 'react'
import HomePage from './pages/HomePage'
import { ThemeProvider } from './context/ThemeContext'
import { LocaleProvider } from './context/LocaleContext'
import SettingsModal from './components/SettingsModal'

function App() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  return (
    <LocaleProvider>
      <ThemeProvider>
        <div className="app">
          <HomePage onOpenSettings={() => setIsSettingsOpen(true)} />
          <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
        </div>
      </ThemeProvider>
    </LocaleProvider>
  )
}

export default App
