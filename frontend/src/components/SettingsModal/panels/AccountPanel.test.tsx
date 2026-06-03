import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AccountPanel from './AccountPanel'

const authApiMock = vi.hoisted(() => ({
  updateProfile: vi.fn(),
  updateAvatarPreset: vi.fn(),
}))

const authState = vi.hoisted(() => ({
  user: {
    id: 'user_202605061508090',
    username: 'user_202605061508090',
    email: 'tester@example.com',
    email_verified: true,
    nickname: 'Initial Nick',
    created_at: '2026-05-06T07:08:09',
  },
  deleteAccount: vi.fn(),
  refreshUser: vi.fn(),
}))

const messages: Record<string, string> = {
  'settings.account.avatar': 'Avatar',
  'settings.account.changeAvatar': 'Change Avatar',
  'settings.account.avatarDialogTitle': 'Choose avatar',
  'settings.account.avatarUploadLine1': 'Upload',
  'settings.account.avatarUploadLine2': 'Avatar',
  'settings.account.avatarLocalOption': 'Uploaded avatar',
  'settings.account.avatarPresetOption': 'Preset avatar {{id}}',
  'settings.account.avatarSaveFailed': 'Unable to save avatar.',
  'settings.account.avatarInvalidFile': 'Please choose an image file.',
  'settings.account.avatarCropTitle': 'Edit avatar',
  'settings.account.avatarCropFailed': 'Unable to crop avatar.',
  'settings.account.avatarZoomIn': 'Zoom in',
  'settings.account.avatarZoomOut': 'Zoom out',
  'settings.account.avatarMoveLeft': 'Move left',
  'settings.account.avatarMoveRight': 'Move right',
  'settings.account.avatarMoveUp': 'Move up',
  'settings.account.avatarMoveDown': 'Move down',
  'settings.account.nickname': 'Nickname',
  'settings.account.nicknamePlaceholder': 'Enter your nickname',
  'settings.account.saveNickname': 'Save Nickname',
  'settings.account.nicknameSaved': 'Nickname saved.',
  'settings.account.nicknameRequired': 'Nickname cannot be empty.',
  'settings.account.nicknameSaveFailed': 'Unable to save nickname.',
  'settings.account.username': 'User ID',
  'settings.account.usernameDesc': 'User ID is generated at registration and cannot be changed.',
  'settings.account.dangerZone': 'Danger zone',
  'settings.account.deleteHint': 'Deleting cannot be undone.',
  'settings.account.deleteAccount': 'Delete account',
  'settings.account.deleteTitle': 'Delete account?',
  'settings.account.deleteMessage': 'This action cannot be undone.',
  'settings.account.deleteFinalTitle': 'Final confirmation',
  'settings.account.deleteFinalMessage': 'Please confirm again.',
  'settings.account.deleteFailed': 'Account deletion failed.',
  'settings.account.cancel': 'Cancel',
  'settings.account.confirm': 'Confirm',
}

