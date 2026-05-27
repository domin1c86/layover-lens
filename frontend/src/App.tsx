import HomePage from './pages/HomePage'
import { ThemeProvider } from './context/ThemeContext'
import { LocaleProvider } from './context/LocaleContext'

function App() {
  return (
    <LocaleProvider>
      <ThemeProvider>
        <div className="app">
          <HomePage />
        </div>
      </ThemeProvider>
    </LocaleProvider>
  )
}

export default App
