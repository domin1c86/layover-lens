import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import { authApi, getApiErrorMessage } from '../../../services/api'
import {
  addLocalAvatar,
  clearCurrentLocalAvatar,
  getCurrentLocalAvatar,
  getLocalAvatars,
  setCurrentLocalAvatarId,
  type LocalAvatar,
} from '../../../services/avatarStorage'
import { materialAvatars } from '../../../icons/materialAvatars'
import type { UserProfile } from '../../../types'
import AnimatedModal from '../../common/AnimatedModal'
import UserAvatar from '../../common/UserAvatar'

type DeleteStep = 1 | 2
type AvatarSelection = `local:${string}` | `material:${string}`

interface CropState {
  src: string
  naturalWidth: number
  naturalHeight: number
  scale: number
  offsetX: number
  offsetY: number
}

const CROP_SIZE = 256

function profileNickname(user: UserProfile | null) {
  return user?.nickname || user?.username || ''
}

function selectionFromUser(user: UserProfile | null): AvatarSelection | '' {
  if (!user) return ''
  const localAvatar = getCurrentLocalAvatar(user.id)
  if (localAvatar) return `local:${localAvatar.id}`
  if (user.avatar_url?.startsWith('material:')) return `material:${user.avatar_url.slice('material:'.length)}`
  return ''
}

