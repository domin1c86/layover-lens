import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SecurityPanel from './SecurityPanel'

const authApiMock = vi.hoisted(() => ({
  sendEmailVerificationCode: vi.fn(),
  verifyEmailVerificationCode: vi.fn(),
  updateEmail: vi.fn(),
  verifyCurrentEmail: vi.fn(),
  checkPassword: vi.fn(),
  updatePassword: vi.fn(),
  setupTotp: vi.fn(),
  enableTotp: vi.fn(),
  disableTotp: vi.fn(),
  updateTotpEmailCodeReplacement: vi.fn(),
}))

const authState = vi.hoisted(() => ({
  user: {
    id: 'user_1',
    username: 'tester',
    email: 'old@example.com',
    email_verified: false,
    totp_enabled: false,
    totp_replaces_email_codes: false,
    created_at: '2026-01-01T00:00:00',
  },
  sessionDuration: 'day',
  setSessionDuration: vi.fn(),
  refreshUser: vi.fn(),
}))

const messages: Record<string, string> = {
  'auth.emailPlaceholder': 'Enter your email address',
  'settings.security.sessionDuration': 'Session duration',
  'settings.security.sessionHint': 'This applies immediately.',
  'settings.security.sessionUpdateFailed': 'Unable to update session duration.',
  'settings.security.sessionDurationDay': 'One day',
  'settings.security.sessionDurationWeek': 'One week',
  'settings.security.sessionDurationMonth': 'One month',
  'settings.security.sessionDurationHalfYear': 'Six months',
  'settings.security.sessionDurationYear': 'One year',
  'settings.security.sessionDurationForever': 'Forever',
  'settings.security.email': 'Email',
  'settings.security.emailReset': 'Reset Email',
  'settings.security.verifyEmail': 'Verify email',
  'settings.security.confirm': 'Confirm',
  'settings.security.currentVerifyTitle': 'Verify current email',
  'settings.security.currentVerifyDesc': 'Code sent to {{email}}.',
  'settings.security.changeEmailOldTitle': 'Confirm current email',
  'settings.security.changeEmailOldDesc': 'Enter current email first.',
  'settings.security.changeEmailCodeTitle': 'Verify new email',
  'settings.security.changeEmailCodeDesc': 'Code sent to {{email}}.',
  'settings.security.currentEmailPlaceholder': 'Current email',
  'settings.security.betaCode': 'Beta code: 000000',
  'settings.security.codePlaceholder': 'Enter verification code',
  'settings.security.resend': 'Resend',
  'settings.security.close': 'Close',
  'settings.security.oldEmailMismatch': 'Current email does not match.',
  'settings.security.newEmailInvalid': 'Enter a valid new email.',
  'settings.security.sendFailed': 'Unable to send code.',
  'settings.security.codeInvalid': 'Code invalid.',
  'settings.security.emailChanged': 'Email updated.',
  'settings.security.emailVerifiedDone': 'Email verified.',
  'settings.security.changePasswordTitle': 'Change Password',
  'settings.security.passwordCurrentPlaceholder': 'Current password',
  'settings.security.passwordNewPlaceholder': 'New password',
  'settings.security.passwordConfirmPlaceholder': 'Confirm new password',
  'settings.security.passwordCompositionHint': 'Use a combination of letters, numbers, and symbols.',
  'settings.security.hidePassword': 'Hide password',
  'settings.security.showPassword': 'Show password',
  'settings.security.passwordFailed': 'Unable to update password.',
  'settings.security.passwordSuccessTitle': 'Password updated successfully',
  'settings.security.passwordSuccessDesc': 'Use the new password next time.',
  'settings.security.statusEmailVerified': 'The current email has been verified.',
  'settings.security.statusEmailUnverified': 'The current email is not verified.',
  'settings.security.statusCurrentPasswordEmpty': 'Enter your current password.',
  'settings.security.statusCurrentPasswordChecking': 'Checking your current password.',
  'settings.security.statusCurrentPasswordValid': 'The current password is correct.',
  'settings.security.statusCurrentPasswordInvalid': 'The current password is incorrect.',
  'settings.security.statusNewPasswordEmpty': 'Enter a new password.',
  'settings.security.statusNewPasswordSame': 'The new password cannot be the same as the current password.',
  'settings.security.statusNewPasswordWeak': 'The new password is weak.',
  'settings.security.statusNewPasswordMedium': 'The new password is medium strength.',
  'settings.security.statusNewPasswordStrong': 'The new password is strong.',
  'settings.security.statusConfirmPasswordEmpty': 'Re-enter the new password.',
  'settings.security.statusConfirmPasswordValid': 'The confirmation password matches.',
  'settings.security.statusConfirmPasswordInvalid': 'The confirmation password does not match.',
  'settings.security.forgotPassword': 'Forgot password?',
  'settings.security.totpTitle': 'Authenticator two-factor authentication',
  'settings.security.totpEnabledStatus': 'TOTP enabled.',
  'settings.security.totpDisabledStatus': 'TOTP disabled.',
  'settings.security.totpEnabledDesc': 'Code required.',
  'settings.security.totpDisabledDesc': 'Enable a code.',
  'settings.security.totpEnable': 'Enable',
  'settings.security.totpDisable': 'Disable',
  'settings.security.totpSetupTitle': 'Enable authenticator',
  'settings.security.totpDisableTitle': 'Disable authenticator',
  'settings.security.totpPasswordDesc': 'Enter password.',
  'settings.security.totpSetupDesc': 'Add secret.',
  'settings.security.totpQrSetupDesc': 'Scan QR code.',
  'settings.security.totpQrCodeLabel': 'Authenticator setup QR code',
  'settings.security.totpUseSecret': 'Unable to scan? Try using the secret',
  'settings.security.totpUseQr': 'Not convenient? Try using the QR code',
  'settings.security.totpCopySecret': 'Copy secret',
  'settings.security.totpCodePlaceholder': 'Enter authenticator code',
  'settings.security.totpVerifyEnable': 'Verify and enable',
  'settings.security.totpDisableDesc': 'Enter password and code.',
  'settings.security.totpSetupFailed': 'Setup failed.',
  'settings.security.totpCodeInvalid': 'Invalid code.',
  'settings.security.totpDisableFailed': 'Disable failed.',
  'settings.security.totpReplacementTitle': 'Use 2FA instead of email codes',
  'settings.security.totpReplacementDesc': 'Use authenticator codes for recovery.',
  'settings.security.totpReplacementOwnershipNote': 'Email ownership still requires email codes.',
  'settings.security.totpReplacementFailed': 'Replacement update failed.',
}

