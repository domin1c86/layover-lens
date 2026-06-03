import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../../context/AuthContext'
import { useLocale } from '../../../context/LocaleContext'
import { authApi, getApiErrorMessage } from '../../../services/api'
import type { DeviceInfo } from '../../../types'

function detectPlatform(deviceName: string, fallback: string) {
  const value = deviceName.toLowerCase()
  const os = value.includes('windows')
    ? 'Windows'
    : value.includes('mac os') || value.includes('macintosh')
      ? 'macOS'
      : value.includes('iphone') || value.includes('ipad')
        ? 'iOS'
        : value.includes('android')
          ? 'Android'
          : value.includes('linux')
            ? 'Linux'
            : fallback

  const browser = value.includes('edg/')
    ? 'Edge'
    : value.includes('chrome/')
      ? 'Chrome'
      : value.includes('firefox/')
        ? 'Firefox'
        : value.includes('safari/')
          ? 'Safari'
          : ''

  return browser ? `${os} / ${browser}` : os
}

export default function DevicesPanel() {
  const { t, lang } = useLocale()
  const { isLoggedIn } = useAuth()
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [revokingId, setRevokingId] = useState<string | null>(null)

  const asyncCopy = useMemo(
    () => ({
      loadFailed: t('settings.devices.loadFailed'),
      revokeFailed: t('settings.devices.revokeFailed'),
    }),
    [lang]
  )

  const formatter = useMemo(
    () => new Intl.DateTimeFormat(lang === 'en' ? 'en-US' : 'zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }),
    [lang]
  )

  const loadDevices = useCallback(async () => {
    if (!isLoggedIn) {
      setDevices([])
      return
    }
    setLoading(true)
    setError('')
    try {
      setDevices(await authApi.listDevices())
    } catch (err) {
      setError(getApiErrorMessage(err, asyncCopy.loadFailed))
    } finally {
      setLoading(false)
    }
  }, [asyncCopy.loadFailed, isLoggedIn])

  useEffect(() => {
    void loadDevices()
  }, [loadDevices])

  const revokeDevice = async (deviceId: string) => {
    setRevokingId(deviceId)
    setError('')
    try {
      await authApi.revokeDevice(deviceId)
      await loadDevices()
    } catch (err) {
      setError(getApiErrorMessage(err, asyncCopy.revokeFailed))
    } finally {
      setRevokingId(null)
    }
  }

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.devices.title')}</div>
        {loading && <p className="settings-panel__hint">{t('settings.devices.loading')}</p>}
        {error && <p className="forgot-modal__error">{error}</p>}
        {!loading && devices.length === 0 ? (
          <p className="settings-panel__hint settings-panel__empty">{t('settings.devices.noDevices')}</p>
        ) : (
          <div className="settings-panel__device-list">
            {devices.map((device) => {
              const platform = detectPlatform(device.device_name, t('settings.devices.unknownPlatform'))
              const loginTime = formatter.format(new Date(device.login_time))
              return (
                <article
                  className={`settings-panel__device-card ${device.is_current ? 'current' : ''}`}
                  key={device.id}
                >
                  <div className="settings-panel__device-header">
                    <div>
                      <div className="settings-panel__device-name">
                        {platform}
                        {device.is_current && (
                          <span className="settings-panel__device-tag">{t('settings.devices.current')}</span>
                        )}
                      </div>
                    </div>
                    {!device.is_current && (
                      <button
                        className="settings-panel__btn settings-panel__btn--gray"
                        type="button"
                        disabled={revokingId === device.id}
                        onClick={() => void revokeDevice(device.id)}
                      >
                        {revokingId === device.id ? '...' : t('settings.devices.logout')}
                      </button>
                    )}
                  </div>
                  <div className="settings-panel__device-meta-grid">
                    <div>
                      <span>{t('settings.devices.loginTime')}</span>
                      <strong>{loginTime}</strong>
                    </div>
                    <div>
                      <span>{t('settings.devices.ipAddress')}</span>
                      <strong>{device.ip_address || t('settings.devices.unknownIp')}</strong>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
