<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from './api'
import { setCurrency } from './format'
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
  { to: '/', label: 'Overview' },
  { to: '/trips', label: 'Trips' },
  { to: '/fuel', label: 'Fuel' },
  { to: '/charging', label: 'Charging' },
  { to: '/maintenance', label: 'Maintenance' },
  { to: '/costs', label: 'Costs' },
  { to: '/reports', label: 'Reports' },
  { to: '/review', label: 'Review' },
  { to: '/vehicles', label: 'Vehicles' },
  { to: '/settings', label: 'Settings' },
]

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
        ? 'Open AutoLedger from the Home Assistant sidebar.'
        : `Could not reach the AutoLedger API: ${(err as Error).message}`
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
        <label class="sr-only" for="vehicle-filter">Vehicle</label>
        <select id="vehicle-filter" v-model="state.vehicleId">
          <option value="">All vehicles</option>
          <option v-for="v in activeVehicles" :key="v.id" :value="v.id">{{ v.name }}</option>
        </select>
        <label class="sr-only" for="period-filter">Period</label>
        <select id="period-filter" v-model="state.preset">
          <option v-for="p in PRESETS" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
        <template v-if="state.preset === 'custom'">
          <input type="date" v-model="state.customFrom" aria-label="From" />
          <input type="date" v-model="state.customTo" aria-label="To" />
        </template>
      </div>
    </div>
    <nav class="tabs" aria-label="Sections">
      <router-link v-for="t in tabs" :key="t.to" :to="{ path: t.to, query: route.query }" class="tab"
        :class="{ active: route.path === t.to }">{{ t.label }}<span v-if="t.to === '/review' && state.reviewCount"
          class="count">{{ state.reviewCount }}</span></router-link>
    </nav>
  </header>

  <main class="page">
    <div v-if="!ready" class="muted">Loading…</div>
    <div v-else-if="state.loadError" class="notice error">{{ state.loadError }}</div>
    <router-view v-else />
  </main>

  <div class="toasts" aria-live="polite">
    <div v-for="t in state.toasts" :key="t.id" class="toast">
      <span>{{ t.message }}</span>
      <button v-if="t.action" class="link" @click="t.action(); dismissToast(t.id)">{{ t.actionLabel }}</button>
      <button class="icon" aria-label="Dismiss" @click="dismissToast(t.id)">×</button>
    </div>
  </div>
</template>
