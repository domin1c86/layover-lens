import { beforeEach, describe, expect, it } from 'vitest'
import {
  addLocalAvatar,
  clearCurrentLocalAvatar,
  getCurrentLocalAvatar,
  getLocalAvatars,
  setCurrentLocalAvatarId,
} from './avatarStorage'

describe('avatarStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('keeps local uploaded avatars isolated by user id', () => {
    const userOneAvatar = addLocalAvatar('user_one', 'data:image/png;base64,one')
    addLocalAvatar('user_two', 'data:image/png;base64,two')

    expect(getLocalAvatars('user_one')).toEqual([userOneAvatar])
    expect(getLocalAvatars('user_two')).toHaveLength(1)
    expect(getLocalAvatars('user_missing')).toEqual([])
  })

  it('stores the current local avatar selection separately from the library', () => {
    const avatar = addLocalAvatar('user_one', 'data:image/png;base64,one')

    expect(getCurrentLocalAvatar('user_one')).toBeNull()

    setCurrentLocalAvatarId('user_one', avatar.id)
    expect(getCurrentLocalAvatar('user_one')).toEqual(avatar)

    clearCurrentLocalAvatar('user_one')
    expect(getCurrentLocalAvatar('user_one')).toBeNull()
  })

  it('keeps only the latest 20 local uploaded avatars', () => {
    for (let index = 0; index < 21; index += 1) {
      addLocalAvatar('user_one', `data:image/png;base64,${index}`)
    }

    const avatars = getLocalAvatars('user_one')
    expect(avatars).toHaveLength(20)
    expect(avatars[0].dataUrl).toBe('data:image/png;base64,1')
    expect(avatars[19].dataUrl).toBe('data:image/png;base64,20')
  })
})
