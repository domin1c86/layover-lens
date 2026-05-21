import HomePage from './pages/HomePage'
import { ThemeProvider } from './context/ThemeContext'

function App() {
  return (
    <ThemeProvider>
      <div className="app">
        <HomePage />
      </div>
    </ThemeProvider>
  )
}

export default App
