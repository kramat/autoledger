<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type MonthTotals, type ScheduleDue, type Summary, type Trip, type VehicleSummary } from '../api'
import ChartBox from '../components/ChartBox.vue'
import { fmtDate, fmtDateTime, fmtMonth, km, money, num } from '../format'
import { t, tn } from '../i18n'
import { DUE_STATUSES, label, VEHICLE_TYPES } from '../labels'
import { periodRange, state } from '../store'
import { useTheme } from '../theme'

const summary = ref<Summary | null>(null)
const error = ref('')
const view = ref<'chart' | 'table'>('chart')
const theme = useTheme()

async function load(): Promise<void> {
  const { from, to } = periodRange()
  try {
    summary.value = await api.summary({ from, to, vehicle_id: state.vehicleId || undefined })
    state.reviewCount = summary.value.review_count
    error.value = ''
  } catch (err) {
    error.value = (err as Error).message
  }
}

watch(() => [state.vehicleId, state.preset, state.customFrom, state.customTo, state.vehicles.length], load, {
  immediate: true,
})

const showCombined = computed(() => !state.vehicleId && (summary.value?.vehicles.length ?? 0) > 1)
const monthly = computed<MonthTotals[]>(() => {
  if (!summary.value) return []
  return state.vehicleId ? (summary.value.vehicles[0]?.monthly ?? []) : summary.value.combined.monthly
})
const hasElectricity = computed(() => monthly.value.some((m) => m.electricity_cost > 0))
const hasDepreciation = computed(() => monthly.value.some((m) => m.depreciation_cost > 0))

function tripRoute(trip: Trip): string {
  const from = trip.start_address ?? trip.start_zone ?? '?'
  return trip.kind === 'round_trip'
    ? t('overview.lastTrip.roundTrip', { place: trip.start_zone ?? from })
    : `${from} → ${trip.end_address ?? trip.end_zone ?? '?'}`
}

function dueText(item: ScheduleDue): string {
  const parts = []
  if (item.estimated_date) {
    const date = fmtDate(item.estimated_date)
    parts.push(item.days_left != null && item.days_left < 0 ? t('overview.due.wasDue', { date }) : t('overview.due.due', { date }))
  }
  if (item.km_left != null) {
    parts.push(item.km_left >= 0 ? t('overview.due.kmLeft', { km: km(item.km_left) }) : t('overview.due.kmOver', { km: km(-item.km_left) }))
  }
  return parts.join(' · ')
}

function distanceNote(v: VehicleSummary): string | null {
  const known = v.period.distance_known_until
  if (!known || !summary.value) return null
  // Only worth a note when more than a day of the period is missing.
  const periodEnd = Math.min(new Date(`${summary.value.to}T23:59:59`).getTime(), Date.now())
  if (new Date(known).getTime() >= periodEnd - 24 * 3600 * 1000) return null
  return t('overview.distanceKnownUntil', { date: fmtDate(known) })
}

// Fixed category → color slot, so a category keeps its color whatever is shown.
const categories = computed(() => {
  const all = [
    { key: 'fuel_cost', name: t('overview.categories.fuel'), color: theme.value.series[0] },
    { key: 'electricity_cost', name: t('overview.categories.electricity'), color: theme.value.series[1] },
    { key: 'maintenance_cost', name: t('overview.categories.maintenance'), color: theme.value.series[2] },
    // Four colors only: depreciation shares the "Other" bar (tables show it apart).
    {
      key: 'other_cost',
      name: hasDepreciation.value ? t('overview.categories.otherDepreciation') : t('overview.categories.other'),
      color: theme.value.series[3],
    },
  ] as const
  return all.filter((c) => c.key !== 'electricity_cost' || hasElectricity.value)
})

function axisStyle() {
  const th = theme.value
  return {
    axisLine: { lineStyle: { color: th.axis } },
    axisTick: { show: false },
    axisLabel: { color: th.muted },
    splitLine: { lineStyle: { color: th.grid } },
  }
}

function tooltipStyle() {
  const th = theme.value
  return {
    backgroundColor: th.surface,
    borderColor: th.axis,
    textStyle: { color: th.text },
  }
}