export default function AccountPanel() {
  const { t } = useLocale()
  const { user, deleteAccount, refreshUser } = useAuth()
  const currentNickname = useMemo(() => profileNickname(user), [user])
  const [nickname, setNickname] = useState(currentNickname)
  const [nicknameLoading, setNicknameLoading] = useState(false)
  const [nicknameError, setNicknameError] = useState('')
  const [nicknameSuccess, setNicknameSuccess] = useState('')
  const [deleteStep, setDeleteStep] = useState<DeleteStep | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [avatarDialogOpen, setAvatarDialogOpen] = useState(false)
  const [localAvatars, setLocalAvatars] = useState<LocalAvatar[]>([])
  const [selectedAvatar, setSelectedAvatar] = useState<AvatarSelection | ''>('')
  const [avatarLoading, setAvatarLoading] = useState(false)
  const [avatarError, setAvatarError] = useState('')
  const [cropState, setCropState] = useState<CropState | null>(null)
  const [cropDragging, setCropDragging] = useState(false)
  const dragOriginRef = useRef<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const trimmedNickname = nickname.trim()
  const canSaveNickname = Boolean(trimmedNickname) && trimmedNickname !== currentNickname.trim() && !nicknameLoading

  useEffect(() => {
    setNickname(currentNickname)
    setNicknameError('')
    setNicknameSuccess('')
  }, [currentNickname])

  const openAvatarDialog = () => {
    if (!user) return
    setLocalAvatars(getLocalAvatars(user.id))
    setSelectedAvatar(selectionFromUser(user))
    setAvatarError('')
    setAvatarDialogOpen(true)
  }

  const closeAvatarDialog = () => {
    if (avatarLoading) return
    setAvatarDialogOpen(false)
    setAvatarError('')
  }

  const saveNickname = async () => {
    if (!canSaveNickname) return
    setNicknameLoading(true)
    setNicknameError('')
    setNicknameSuccess('')
    try {
      await authApi.updateProfile(trimmedNickname)
      await refreshUser()
      setNicknameSuccess(t('settings.account.nicknameSaved'))
    } catch (err) {
      setNicknameError(getApiErrorMessage(err, t('settings.account.nicknameSaveFailed')))
    } finally {
      setNicknameLoading(false)
    }
  }

  const confirmAvatarSelection = async () => {
    if (!user || !selectedAvatar) return
    setAvatarLoading(true)
    setAvatarError('')
    try {
      if (selectedAvatar.startsWith('local:')) {
        setCurrentLocalAvatarId(user.id, selectedAvatar.slice('local:'.length))
      } else {
        await authApi.updateAvatarPreset(selectedAvatar.slice('material:'.length))
        clearCurrentLocalAvatar(user.id)
        await refreshUser()
      }
      setAvatarDialogOpen(false)
    } catch (err) {
      setAvatarError(getApiErrorMessage(err, t('settings.account.avatarSaveFailed')))
    } finally {
      setAvatarLoading(false)
    }
  }

  const handleFileSelected = (file: File | null) => {
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setAvatarError(t('settings.account.avatarInvalidFile'))
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const src = String(reader.result || '')
      const image = new Image()
      image.onload = () => {
        setCropState({
          src,
          naturalWidth: image.naturalWidth,
          naturalHeight: image.naturalHeight,
          scale: 1,
          offsetX: 0,
          offsetY: 0,
        })
        setAvatarError('')
      }
      image.onerror = () => setAvatarError(t('settings.account.avatarInvalidFile'))
      image.src = src
    }
    reader.readAsDataURL(file)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const adjustCrop = (patch: Partial<Pick<CropState, 'scale' | 'offsetX' | 'offsetY'>>) => {
    setCropState((current) => {
      if (!current) return current
      return {
        ...current,
        ...patch,
        scale: Math.min(4, Math.max(0.5, patch.scale ?? current.scale)),
      }
    })
  }

  const moveCrop = (dx: number, dy: number) => {
    setCropState((current) => current ? {
      ...current,
      offsetX: current.offsetX + dx,
      offsetY: current.offsetY + dy,
    } : current)
  }

  const cropMetrics = cropState
    ? (() => {
      const baseScale = Math.max(CROP_SIZE / cropState.naturalWidth, CROP_SIZE / cropState.naturalHeight)
      const drawWidth = cropState.naturalWidth * baseScale * cropState.scale
      const drawHeight = cropState.naturalHeight * baseScale * cropState.scale
      return {
        drawWidth,
        drawHeight,
        x: (CROP_SIZE - drawWidth) / 2 + cropState.offsetX,
        y: (CROP_SIZE - drawHeight) / 2 + cropState.offsetY,
      }
    })()
    : null

  const saveCrop = () => {
    if (!cropState || !cropMetrics || !user) return
    const image = new Image()
    image.onload = () => {
      const canvas = document.createElement('canvas')
      canvas.width = CROP_SIZE
      canvas.height = CROP_SIZE
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        setAvatarError(t('settings.account.avatarCropFailed'))
        return
      }
      ctx.clearRect(0, 0, CROP_SIZE, CROP_SIZE)
      ctx.save()
      ctx.beginPath()
      ctx.arc(CROP_SIZE / 2, CROP_SIZE / 2, CROP_SIZE / 2, 0, Math.PI * 2)
      ctx.clip()
      ctx.drawImage(image, cropMetrics.x, cropMetrics.y, cropMetrics.drawWidth, cropMetrics.drawHeight)
      ctx.restore()
      const avatar = addLocalAvatar(user.id, canvas.toDataURL('image/png'))
      setLocalAvatars(getLocalAvatars(user.id))
      setSelectedAvatar(`local:${avatar.id}`)
      setCropState(null)
    }
    image.onerror = () => setAvatarError(t('settings.account.avatarCropFailed'))
    image.src = cropState.src
  }

  const closeDeleteDialog = () => {
    if (deleteLoading) return
    setDeleteStep(null)
    setDeleteError('')
  }

  const startDeleteFlow = () => {
    setDeleteStep(1)
    setDeleteError('')
  }

  const confirmFirstStep = () => {
    setDeleteStep(2)
    setDeleteError('')
  }

  const confirmDeleteAccount = async () => {
    setDeleteLoading(true)
    setDeleteError('')
    try {
      await deleteAccount()
      setDeleteStep(null)
    } catch (err) {
      setDeleteError(getApiErrorMessage(err, t('settings.account.deleteFailed')))
    } finally {
      setDeleteLoading(false)
    }
  }

  const dialogTitle = deleteStep === 1
    ? t('settings.account.deleteTitle')
    : t('settings.account.deleteFinalTitle')
  const dialogMessage = deleteStep === 1
    ? t('settings.account.deleteMessage')
    : t('settings.account.deleteFinalMessage')

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.avatar')}</div>
        <div className="settings-panel__avatar-row">
          <UserAvatar user={user} className="settings-panel__avatar" />
          <button
            className="settings-panel__btn settings-panel__btn--gray settings-panel__btn--avatar"
            type="button"
            onClick={openAvatarDialog}
          >
            {t('settings.account.changeAvatar')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.nickname')}</div>
        <div className="settings-panel__row">
          <input
            className="settings-panel__input"
            type="text"
            value={nickname}
            onChange={(event) => {
              setNickname(event.target.value)
              setNicknameError('')
              setNicknameSuccess('')
            }}
            placeholder={t('settings.account.nicknamePlaceholder')}
          />
          <button
            className={`settings-panel__btn ${canSaveNickname ? 'settings-panel__btn--password-ready' : 'settings-panel__btn--gray'}`}
            type="button"
            onClick={saveNickname}
            disabled={!canSaveNickname}
          >
            {nicknameLoading ? '...' : t('settings.account.saveNickname')}
          </button>
        </div>
        {!trimmedNickname && <p className="forgot-modal__error">{t('settings.account.nicknameRequired')}</p>}
        {nicknameError && <p className="forgot-modal__error">{nicknameError}</p>}
        {nicknameSuccess && <p className="forgot-modal__success">{nicknameSuccess}</p>}
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.username')}</div>
        <div className="settings-panel__row">
          <input
            className="settings-panel__input"
            type="text"
            value={user?.id || user?.username || ''}
            readOnly
          />
        </div>
        <p className="settings-panel__hint">{t('settings.account.usernameDesc')}</p>
      </div>

      <div className="settings-panel__section settings-panel__danger-zone">
        <div className="settings-panel__label">{t('settings.account.dangerZone')}</div>
        <p className="settings-panel__hint">{t('settings.account.deleteHint')}</p>
        <button
          className="settings-panel__btn settings-panel__btn--danger"
          type="button"
          onClick={startDeleteFlow}
        >
          {t('settings.account.deleteAccount')}
        </button>
      </div>

      <AnimatedModal
        isOpen={avatarDialogOpen}
        overlayClassName="avatar-modal__overlay"
        dialogClassName="avatar-modal__dialog"
        ariaLabel={t('settings.account.avatarDialogTitle')}
        onClose={closeAvatarDialog}
      >
        <div className="avatar-modal__header">
          <h3 className="avatar-modal__title">{t('settings.account.avatarDialogTitle')}</h3>
          <button className="forgot-modal__close" type="button" onClick={closeAvatarDialog} aria-label={t('settings.account.cancel')}>
            <span className="avatar-crop__icon avatar-crop__icon--close" aria-hidden="true" />
          </button>
        </div>
        <div className="avatar-modal__body">
          <div className="avatar-modal__local-grid">
            <button
              className="avatar-modal__upload"
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              <span>{t('settings.account.avatarUploadLine1')}</span>
              <span>{t('settings.account.avatarUploadLine2')}</span>
            </button>
            {localAvatars.map((avatar) => (
              <button
                key={avatar.id}
                className={`avatar-modal__option ${selectedAvatar === `local:${avatar.id}` ? 'selected' : ''}`}
                type="button"
                onClick={() => setSelectedAvatar(`local:${avatar.id}`)}
                aria-label={t('settings.account.avatarLocalOption')}
              >
                <img src={avatar.dataUrl} alt="" />
              </button>
            ))}
          </div>
          <div className="avatar-modal__preset-grid">
            {materialAvatars.map((avatar) => (
              <button
                key={avatar.id}
                className={`avatar-modal__option ${selectedAvatar === `material:${avatar.id}` ? 'selected' : ''}`}
                type="button"
                onClick={() => setSelectedAvatar(`material:${avatar.id}`)}
                aria-label={t('settings.account.avatarPresetOption', { id: avatar.id })}
              >
                <img src={avatar.url} alt="" />
              </button>
            ))}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(event) => handleFileSelected(event.target.files?.[0] || null)}
          />
          {avatarError && <p className="forgot-modal__error">{avatarError}</p>}
        </div>
        <div className="avatar-modal__actions">
          <button className="settings-panel__btn settings-panel__btn--gray" type="button" onClick={closeAvatarDialog} disabled={avatarLoading}>
            {t('settings.account.cancel')}
          </button>
          <button
            className="settings-panel__btn settings-panel__btn--password-ready"
            type="button"
            onClick={confirmAvatarSelection}
            disabled={!selectedAvatar || avatarLoading}
          >
            {avatarLoading ? '...' : t('settings.account.confirm')}
          </button>
        </div>
      </AnimatedModal>

      <AnimatedModal
        isOpen={cropState !== null}
        overlayClassName="avatar-modal__overlay"
        dialogClassName="avatar-crop__dialog"
        ariaLabel={t('settings.account.avatarCropTitle')}
        onClose={() => setCropState(null)}
      >
        {cropState && cropMetrics && (
          <>
            <h3 className="avatar-modal__title">{t('settings.account.avatarCropTitle')}</h3>
            <div
              className="avatar-crop__stage"
              onWheel={(event) => {
                event.preventDefault()
                adjustCrop({ scale: cropState.scale + (event.deltaY < 0 ? 0.08 : -0.08) })
              }}
              onMouseDown={(event) => {
                setCropDragging(true)
                dragOriginRef.current = {
                  x: event.clientX,
                  y: event.clientY,
                  offsetX: cropState.offsetX,
                  offsetY: cropState.offsetY,
                }
              }}
              onMouseMove={(event) => {
                if (!cropDragging || !dragOriginRef.current) return
                adjustCrop({
                  offsetX: dragOriginRef.current.offsetX + event.clientX - dragOriginRef.current.x,
                  offsetY: dragOriginRef.current.offsetY + event.clientY - dragOriginRef.current.y,
                })
              }}
              onMouseUp={() => setCropDragging(false)}
              onMouseLeave={() => setCropDragging(false)}
            >
              <img
                src={cropState.src}
                alt=""
                className="avatar-crop__image"
                style={{
                  width: `${cropMetrics.drawWidth}px`,
                  height: `${cropMetrics.drawHeight}px`,
                  left: `${cropMetrics.x}px`,
                  top: `${cropMetrics.y}px`,
                }}
                draggable={false}
              />
              <div className="avatar-crop__mask" aria-hidden="true" />
            </div>
            <div className="avatar-crop__tools">
              <button type="button" onClick={() => adjustCrop({ scale: cropState.scale + 0.08 })} aria-label={t('settings.account.avatarZoomIn')}>
                <span className="avatar-crop__icon avatar-crop__icon--zoom-in" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => adjustCrop({ scale: cropState.scale - 0.08 })} aria-label={t('settings.account.avatarZoomOut')}>
                <span className="avatar-crop__icon avatar-crop__icon--zoom-out" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => moveCrop(-12, 0)} aria-label={t('settings.account.avatarMoveLeft')}>
                <span className="avatar-crop__icon avatar-crop__icon--left" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => moveCrop(12, 0)} aria-label={t('settings.account.avatarMoveRight')}>
                <span className="avatar-crop__icon avatar-crop__icon--right" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => moveCrop(0, -12)} aria-label={t('settings.account.avatarMoveUp')}>
                <span className="avatar-crop__icon avatar-crop__icon--up" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => moveCrop(0, 12)} aria-label={t('settings.account.avatarMoveDown')}>
                <span className="avatar-crop__icon avatar-crop__icon--down" aria-hidden="true" />
              </button>
              <button type="button" onClick={() => setCropState(null)} aria-label={t('settings.account.cancel')}>
                <span className="avatar-crop__icon avatar-crop__icon--close" aria-hidden="true" />
              </button>
              <button type="button" onClick={saveCrop} aria-label={t('settings.account.confirm')}>
                <span className="avatar-crop__icon avatar-crop__icon--check" aria-hidden="true" />
              </button>
            </div>
          </>
        )}
      </AnimatedModal>

      <AnimatedModal
        isOpen={deleteStep !== null}
        overlayClassName="account-delete-modal__overlay"
        dialogClassName="account-delete-modal__dialog"
        ariaLabel={dialogTitle}
        onClose={closeDeleteDialog}
      >
        <h3 className="account-delete-modal__title">{dialogTitle}</h3>
        <p className="account-delete-modal__message">{dialogMessage}</p>
        {deleteError && <p className="account-delete-modal__error">{deleteError}</p>}
        <div className="account-delete-modal__actions">
          <button
            className="settings-panel__btn settings-panel__btn--gray"
            type="button"
            onClick={closeDeleteDialog}
            disabled={deleteLoading}
          >
            {t('settings.account.cancel')}
          </button>
          <button
            className="settings-panel__btn settings-panel__btn--danger"
            type="button"
            onClick={deleteStep === 1 ? confirmFirstStep : confirmDeleteAccount}
            disabled={deleteLoading}
          >
            {deleteLoading ? '...' : t('settings.account.confirm')}
          </button>
        </div>
      </AnimatedModal>
    </div>
  )
}
