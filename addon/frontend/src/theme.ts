// Chart colors come from the CSS custom properties, re-read when the OS theme flips.

import { onBeforeUnmount, ref } from 'vue'

export interface ThemeColors {
  surface: string
  text: string
  text2: string
  muted: string
  grid: string
  axis: string
  series: [string, string, string, string]
}

function read(): ThemeColors {
  const css = getComputedStyle(document.documentElement)
  const v = (name: string) => css.getPropertyValue(name).trim()
  return {
    surface: v('--surface'),
    text: v('--text'),
    text2: v('--text-2'),
    muted: v('--muted'),
    grid: v('--grid'),
    axis: v('--axis'),
    series: [v('--series-1'), v('--series-2'), v('--series-3'), v('--series-4')],
  }
}

export function useTheme() {
  const colors = ref<ThemeColors>(read())
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const update = () => (colors.value = read())
  media.addEventListener('change', update)
  onBeforeUnmount(() => media.removeEventListener('change', update))
  return colors
}