const costOption = computed(() => {
  const th = theme.value
  const months = monthly.value
  const totalLabel = (amount: number) => t('overview.monthly.tooltipTotal', { amount: `<b>${money(amount)}</b>` })
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 36, bottom: 4, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: th.text2 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(128,128,128,0.08)' } },
      ...tooltipStyle(),
      formatter: (items: { dataIndex: number; marker: string; seriesName: string; value: number }[]) => {
        const m = months[items[0].dataIndex]
        const rows = items.map((i) => `${i.marker} ${i.seriesName}: <b>${money(i.value)}</b>`)
        return [`<b>${fmtMonth(m.month)}</b>`, ...rows, totalLabel(m.total_cost)].join('<br>')
      },
    },
    xAxis: { type: 'category', data: months.map((m) => fmtMonth(m.month)), ...axisStyle(), splitLine: { show: false } },
    yAxis: {
      type: 'value', ...axisStyle(), axisLine: { show: false },
      // Small amounts (a first month with only trips) need cents, or every tick reads "€ 1".
      axisLabel: { color: th.muted, formatter: (v: number) => money(v, Math.max(...months.map((m) => m.total_cost)) < 10 ? 2 : 0) },
    },
    series: categories.value.map((c) => ({
      name: c.name,
      type: 'bar',
      stack: 'cost',
      barMaxWidth: 28,
      data: months.map((m) => Math.round((m[c.key] + (c.key === 'other_cost' ? m.depreciation_cost : 0)) * 100) / 100),
      itemStyle: { color: c.color, borderColor: th.surface, borderWidth: 1 },
      emphasis: { focus: 'series' },
    })),
  }
})