vi.mock('../../../context/LocaleContext', () => ({
  useLocale: () => ({
    lang: 'en',
    t: (key: string, vars?: Record<string, string>) => {
      let value = messages[key] ?? key
      if (vars) {
        Object.entries(vars).forEach(([name, replacement]) => {
          value = value.replace(new RegExp(`{{${name}}}`, 'g'), replacement)
        })
      }
      return value
    },
  }),
}))

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authState,
}))

vi.mock('../../../services/api', () => ({
  authApi: authApiMock,
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

describe('SecurityPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.user = {
      id: 'user_1',
      username: 'tester',
      email: 'old@example.com',
      email_verified: false,
      totp_enabled: false,
      totp_replaces_email_codes: false,
      created_at: '2026-01-01T00:00:00',
    }
    authState.sessionDuration = 'day'
    authApiMock.sendEmailVerificationCode.mockResolvedValue({ expires_in_seconds: 60 })
    authApiMock.checkPassword.mockResolvedValue(true)
    authApiMock.updatePassword.mockResolvedValue(undefined)
    authApiMock.setupTotp.mockResolvedValue({ secret: 'SECRET123', provisioning_uri: 'otpauth://totp/test' })
    authApiMock.enableTotp.mockResolvedValue({ ...authState.user, totp_enabled: true })
    authApiMock.updateTotpEmailCodeReplacement.mockResolvedValue({
      ...authState.user,
      totp_enabled: true,
      totp_replaces_email_codes: true,
    })
  })

  it('shows status explanations and password composition hint', () => {
    render(<SecurityPanel />)

    expect(screen.getByLabelText('The current email is not verified.')).toBeInTheDocument()
    expect(screen.getByLabelText('Enter your current password.')).toBeInTheDocument()
    expect(screen.getByLabelText('Enter a new password.')).toBeInTheDocument()
    expect(screen.getByText('Use a combination of letters, numbers, and symbols.')).toBeInTheDocument()
  })

  it('does not send a change-email code when current email confirmation is wrong', async () => {
    render(<SecurityPanel />)

    fireEvent.click(screen.getByRole('button', { name: 'Reset Email' }))
    const emailInput = screen.getByPlaceholderText('Enter your email address')
    const emailRow = emailInput.closest('.settings-panel__row') as HTMLElement
    const resetConfirmButton = within(emailRow).getByRole('button', { name: 'Confirm' })
    expect(resetConfirmButton).toBeDisabled()
    expect(resetConfirmButton).toHaveClass('settings-panel__btn--gray')
    fireEvent.change(emailInput, {
      target: { value: 'new@example.com' },
    })
    expect(resetConfirmButton).not.toBeDisabled()
    expect(resetConfirmButton).toHaveClass('settings-panel__btn--password-ready')
    fireEvent.click(resetConfirmButton)
    fireEvent.change(screen.getByPlaceholderText('Current email'), {
      target: { value: 'wrong@example.com' },
    })
    const confirmButtons = screen.getAllByRole('button', { name: 'Confirm' })
    fireEvent.click(confirmButtons[confirmButtons.length - 1])

    expect(await screen.findByText('Current email does not match.')).toBeInTheDocument()
    expect(authApiMock.sendEmailVerificationCode).not.toHaveBeenCalled()
  })

  it('sends a change-email code to the pending new email after current email confirmation', async () => {
    render(<SecurityPanel />)

    fireEvent.click(screen.getByRole('button', { name: 'Reset Email' }))
    fireEvent.change(screen.getByPlaceholderText('Enter your email address'), {
      target: { value: 'new@example.com' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Confirm' })[0])
    const currentEmailInput = screen.getByPlaceholderText('Current email')
    fireEvent.mouseDown(currentEmailInput)
    fireEvent.change(currentEmailInput, {
      target: { value: 'old@example.com' },
    })
    const confirmButtons = screen.getAllByRole('button', { name: 'Confirm' })
    fireEvent.click(confirmButtons[confirmButtons.length - 1])

    await waitFor(() => {
      expect(authApiMock.sendEmailVerificationCode).toHaveBeenCalledWith('new@example.com', 'change_email')
    })
  })

  it('opens a success modal after password update succeeds', async () => {
    render(<SecurityPanel />)

    fireEvent.change(screen.getByPlaceholderText('Current password'), {
      target: { value: 'oldpass123' },
    })
    fireEvent.change(screen.getByPlaceholderText('New password'), {
      target: { value: 'Newpass123!' },
    })
    fireEvent.change(screen.getByPlaceholderText('Confirm new password'), {
      target: { value: 'Newpass123!' },
    })

    await waitFor(() => expect(authApiMock.checkPassword).toHaveBeenCalledWith('oldpass123'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirm' })).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(authApiMock.updatePassword).toHaveBeenCalledWith('oldpass123', 'Newpass123!'))
    expect(await screen.findByText('Password updated successfully')).toBeInTheDocument()
  })

  it('opens the TOTP setup entry and enables it after code verification', async () => {
    render(<SecurityPanel />)

    fireEvent.click(screen.getByRole('button', { name: 'Enable' }))
    const dialog = screen.getByRole('dialog', { name: 'Authenticator two-factor authentication' })
    const passwordInputs = within(dialog).getAllByPlaceholderText('Current password')
    fireEvent.change(passwordInputs[0], { target: { value: 'secret123' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(authApiMock.setupTotp).toHaveBeenCalledWith('secret123'))
    expect(await within(dialog).findByText('Scan QR code.')).toBeInTheDocument()
    expect(within(dialog).getByText('Authenticator setup QR code')).toBeInTheDocument()
    const enableButton = within(dialog).getByRole('button', { name: 'Verify and enable' })
    expect(enableButton).toBeDisabled()
    expect(enableButton).toHaveClass('settings-panel__btn--gray')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Unable to scan? Try using the secret' }))
    expect(await within(dialog).findByText('SECRET123')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'Copy secret' })).toHaveClass('settings-panel__btn--totp-action')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Not convenient? Try using the QR code' }))
    expect(await within(dialog).findByText('Scan QR code.')).toBeInTheDocument()
    fireEvent.change(within(dialog).getByPlaceholderText('Enter authenticator code'), {
      target: { value: '123 456' },
    })
    expect(enableButton).not.toBeDisabled()
    expect(enableButton).toHaveClass('settings-panel__btn--password-ready')
    fireEvent.click(enableButton)

    await waitFor(() => expect(authApiMock.enableTotp).toHaveBeenCalledWith('123456'))
    await waitFor(() => expect(authState.refreshUser).toHaveBeenCalled())
  })

  it('highlights the TOTP disable action only after password and six digits', () => {
    authState.user = { ...authState.user, totp_enabled: true }
    render(<SecurityPanel />)

    const entryButton = screen.getByRole('button', { name: 'Disable' })
    expect(entryButton).toHaveClass('settings-panel__btn--totp-action')
    fireEvent.click(entryButton)

    const dialog = screen.getByRole('dialog', { name: 'Authenticator two-factor authentication' })
    const disableButton = within(dialog).getByRole('button', { name: 'Disable' })
    expect(disableButton).toBeDisabled()
    expect(disableButton).toHaveClass('settings-panel__btn--gray')

    fireEvent.change(within(dialog).getByPlaceholderText('Current password'), {
      target: { value: 'secret123' },
    })
    fireEvent.change(within(dialog).getByPlaceholderText('Enter authenticator code'), {
      target: { value: '123 456' },
    })

    expect(disableButton).not.toBeDisabled()
    expect(disableButton).toHaveClass('settings-panel__btn--password-ready')
  })

  it('only enables the 2FA email-code replacement switch after TOTP is enabled', async () => {
    const { rerender } = render(<SecurityPanel />)
    const disabledSwitch = screen.getByRole('switch', { name: 'Use 2FA instead of email codes' })
    expect(disabledSwitch).toBeDisabled()

    authState.user = {
      ...authState.user,
      totp_enabled: true,
      totp_replaces_email_codes: false,
    }
    rerender(<SecurityPanel />)

    const enabledSwitch = screen.getByRole('switch', { name: 'Use 2FA instead of email codes' })
    expect(enabledSwitch).not.toBeDisabled()
    fireEvent.click(enabledSwitch)

    await waitFor(() => expect(authApiMock.updateTotpEmailCodeReplacement).toHaveBeenCalledWith(true))
    await waitFor(() => expect(authState.refreshUser).toHaveBeenCalled())
  })
})
