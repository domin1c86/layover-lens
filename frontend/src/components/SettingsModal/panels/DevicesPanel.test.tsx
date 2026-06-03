import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DevicesPanel from './DevicesPanel'
import type { DeviceInfo } from '../../../types'

const authApiMock = vi.hoisted(() => ({
  listDevices: vi.fn(),
  revokeDevice: vi.fn(),
}))

const authState = vi.hoisted(() => ({
  isLoggedIn: true,
}))

const messages: Record<string, string> = {
  'settings.devices.title': 'Login Devices',
  'settings.devices.current': 'Current Device',
  'settings.devices.deviceName': 'Device Name',
  'settings.devices.loginTime': 'Last active',
  'settings.devices.ipAddress': 'IP Address',
  'settings.devices.logout': 'Log Out',
  'settings.devices.loading': 'Loading login devices...',
  'settings.devices.loadFailed': 'Unable to load login devices.',
  'settings.devices.revokeFailed': 'Unable to log out this device.',
  'settings.devices.unknownPlatform': 'Unknown platform',
  'settings.devices.unknownIp': 'Unknown IP',
  'settings.devices.noDevices': 'No login devices',
}

vi.mock('../../../context/LocaleContext', () => ({
  useLocale: () => ({
    lang: 'en',
    t: (key: string) => messages[key] ?? key,
  }),
}))

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authState,
}))

vi.mock('../../../services/api', () => ({
  authApi: authApiMock,
  getApiErrorMessage: (_error: unknown, fallback: string) => fallback,
}))

const devices: DeviceInfo[] = [
  {
    id: 'device_current',
    device_name: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit Chrome/125.0 Safari/537.36',
    ip_address: '127.0.0.1',
    login_time: '2026-06-02T12:00:00',
    is_current: true,
  },
  {
    id: 'device_old',
    device_name: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit Version/17.0 Safari/605.1.15',
    ip_address: '10.0.0.2',
    login_time: '2026-06-01T12:00:00',
    is_current: false,
  },
]

describe('DevicesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    authState.isLoggedIn = true
    authApiMock.listDevices.mockResolvedValue(devices)
    authApiMock.revokeDevice.mockResolvedValue(undefined)
  })

  it('renders login devices as cards', async () => {
    render(<DevicesPanel />)

    expect(await screen.findByText('Windows / Chrome')).toBeInTheDocument()
    expect(screen.getByText('Current Device')).toBeInTheDocument()
    expect(screen.getByText('macOS / Safari')).toBeInTheDocument()
    expect(screen.getByText('127.0.0.1')).toBeInTheDocument()
    expect(screen.getByText('10.0.0.2')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Log Out' })).toHaveLength(1)
  })

  it('revokes a non-current device and refreshes the list', async () => {
    authApiMock.listDevices
      .mockResolvedValueOnce(devices)
      .mockResolvedValueOnce(devices.filter((device) => device.id !== 'device_old'))

    render(<DevicesPanel />)

    fireEvent.click(await screen.findByRole('button', { name: 'Log Out' }))

    await waitFor(() => expect(authApiMock.revokeDevice).toHaveBeenCalledWith('device_old'))
    await waitFor(() => expect(authApiMock.listDevices).toHaveBeenCalledTimes(2))
    expect(screen.queryByText('macOS / Safari')).not.toBeInTheDocument()
  })
})
