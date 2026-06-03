export interface MaterialAvatar {
  id: string
  url: string
}

const modules = import.meta.glob('./materials/*.svg', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

export const materialAvatars: MaterialAvatar[] = Object.entries(modules)
  .map(([path, url]) => {
    const filename = path.split('/').pop() || ''
    const id = filename.replace(/\.svg$/i, '')
    return { id, url }
  })
  .filter((avatar) => avatar.id && avatar.id !== 'favicon')
  .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))

export function getMaterialAvatarUrl(id: string): string | undefined {
  return materialAvatars.find((avatar) => avatar.id === id)?.url
}