const kmOption = computed(() => {
  const th = theme.value
  const months = monthly.value
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 12, bottom: 4, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(128,128,128,0.08)' } },
      ...tooltipStyle(),
      formatter: (items: { dataIndex: number }[]) => {
        const m = months[items[0].dataIndex]
        return `<b>${fmtMonth(m.month)}</b><br>${km(m.km)}`
      },
    },
    xAxis: { type: 'category', data: months.map((m) => fmtMonth(m.month)), ...axisStyle(), splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle(), axisLine: { show: false }, axisLabel: { color: th.muted, formatter: (v: number) => num(v) } },
    series: [
      {
        name: t('overview.stats.distance'),
        type: 'bar',
        barMaxWidth: 28,
        data: months.map((m) => Math.round(m.km)),
        itemStyle: { color: th.series[0], borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})
</script>

<template>
  <div class="stack">
    <p v-if="error" class="notice error">{{ error }}</p>

    <div v-if="!state.vehicles.length" class="card empty">
      <h2>{{ t('overview.welcome.title') }}</h2>
      <p>{{ t('overview.welcome.text') }}</p>
      <router-link :to="{ path: '/vehicles', query: { new: '1' } }"><button class="primary">{{ t('overview.welcome.addVehicle') }}</button></router-link>
    </div>

    <template v-else-if="summary">
      <p class="muted small">{{ fmtDate(summary.from) }} – {{ fmtDate(summary.to) }}</p>
      <router-link v-if="summary.review_count" :to="{ path: '/review', query: $route.query }" class="notice"
        style="display: block; text-decoration: none">
        {{ tn('overview.reviewNotice', summary.review_count) }}
      </router-link>

      <div class="grid cols-2">
        <section v-for="v in summary.vehicles" :key="v.vehicle.id" class="card">
          <div class="vehicle-head">
            <h2>
              <span class="swatch" :style="{ background: v.vehicle.color ?? 'var(--series-1)' }" />{{ v.vehicle.name }}
            </h2>
            <span class="muted small">
              {{ label(VEHICLE_TYPES, v.vehicle.type) }}<template v-if="v.vehicle.plate"> · {{ v.vehicle.plate }}</template>
            </span>
          </div>
          <div class="stats">
            <div class="stat">
              <div class="label">{{ t('overview.stats.distance') }}</div>
              <div class="value">{{ km(v.period.km) }}</div>
              <div class="sub">{{ t('overview.stats.odometer', { km: km(v.odometer_km) }) }}</div>
            </div>
            <div class="stat">
              <div class="label">{{ t('overview.stats.totalCost') }}</div>
              <div class="value">{{ money(v.period.total_cost) }}</div>
              <div class="sub">{{ v.period.total_cost_per_km == null ? '—' : t('overview.stats.perKm', { amount: money(v.period.total_cost_per_km, 3) }) }}</div>
            </div>
            <div class="stat" v-if="v.vehicle.type !== 'BEV'">
              <div class="label">{{ t('overview.stats.fuel') }}</div>
              <div class="value">{{ money(v.period.fuel_cost) }}</div>
              <div class="sub">{{ num(v.period.fuel_l, 1) }} L<template v-if="v.period.fuel_l_per_100km != null"> · {{ num(v.period.fuel_l_per_100km, 1) }} L/100 km</template></div>
            </div>
            <div class="stat" v-if="v.vehicle.type !== 'ICE'">
              <div class="label">{{ t('overview.stats.electricity') }}</div>
              <div class="value">{{ money(v.period.electricity_cost) }}</div>
              <div v-if="v.trips_since" class="sub">
                {{ t('overview.stats.kwhUsed', { kwh: num(v.period.electricity_kwh, 1) }) }}<template v-if="v.period.kwh_per_100km != null"> ·
                {{ num(v.period.kwh_per_100km, 1) }} kWh/100 km</template>
              </div>
              <div v-else class="sub">
                {{ num(v.period.electricity_kwh, 1) }} kWh · {{ tn('overview.stats.charges', v.period.charge_count, { n: num(v.period.charge_count) }) }}
              </div>
            </div>
            <div class="stat">
              <div class="label">{{ t('overview.stats.maintenance') }}</div>
              <div class="value">{{ money(v.period.maintenance_cost) }}</div>
              <div class="sub">{{ tn('overview.stats.entries', v.period.maintenance_count, { n: num(v.period.maintenance_count) }) }}</div>
            </div>
            <div class="stat">
              <div class="label">{{ t('overview.stats.otherCosts') }}</div>
              <div class="value">{{ money(v.period.other_cost) }}</div>
              <div class="sub">{{ t('overview.stats.otherHint') }}</div>
            </div>
            <div v-if="v.period.depreciation_cost > 0" class="stat">
              <div class="label">{{ t('overview.stats.depreciation') }}</div>
              <div class="value">{{ money(v.period.depreciation_cost) }}</div>
              <div class="sub">{{ t('overview.stats.depreciationHint') }}</div>
            </div>
          </div>
          <p class="small muted" style="margin: 14px 0 0">
            {{ t('overview.rolling.distance', { km: km(v.rolling_12m.km) }) }}
            · {{ v.rolling_12m.total_cost_per_km == null ? '—' : t('overview.rolling.totalPerKm', { amount: money(v.rolling_12m.total_cost_per_km, 3) }) }}
            · {{ v.rolling_12m.energy_cost_per_km == null ? '—' : t('overview.rolling.energyPerKm', { amount: money(v.rolling_12m.energy_cost_per_km, 3) }) }}
            <template v-if="v.rolling_12m.fuel_l_per_100km != null"> · {{ num(v.rolling_12m.fuel_l_per_100km, 1) }} L/100 km</template>
            <template v-if="v.rolling_12m.electric_share != null"> · {{ t('overview.rolling.electricShare', { pct: num(v.rolling_12m.electric_share * 100) }) }}</template>
          </p>
          <p v-if="v.last_trip" class="small" style="margin: 8px 0 0">
            {{ t('overview.lastTrip.label', { date: fmtDateTime(v.last_trip.end_ts) }) }}
            <router-link :to="{ path: '/trips', query: $route.query }">{{ tripRoute(v.last_trip) }}</router-link>,
            {{ t('overview.lastTrip.detail', { distance: num(v.last_trip.distance_km, 1), cost: money(v.last_trip.costing?.cost) }) }}
          </p>
          <p v-if="v.period.idle_cost >= 0.01" class="small muted" style="margin: 4px 0 0">
            <template v-if="v.period.idle_fuel_l">
              {{ t('overview.idle.withFuel', { kwh: num(v.period.idle_kwh, 1), litres: num(v.period.idle_fuel_l, 1), cost: money(v.period.idle_cost) }) }}
            </template>
            <template v-else>
              {{ t('overview.idle.electric', { kwh: num(v.period.idle_kwh, 1), cost: money(v.period.idle_cost) }) }}
            </template>
          </p>
          <p v-if="v.open_charge" class="small" style="margin: 8px 0 0">
            <b>{{ t('overview.charging.now') }}</b>
            {{ t('overview.charging.since', { date: fmtDateTime(v.open_charge.start_ts), kwh: num(v.open_charge.energy_kwh, 2), cost: money(v.open_charge.cost) }) }}
          </p>
          <p v-else-if="v.last_charge" class="small muted" style="margin: 4px 0 0">
            {{ t('overview.charging.last', { date: fmtDate(v.last_charge.start_ts), kwh: num(v.last_charge.energy_kwh, 1), cost: money(v.last_charge.cost) }) }}
          </p>
          <p v-if="v.last_refuel" class="small muted" style="margin: 4px 0 0">
            {{ t('overview.lastRefuel', { date: fmtDate(v.last_refuel.ts), litres: num(v.last_refuel.litres, 1), cost: money(v.last_refuel.total) }) }}
          </p>
          <p v-if="v.next_maintenance" class="small" style="margin: 8px 0 0">
            <span class="badge" :class="v.next_maintenance.status" style="margin-right: 6px">{{ DUE_STATUSES[v.next_maintenance.status] }}</span>
            <router-link :to="{ path: '/maintenance', query: $route.query }">{{ v.next_maintenance.name }}</router-link>
            {{ dueText(v.next_maintenance) }}
          </p>
          <p v-if="distanceNote(v)" class="small" style="margin: 8px 0 0">{{ distanceNote(v) }}</p>
          <p v-if="v.odometer_points_ignored" class="small" style="margin: 8px 0 0">
            {{ tn('overview.odometerIgnored', v.odometer_points_ignored) }}
          </p>
        </section>

        <section v-if="showCombined" class="card">
          <h2>{{ t('common.app.filters.allVehicles') }}</h2>
          <div class="stats">
            <div class="stat"><div class="label">{{ t('overview.stats.distance') }}</div><div class="value">{{ km(summary.combined.period.km) }}</div></div>
            <div class="stat"><div class="label">{{ t('overview.stats.totalCost') }}</div><div class="value">{{ money(summary.combined.period.total_cost) }}</div>
              <div class="sub">{{ summary.combined.period.total_cost_per_km == null ? '—' : t('overview.stats.perKm', { amount: money(summary.combined.period.total_cost_per_km, 3) }) }}</div></div>
            <div class="stat"><div class="label">{{ t('overview.stats.energy') }}</div><div class="value">{{ money(summary.combined.period.energy_cost) }}</div></div>
            <div class="stat"><div class="label">{{ t('overview.stats.maintenance') }}</div><div class="value">{{ money(summary.combined.period.maintenance_cost) }}</div></div>
            <div class="stat"><div class="label">{{ t('overview.stats.otherCosts') }}</div><div class="value">{{ money(summary.combined.period.other_cost) }}</div></div>
            <div v-if="summary.combined.period.depreciation_cost > 0" class="stat"><div class="label">{{ t('overview.stats.depreciation') }}</div><div class="value">{{ money(summary.combined.period.depreciation_cost) }}</div></div>
          </div>
        </section>
      </div>

      <section class="card">
        <div class="page-head" style="margin-bottom: 8px">
          <h2>{{ state.vehicleId ? t('overview.monthly.title') : t('overview.monthly.titleAll') }}</h2>
          <div class="segmented" role="group" :aria-label="t('overview.monthly.display')">
            <button :class="{ on: view === 'chart' }" :aria-pressed="view === 'chart'" @click="view = 'chart'">{{ t('overview.monthly.chart') }}</button>
            <button :class="{ on: view === 'table' }" :aria-pressed="view === 'table'" @click="view = 'table'">{{ t('overview.monthly.table') }}</button>
          </div>
        </div>
        <template v-if="view === 'chart'">
          <h3 class="small muted" style="margin: 8px 0 4px">{{ t('overview.monthly.costPerMonth') }}</h3>
          <ChartBox :option="costOption" :height="280" :label="t('overview.monthly.costChartLabel')" />
          <h3 class="small muted" style="margin: 16px 0 4px">{{ t('overview.monthly.distancePerMonth') }}</h3>
          <ChartBox :option="kmOption" :height="200" :label="t('overview.monthly.distanceChartLabel')" />
        </template>
        <div v-else class="table-wrap">
          <table class="matrix">
            <thead>
              <tr>
                <th scope="col">{{ t('overview.table.month') }}</th><th class="num" scope="col">{{ t('overview.table.km') }}</th><th class="num" scope="col">{{ t('overview.table.fuel') }}</th>
                <th v-if="hasElectricity" class="num" scope="col">{{ t('overview.table.electricity') }}</th>
                <th class="num" scope="col">{{ t('overview.table.maintenance') }}</th><th class="num" scope="col">{{ t('overview.table.other') }}</th>
                <th v-if="hasDepreciation" class="num" scope="col">{{ t('overview.table.depreciation') }}</th>
                <th class="num" scope="col">{{ t('overview.table.total') }}</th><th class="num" scope="col">{{ t('overview.table.perKm') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in monthly" :key="m.month">
                <td>{{ fmtMonth(m.month) }}</td><td class="num">{{ num(m.km) }}</td><td class="num">{{ money(m.fuel_cost) }}</td>
                <td v-if="hasElectricity" class="num">{{ money(m.electricity_cost) }}</td>
                <td class="num">{{ money(m.maintenance_cost) }}</td><td class="num">{{ money(m.other_cost) }}</td>
                <td v-if="hasDepreciation" class="num">{{ money(m.depreciation_cost) }}</td>
                <td class="num">{{ money(m.total_cost) }}</td>
                <td class="num">{{ m.total_cost_per_km == null ? '—' : money(m.total_cost_per_km, 3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="small muted" style="margin: 10px 0 0">{{ t('overview.monthly.note') }}</p>
      </section>
    </template>
  </div>
</template>