vi.mock('../../../context/LocaleContext', () => ({
  useLocale: () => ({
    lang: 'en',
    t: (key: string, vars?: Record<string, string>) => {
      let value = messages[key] ?? key
      if (vars) {
        Object.entries(vars).forEach(([name, replacement]) => {
          value = value.replace(`{{${name}}}`, replacement)
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

vi.mock('../../../icons/materialAvatars', () => ({
  materialAvatars: [
    { id: 'm1', url: '/avatars/m1.svg' },
    { id: 'w1', url: '/avatars/w1.svg' },
  ],
  getMaterialAvatarUrl: (id: string) => `/avatars/${id}.svg`,
}))

describe('AccountPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.user = {
      id: 'user_202605061508090',
      username: 'user_202605061508090',
      email: 'tester@example.com',
      email_verified: true,
      nickname: 'Initial Nick',
      created_at: '2026-05-06T07:08:09',
    }
    authApiMock.updateProfile.mockResolvedValue({
      ...authState.user,
      nickname: 'New Nick',
    })
    authApiMock.updateAvatarPreset.mockResolvedValue({
      ...authState.user,
      avatar_url: 'material:m1',
    })
    authState.refreshUser.mockResolvedValue(undefined)
    authState.deleteAccount.mockResolvedValue(undefined)
    localStorage.clear()
  })

  it('shows nickname and read-only generated user id', () => {
    render(<AccountPanel />)

    expect(screen.getByDisplayValue('Initial Nick')).toBeInTheDocument()
    expect(screen.getByDisplayValue('user_202605061508090')).toBeInTheDocument()
    expect(screen.getByText('User ID')).toBeInTheDocument()
  })

  it('highlights and saves nickname only after it changes', async () => {
    render(<AccountPanel />)

    const saveButton = screen.getByRole('button', { name: 'Save Nickname' })
    expect(saveButton).toBeDisabled()
    expect(saveButton).toHaveClass('settings-panel__btn--gray')

    fireEvent.change(screen.getByDisplayValue('Initial Nick'), {
      target: { value: 'New Nick' },
    })

    expect(saveButton).not.toBeDisabled()
    expect(saveButton).toHaveClass('settings-panel__btn--password-ready')
    fireEvent.click(saveButton)

    await waitFor(() => expect(authApiMock.updateProfile).toHaveBeenCalledWith('New Nick'))
    await waitFor(() => expect(authState.refreshUser).toHaveBeenCalledOnce())
    expect(await screen.findByText('Nickname saved.')).toBeInTheDocument()
  })

  it('opens avatar chooser and saves a preset avatar', async () => {
    render(<AccountPanel />)

    fireEvent.click(screen.getByRole('button', { name: 'Change Avatar' }))

    expect(screen.getByRole('dialog', { name: 'Choose avatar' })).toBeInTheDocument()
    const uploadButton = screen.getByRole('button', { name: /UploadAvatar/ })
    expect(uploadButton).toHaveTextContent('Upload')
    expect(uploadButton).toHaveTextContent('Avatar')

    fireEvent.click(screen.getByRole('button', { name: 'Preset avatar m1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() => expect(authApiMock.updateAvatarPreset).toHaveBeenCalledWith('m1'))
    await waitFor(() => expect(authState.refreshUser).toHaveBeenCalledOnce())
  })

  it('stores a cropped upload locally and selects it in the chooser', async () => {
    const originalFileReader = globalThis.FileReader
    const originalImage = globalThis.Image
    const getContextSpy = vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      clearRect: vi.fn(),
      save: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      clip: vi.fn(),
      drawImage: vi.fn(),
      restore: vi.fn(),
    } as unknown as CanvasRenderingContext2D)
    const toDataUrlSpy = vi
      .spyOn(HTMLCanvasElement.prototype, 'toDataURL')
      .mockReturnValue('data:image/png;base64,cropped')

    class MockFileReader {
      result: string | ArrayBuffer | null = 'data:image/png;base64,input'
      onload: ((event: ProgressEvent<FileReader>) => void) | null = null
      readAsDataURL() {
        this.onload?.({} as ProgressEvent<FileReader>)
      }
    }

    class MockImage {
      naturalWidth = 512
      naturalHeight = 512
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      set src(_value: string) {
        window.setTimeout(() => this.onload?.(), 0)
      }
    }

    vi.stubGlobal('FileReader', MockFileReader)
    vi.stubGlobal('Image', MockImage)

    try {
      const { container } = render(<AccountPanel />)

      fireEvent.click(screen.getByRole('button', { name: 'Change Avatar' }))
      const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement
      fireEvent.change(fileInput, {
        target: {
          files: [new File(['avatar'], 'avatar.png', { type: 'image/png' })],
        },
      })

      expect(await screen.findByRole('dialog', { name: 'Edit avatar' })).toBeInTheDocument()
      const confirmButtons = screen.getAllByRole('button', { name: 'Confirm' })
      fireEvent.click(confirmButtons[confirmButtons.length - 1])

      await waitFor(() => expect(toDataUrlSpy).toHaveBeenCalledWith('image/png'))
      expect(await screen.findByRole('button', { name: 'Uploaded avatar' })).toHaveClass('selected')
    } finally {
      vi.stubGlobal('FileReader', originalFileReader)
      vi.stubGlobal('Image', originalImage)
      getContextSpy.mockRestore()
      toDataUrlSpy.mockRestore()
    }
  })
})
