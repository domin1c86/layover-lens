/**
 * Central icon registry for Layover Lens.
 *
 * All icons and emoji symbols used in the UI are defined in icons.json.
 * Components import the <Icon> component or getIcon() helper from this module
 * rather than hard-coding SVGs or emoji characters inline.
 *
 * To add / change an icon: edit icons.json, then reference it by its dot-path key
 * (e.g. "actions.close", "transport.flight").
 */
import { type FC, type SVGProps } from 'react'
import registry from './icons.json'

// ── types ───────────────────────────────────────────────────────────

export interface SvgIconDef {
  type: 'svg'
  viewBox: string
  paths?: string[]
  circle?: { cx: number; cy: number; r: number }
  label: string
}

export interface EmojiIconDef {
  type: 'emoji'
  value: string
  label: string
}

export type IconDef = SvgIconDef | EmojiIconDef

// ── registry access ─────────────────────────────────────────────────

/** Dot-path lookup: "actions.close" → IconDef */
export function getIcon(key: string): IconDef | undefined {
  const parts = key.split('.')
  let current: any = registry
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined
    current = current[part]
  }
  if (current && typeof current === 'object' && 'type' in current) {
    return current as IconDef
  }
  return undefined
}

// ── SVG renderer (no motion dependency — pure static icon) ──────────

const strokeDefaults: SVGProps<SVGSVGElement> = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export const SvgIcon: FC<{ def: SvgIconDef; size?: number; className?: string }> = ({
  def,
  size = 16,
  className,
}) => (
  <svg
    width={size}
    height={size}
    viewBox={def.viewBox}
    className={className}
    aria-label={def.label}
    {...strokeDefaults}
  >
    {def.paths?.map((d, i) => <path key={i} d={d} />)}
    {def.circle && <circle cx={def.circle.cx} cy={def.circle.cy} r={def.circle.r} />}
  </svg>
)

// ── main <Icon> component ───────────────────────────────────────────

interface IconProps {
  name: string // dot-path key, e.g. "theme.moon"
  size?: number
  className?: string
}

/**
 * Render an icon by its registry key.
 *
 * Usage:
 *   <Icon name="actions.search" size={16} />
 *   <Icon name="transport.flight" />
 */
export const Icon: FC<IconProps> = ({ name, size = 16, className }) => {
  const def = getIcon(name)
  if (!def) {
    console.warn(`[icons] Unknown icon key: "${name}"`)
    return null
  }
  if (def.type === 'svg') {
    return <SvgIcon def={def} size={size} className={className} />
  }
  return (
    <span className={className} role="img" aria-label={def.label}>
      {def.value}
    </span>
  )
}

// ── convenience exports for commonly used emoji icons ───────────────

/** Look up an emoji icon's character by key. Returns "" if not found. */
export function getEmoji(key: string): string {
  const def = getIcon(key)
  if (def && def.type === 'emoji') return def.value
  return ''
}
