export interface LocalAvatar {
  id: string
  dataUrl: string
  createdAt: string
}

const MAX_LOCAL_AVATARS = 20
const AVATAR_LIBRARY_PREFIX = 'layover_lens_local_avatars_'
const CURRENT_AVATAR_PREFIX = 'layover_lens_current_local_avatar_'
export const AVATAR_UPDATED_EVENT = 'layover-lens:avatar-updated'

function libraryKey(userId: string) {
  return `${AVATAR_LIBRARY_PREFIX}${userId}`
}

function currentKey(userId: string) {
  return `${CURRENT_AVATAR_PREFIX}${userId}`
}

function emitAvatarUpdated(userId: string) {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(AVATAR_UPDATED_EVENT, { detail: { userId } }))
}

export function getLocalAvatars(userId: string): LocalAvatar[] {
  const raw = localStorage.getItem(libraryKey(userId))
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as LocalAvatar[]
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item) => (
      typeof item.id === 'string'
      && typeof item.dataUrl === 'string'
      && item.dataUrl.startsWith('data:image/')
      && typeof item.createdAt === 'string'
    ))
  } catch {
    return []
  }
}

function saveLocalAvatars(userId: string, avatars: LocalAvatar[]) {
  localStorage.setItem(libraryKey(userId), JSON.stringify(avatars))
}

export function addLocalAvatar(userId: string, dataUrl: string): LocalAvatar {
  const avatar: LocalAvatar = {
    id: typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `avatar_${Date.now()}`,
    dataUrl,
    createdAt: new Date().toISOString(),
  }
  const avatars = [...getLocalAvatars(userId), avatar].slice(-MAX_LOCAL_AVATARS)
  saveLocalAvatars(userId, avatars)
  return avatar
}

export function getCurrentLocalAvatar(userId: string): LocalAvatar | null {
  const currentId = localStorage.getItem(currentKey(userId))
  if (!currentId) return null
  return getLocalAvatars(userId).find((avatar) => avatar.id === currentId) || null
}

export function setCurrentLocalAvatarId(userId: string, avatarId: string): void {
  localStorage.setItem(currentKey(userId), avatarId)
  emitAvatarUpdated(userId)
}

export function clearCurrentLocalAvatar(userId: string): void {
  localStorage.removeItem(currentKey(userId))
  emitAvatarUpdated(userId)
}
