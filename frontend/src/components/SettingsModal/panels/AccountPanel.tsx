import { useState } from 'react'
import { useLocale } from '../../../context/LocaleContext'
import { useAuth } from '../../../context/AuthContext'
import { getApiErrorMessage } from '../../../services/api'
import AnimatedModal from '../../common/AnimatedModal'

type DeleteStep = 1 | 2

export default function AccountPanel() {
  const { lang, t } = useLocale()
  const { user, deleteAccount } = useAuth()
  const [nickname, setNickname] = useState(user?.username || '')
  const [deleteStep, setDeleteStep] = useState<DeleteStep | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')

  const isEnglish = lang === 'en'

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
      setDeleteError(getApiErrorMessage(err, isEnglish ? 'Account deletion failed.' : '注销账号失败，请稍后重试。'))
    } finally {
      setDeleteLoading(false)
    }
  }

  const dialogTitle = deleteStep === 1
    ? isEnglish ? 'Delete account?' : '确认注销账号？'
    : isEnglish ? 'Final confirmation' : '二次确认'
  const dialogMessage = deleteStep === 1
    ? isEnglish
      ? 'This will permanently delete your account and sign you out. This action cannot be undone.'
      : '注销后将永久删除当前账号并退出登录，此操作不可撤销。'
    : isEnglish
      ? 'Please confirm again. After this step, your account will be deleted immediately.'
      : '请再次确认。点击确认后，当前账号将立即注销。'

  return (
    <div className="settings-panel">
      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.avatar')}</div>
        <div className="settings-panel__avatar-row">
          <div className="settings-panel__avatar">
            {user ? (
              <span style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', height: '100%', fontSize: '24px', fontWeight: 600,
                color: '#fff', background: 'var(--primary)', borderRadius: '50%',
              }}>
                {(user.username || user.email || '?')[0].toUpperCase()}
              </span>
            ) : null}
          </div>
          <button className="settings-panel__btn settings-panel__btn--gray" type="button">
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
            onChange={(e) => setNickname(e.target.value)}
            placeholder={t('settings.account.nicknamePlaceholder')}
          />
          <button className="settings-panel__btn settings-panel__btn--gray" type="button">
            {t('settings.account.saveNickname')}
          </button>
        </div>
      </div>

      <div className="settings-panel__section">
        <div className="settings-panel__label">{t('settings.account.username')}</div>
        <div className="settings-panel__row">
          <input
            className="settings-panel__input"
            type="text"
            value={user?.username || ''}
            readOnly
          />
        </div>
        <p className="settings-panel__hint">{t('settings.account.usernameDesc')}</p>
      </div>

      <div className="settings-panel__section settings-panel__danger-zone">
        <div className="settings-panel__label">
          {isEnglish ? 'Danger zone' : '危险操作'}
        </div>
        <p className="settings-panel__hint">
          {isEnglish
            ? 'Deleting your account removes your profile, login sessions, saved server-side data, and cannot be undone.'
            : '注销账号会删除你的个人资料、登录会话和服务端保存的数据，操作不可撤销。'}
        </p>
        <button
          className="settings-panel__btn settings-panel__btn--danger"
          type="button"
          onClick={startDeleteFlow}
        >
          {isEnglish ? 'Delete account' : '注销账号'}
        </button>
      </div>

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
                {isEnglish ? 'Cancel' : '取消'}
              </button>
              <button
                className="settings-panel__btn settings-panel__btn--danger"
                type="button"
                onClick={deleteStep === 1 ? confirmFirstStep : confirmDeleteAccount}
                disabled={deleteLoading}
              >
                {deleteLoading ? '...' : isEnglish ? 'Confirm' : '确认'}
              </button>
            </div>
      </AnimatedModal>
    </div>
  )
}
