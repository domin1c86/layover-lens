import { useState, useCallback } from 'react'
import HomePage from './pages/HomePage'
import { ThemeProvider } from './context/ThemeContext'
import { LocaleProvider } from './context/LocaleContext'
import { AuthProvider } from './context/AuthContext'
import { FavoritesProvider } from './context/FavoritesContext'
import SettingsModal from './components/SettingsModal'
import LoginModal from './components/AuthModals/LoginModal'
import RegisterModal from './components/AuthModals/RegisterModal'
import ForgotPasswordFlowModal from './components/AuthModals/ForgotPasswordFlowModal'

type AuthModalType = 'login' | 'register' | 'forgotPassword' | null

function App() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [authModal, setAuthModal] = useState<AuthModalType>(null)
  const [prefillEmail, setPrefillEmail] = useState('')

  const openLogin = useCallback(() => setAuthModal('login'), [])
  const openRegister = useCallback(() => setAuthModal('register'), [])
  const openForgotPassword = useCallback(() => setAuthModal('forgotPassword'), [])
  const closeAuth = useCallback(() => {
    setAuthModal(null)
    setPrefillEmail('')
  }, [])

  const switchToRegister = useCallback(() => setAuthModal('register'), [])
  const switchToLogin = useCallback(() => setAuthModal('login'), [])

  const handleForgotPasswordSwitchToRegister = useCallback((email: string) => {
    setPrefillEmail(email)
    setAuthModal('register')
  }, [])

  const handleForgotPasswordSuccess = useCallback(() => {
    setAuthModal('login')
  }, [])

  return (
    <LocaleProvider>
      <ThemeProvider>
        <AuthProvider>
          <FavoritesProvider>
            <div className="app">
            <HomePage
              onOpenSettings={() => setIsSettingsOpen(true)}
              onOpenLogin={openLogin}
              onOpenRegister={openRegister}
            />
            <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
            <LoginModal
              isOpen={authModal === 'login'}
              onClose={closeAuth}
              onSwitchToRegister={switchToRegister}
              onOpenForgotPassword={openForgotPassword}
            />
            <RegisterModal
              isOpen={authModal === 'register'}
              onClose={closeAuth}
              onSwitchToLogin={switchToLogin}
              prefillEmail={prefillEmail}
            />
            <ForgotPasswordFlowModal
              isOpen={authModal === 'forgotPassword'}
              onClose={closeAuth}
              onSwitchToRegister={handleForgotPasswordSwitchToRegister}
              onSuccess={handleForgotPasswordSuccess}
            />
            </div>
          </FavoritesProvider>
        </AuthProvider>
      </ThemeProvider>
    </LocaleProvider>
  )
}

export default App
