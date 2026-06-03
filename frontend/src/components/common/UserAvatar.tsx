import { useEffect, useMemo, useState } from 'react'
import type { UserProfile } from '../../types'
import { getMaterialAvatarUrl } from '../../icons/materialAvatars'
import { AVATAR_UPDATED_EVENT, getCurrentLocalAvatar } from '../../services/avatarStorage'

interface UserAvatarProps {
  user: UserProfile | null
  size?: number
  className?: string
}

function avatarInitial(user: UserProfile | null) {
  return (user?.nickname || user?.username || user?.email || '?')[0].toUpperCase()
}

function getRemoteAvatarUrl(avatarUrl: string | null | undefined) {
  if (!avatarUrl) return null
  if (avatarUrl.startsWith('material:')) {
    return getMaterialAvatarUrl(avatarUrl.slice('material:'.length)) || null
  }
  return avatarUrl
}

export default function UserAvatar({ user, size = 64, className }: UserAvatarProps) {
  const [version, setVersion] = useState(0)

  useEffect(() => {
    const handleUpdate = () => setVersion((value) => value + 1)
    window.addEventListener(AVATAR_UPDATED_EVENT, handleUpdate)
    return () => window.removeEventListener(AVATAR_UPDATED_EVENT, handleUpdate)
  }, [])

  const src = useMemo(() => {
    if (!user) return null
    const localAvatar = getCurrentLocalAvatar(user.id)
    return localAvatar?.dataUrl || getRemoteAvatarUrl(user.avatar_url)
  }, [user, version])

  const style = {
    width: `${size}px`,
    height: `${size}px`,
  }

  if (src) {
    return (
      <img
        className={className}
        src={src}
        alt=""
        style={style}
      />
    )
  }

  return (
    <span className={className} style={style}>
      {avatarInitial(user)}
    </span>
  )
}
