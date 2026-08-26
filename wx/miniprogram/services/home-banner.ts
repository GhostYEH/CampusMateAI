import type { HomeBanner } from './types'

export type HeroTheme = 'cpm' | 'learning' | 'academic' | 'study' | 'community'

export interface HeroSlide {
  id: string
  eyebrow: string
  title: string
  subtitle: string
  button: string
  route: string
  tab: boolean
  theme: HeroTheme
  image: string
}

interface Destination {
  route: string
  tab: boolean
  theme: HeroTheme
}

const DESTINATIONS: Record<string, Destination> = {
  CPM_ASSISTANT: { route: '/pages/counselor/counselor', tab: true, theme: 'cpm' },
  CHAOXING: { route: '/package-campus/pages/notices/notices', tab: false, theme: 'learning' },
  EDU_SYSTEM: { route: '/package-academic/pages/edu/edu', tab: false, theme: 'academic' },
  TASKS: { route: '/pages/tasks/tasks', tab: true, theme: 'study' },
  COMMUNITY: { route: '/package-community/pages/community/community', tab: false, theme: 'community' },
}

const THEME_FALLBACKS: Record<string, HeroTheme> = {
  INDIGO: 'cpm',
  CYAN: 'learning',
  VIOLET: 'academic',
  ORANGE: 'study',
  GREEN: 'community',
}

export function mapHomeBanner(banner: HomeBanner, resolveImage: (url: string) => string): HeroSlide {
  const destination = DESTINATIONS[banner.action_key]
  return {
    id: banner.id,
    eyebrow: banner.eyebrow,
    title: banner.title,
    subtitle: banner.subtitle,
    button: banner.cta_label,
    route: destination?.route || '',
    tab: destination?.tab || false,
    theme: destination?.theme || THEME_FALLBACKS[banner.theme_key] || 'cpm',
    image: resolveImage(banner.image_url),
  }
}
