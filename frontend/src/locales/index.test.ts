import { describe, it, expect } from 'vitest'
import { dict } from './index'

describe('dictionary', () => {
  it('has zh and en keys', () => {
    expect(dict.zh).toBeDefined()
    expect(dict.en).toBeDefined()
  })

  it('zh has all required top-level namespaces', () => {
    const required = [
      'topNav',
      'searchBar',
      'searchTab',
      'aiChat',
      'calendar',
      'errors',
      'cityGroups',
      'optimize',
      'resultList',
      'footer',
    ]
    for (const ns of required) {
      expect(dict.zh[ns as keyof typeof dict.zh]).toBeDefined()
    }
  })

  it('en mirrors zh structure for all keys', () => {
    function checkMirror(zhObj: any, enObj: any, path: string) {
      if (typeof zhObj === 'string') {
        expect(typeof enObj).toBe('string')
        return
      }
      if (Array.isArray(zhObj)) {
        expect(Array.isArray(enObj)).toBe(true)
        expect(enObj.length).toBe(zhObj.length)
        return
      }
      for (const key of Object.keys(zhObj)) {
        expect(enObj).toHaveProperty(key)
        checkMirror(zhObj[key], enObj[key], `${path}.${key}`)
      }
    }
    checkMirror(dict.zh, dict.en, 'dict')
  })

  it('contains account security copy required by verified flows', () => {
    const keys = [
      'sessionDuration',
      'sessionHint',
      'sessionUpdateFailed',
      'statusEmailVerified',
      'statusEmailUnverified',
      'statusCurrentPasswordEmpty',
      'statusCurrentPasswordValid',
      'statusCurrentPasswordInvalid',
      'statusNewPasswordSame',
      'statusNewPasswordWeak',
      'statusNewPasswordMedium',
      'statusNewPasswordStrong',
      'statusConfirmPasswordValid',
      'statusConfirmPasswordInvalid',
      'passwordCompositionHint',
      'passwordSuccessTitle',
      'passwordSuccessDesc',
      'changeEmailOldTitle',
      'changeEmailCodeTitle',
      'oldEmailMismatch',
      'newEmailInvalid',
      'totpQrSetupDesc',
      'totpQrCodeLabel',
      'totpUseSecret',
      'totpUseQr',
      'totpReplacementTitle',
      'totpReplacementDesc',
      'totpReplacementOwnershipNote',
      'totpReplacementFailed',
    ]

    for (const key of keys) {
      expect(dict.zh.settings.security).toHaveProperty(key)
      expect(dict.en.settings.security).toHaveProperty(key)
      expect(dict.zh.settings.security[key as keyof typeof dict.zh.settings.security]).toBeTruthy()
      expect(dict.en.settings.security[key as keyof typeof dict.en.settings.security]).toBeTruthy()
    }
  })

  it('contains account settings copy required by profile flows', () => {
    const keys = [
      'nickname',
      'nicknamePlaceholder',
      'saveNickname',
      'nicknameSaved',
      'nicknameRequired',
      'nicknameSaveFailed',
      'avatar',
      'changeAvatar',
      'avatarDialogTitle',
      'avatarUploadLine1',
      'avatarUploadLine2',
      'avatarLocalOption',
      'avatarPresetOption',
      'avatarSaveFailed',
      'avatarInvalidFile',
      'avatarCropTitle',
      'avatarCropFailed',
      'avatarZoomIn',
      'avatarZoomOut',
      'avatarMoveLeft',
      'avatarMoveRight',
      'avatarMoveUp',
      'avatarMoveDown',
      'username',
      'usernameDesc',
      'dangerZone',
      'deleteHint',
      'deleteAccount',
      'deleteTitle',
      'deleteMessage',
      'deleteFinalTitle',
      'deleteFinalMessage',
      'deleteFailed',
      'cancel',
      'confirm',
    ]

    for (const key of keys) {
      expect(dict.zh.settings.account).toHaveProperty(key)
      expect(dict.en.settings.account).toHaveProperty(key)
      expect(dict.zh.settings.account[key as keyof typeof dict.zh.settings.account]).toBeTruthy()
      expect(dict.en.settings.account[key as keyof typeof dict.en.settings.account]).toBeTruthy()
    }
  })

  it('contains device management copy', () => {
    const keys = [
      'title',
      'current',
      'deviceName',
      'loginTime',
      'ipAddress',
      'logout',
      'loading',
      'loadFailed',
      'revokeFailed',
      'unknownPlatform',
      'unknownIp',
      'noDevices',
    ]

    for (const key of keys) {
      expect(dict.zh.settings.devices).toHaveProperty(key)
      expect(dict.en.settings.devices).toHaveProperty(key)
      expect(dict.zh.settings.devices[key as keyof typeof dict.zh.settings.devices]).toBeTruthy()
      expect(dict.en.settings.devices[key as keyof typeof dict.en.settings.devices]).toBeTruthy()
    }
  })
})
