<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from './api'
import { setCurrency } from './format'
import { t } from './i18n'
import {
  PRESETS,
  activeVehicles,
  dismissToast,
  loadReviewCount,
  loadSettings,
  loadVehicles,
  state,
  type Preset,
} from './store'

const route = useRoute()
const router = useRouter()
const ready = ref(false)

const tabs = [
  { to: '/', key: 'overview' },
  { to: '/trips', key: 'trips' },
  { to: '/fuel', key: 'fuel' },
  { to: '/charging', key: 'charging' },
  { to: '/maintenance', key: 'maintenance' },
  { to: '/costs', key: 'costs' },
  { to: '/reports', key: 'reports' },
  { to: '/review', key: 'review' },
  { to: '/vehicles', key: 'vehicles' },
  { to: '/settings', key: 'settings' },
] as const

// Vehicle and period live in the URL query, so deep links and reloads keep them.
function readQuery(): void {
  const q = route.query
  state.vehicleId = typeof q.v === 'string' ? q.v : ''
  state.preset = typeof q.p === 'string' && PRESETS.some((p) => p.value === q.p) ? (q.p as Preset) : 'this_month'
  if (typeof q.from === 'string') state.customFrom = q.from
  if (typeof q.to === 'string') state.customTo = q.to
}

// Links that change only the hash (no reload) must update the filters too.
watch(() => route.query, readQuery)

watch(
  () => [state.vehicleId, state.preset, state.customFrom, state.customTo],
  () => {
    const query: Record<string, string> = {}
    if (state.vehicleId) query.v = state.vehicleId
    if (state.preset !== 'this_month') query.p = state.preset
    if (state.preset === 'custom') Object.assign(query, { from: state.customFrom, to: state.customTo })
    router.replace({ query })
  },
)

watch(
  () => state.settings?.currency,
  (code) => code && setCurrency(code),
)

onMounted(async () => {
  await router.isReady()
  readQuery()
  try {
    await Promise.all([loadVehicles(), loadSettings(), loadReviewCount()])
  } catch (err) {
    state.loadError =
      err instanceof ApiError && err.status === 401
        ? t('common.app.openFromSidebar')
        : t('common.app.cannotReach', { error: (err as Error).message })
  }
  ready.value = true
  // New collector data (a detected refuel, a finished charge) can arrive at any time.
  reviewTimer = window.setInterval(() => loadReviewCount().catch(() => undefined), 60000)
})

let reviewTimer: number | undefined
onBeforeUnmount(() => window.clearInterval(reviewTimer))
</script>

<template>
  <header class="topbar">
    <div class="topbar-row">
      <h1 class="brand">AutoLedger</h1>
      <div class="filters" v-if="ready && !state.loadError">
        <label class="sr-only" for="vehicle-filter">{{ t('common.app.filters.vehicle') }}</label>
        <select id="vehicle-filter" v-model="state.vehicleId">
          <option value="">{{ t('common.app.filters.allVehicles') }}</option>
          <option v-for="v in activeVehicles" :key="v.id" :value="v.id">{{ v.name }}</option>
        </select>
        <label class="sr-only" for="period-filter">{{ t('common.app.filters.period') }}</label>
        <select id="period-filter" v-model="state.preset">
          <option v-for="p in PRESETS" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
        <template v-if="state.preset === 'custom'">
          <input type="date" v-model="state.customFrom" :aria-label="t('common.app.filters.from')" />
          <input type="date" v-model="state.customTo" :aria-label="t('common.app.filters.to')" />
        </template>
      </div>
    </div>
    <nav class="tabs" :aria-label="t('common.app.sections')">
      <router-link v-for="tab in tabs" :key="tab.to" :to="{ path: tab.to, query: route.query }" class="tab"
        :class="{ active: route.path === tab.to }">{{ t(`common.nav.${tab.key}`) }}<span v-if="tab.to === '/review' && state.reviewCount"
          class="count">{{ state.reviewCount }}</span></router-link>
    </nav>
  </header>

  <main class="page">
    <div v-if="!ready" class="muted">{{ t('common.actions.loading') }}</div>
    <div v-else-if="state.loadError" class="notice error">{{ state.loadError }}</div>
    <router-view v-else />
  </main>

  <div class="toasts" aria-live="polite">
    <div v-for="item in state.toasts" :key="item.id" class="toast">
      <span>{{ item.message }}</span>
      <button v-if="item.action" class="link" @click="item.action(); dismissToast(item.id)">{{ item.actionLabel }}</button>
      <button class="icon" :aria-label="t('common.actions.close')" @click="dismissToast(item.id)">×</button>
    </div>
  </div>
</template>
