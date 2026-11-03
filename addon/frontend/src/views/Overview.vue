<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type MonthTotals, type ScheduleDue, type Summary, type Trip, type VehicleSummary } from '../api'
import ChartBox from '../components/ChartBox.vue'
import { fmtDate, fmtDateTime, fmtMonth, km, money, num } from '../format'
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

function tripRoute(t: Trip): string {
  const from = t.start_address ?? t.start_zone ?? '?'
  return t.kind === 'round_trip' ? `round trip from ${t.start_zone ?? from}` : `${from} → ${t.end_address ?? t.end_zone ?? '?'}`
}

function dueText(item: ScheduleDue): string {
  const parts = []
  if (item.estimated_date) parts.push(`${item.days_left != null && item.days_left < 0 ? 'was due' : 'due'} ${fmtDate(item.estimated_date)}`)
  if (item.km_left != null) parts.push(item.km_left >= 0 ? `${km(item.km_left)} left` : `${km(-item.km_left)} over`)
  return parts.join(' · ')
}

function distanceNote(v: VehicleSummary): string | null {
  const known = v.period.distance_known_until
  if (!known || !summary.value) return null
  // Only worth a note when more than a day of the period is missing.
  const periodEnd = Math.min(new Date(`${summary.value.to}T23:59:59`).getTime(), Date.now())
  if (new Date(known).getTime() >= periodEnd - 24 * 3600 * 1000) return null
  return `Distance is known up to ${fmtDate(known)}. Add an odometer reading or a refuel with odometer for later km.`
}

// Fixed category → color slot, so a category keeps its color whatever is shown.
const categories = computed(() => {
  const all = [
    { key: 'fuel_cost', name: 'Fuel', color: theme.value.series[0] },
    { key: 'electricity_cost', name: 'Electricity', color: theme.value.series[1] },
    { key: 'maintenance_cost', name: 'Maintenance', color: theme.value.series[2] },
    { key: 'other_cost', name: 'Other', color: theme.value.series[3] },
  ] as const
  return all.filter((c) => c.key !== 'electricity_cost' || hasElectricity.value)
})

function axisStyle() {
  const t = theme.value
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.muted },
    splitLine: { lineStyle: { color: t.grid } },
  }
}

function tooltipStyle() {
  const t = theme.value
  return {
    backgroundColor: t.surface,
    borderColor: t.axis,
    textStyle: { color: t.text },
  }
}

const costOption = computed(() => {
  const t = theme.value
  const months = monthly.value
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 36, bottom: 4, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: t.text2 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(128,128,128,0.08)' } },
      ...tooltipStyle(),
      formatter: (items: { dataIndex: number; marker: string; seriesName: string; value: number }[]) => {
        const m = months[items[0].dataIndex]
        const rows = items.map((i) => `${i.marker} ${i.seriesName}: <b>${money(i.value)}</b>`)
        return [`<b>${fmtMonth(m.month)}</b>`, ...rows, `Total: <b>${money(m.total_cost)}</b>`].join('<br>')
      },
    },
    xAxis: { type: 'category', data: months.map((m) => fmtMonth(m.month)), ...axisStyle(), splitLine: { show: false } },
    yAxis: {
      type: 'value', ...axisStyle(), axisLine: { show: false },
      // Small amounts (a first month with only trips) need cents, or every tick reads "€ 1".
      axisLabel: { color: t.muted, formatter: (v: number) => money(v, Math.max(...months.map((m) => m.total_cost)) < 10 ? 2 : 0) },
    },
    series: categories.value.map((c) => ({
      name: c.name,
      type: 'bar',
      stack: 'cost',
      barMaxWidth: 28,
      data: months.map((m) => Math.round(m[c.key] * 100) / 100),
      itemStyle: { color: c.color, borderColor: t.surface, borderWidth: 1 },
      emphasis: { focus: 'series' },
    })),
  }
})

const kmOption = computed(() => {
  const t = theme.value
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
    yAxis: { type: 'value', ...axisStyle(), axisLine: { show: false }, axisLabel: { color: t.muted, formatter: (v: number) => num(v) } },
    series: [
      {
        name: 'Distance',
        type: 'bar',
        barMaxWidth: 28,
        data: months.map((m) => Math.round(m.km)),
        itemStyle: { color: t.series[0], borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
})
</script>

<template>
  <div class="stack">
    <p v-if="error" class="notice error">{{ error }}</p>

    <div v-if="!state.vehicles.length" class="card empty">
      <h2>Welcome to AutoLedger</h2>
      <p>Add your first vehicle to start tracking refuels, maintenance and costs.</p>
      <router-link :to="{ path: '/vehicles', query: { new: '1' } }"><button class="primary">Add vehicle</button></router-link>
    </div>

    <template v-else-if="summary">
      <p class="muted small">{{ fmtDate(summary.from) }} – {{ fmtDate(summary.to) }}</p>
      <router-link v-if="summary.review_count" :to="{ path: '/review', query: $route.query }" class="notice"
        style="display: block; text-decoration: none">
        {{ summary.review_count }} {{ summary.review_count === 1 ? 'item needs' : 'items need' }} your input in Review.
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
              <div class="label">Distance</div>
              <div class="value">{{ km(v.period.km) }}</div>
              <div class="sub">Odometer {{ km(v.odometer_km) }}</div>
            </div>
            <div class="stat">
              <div class="label">Total cost</div>
              <div class="value">{{ money(v.period.total_cost) }}</div>
              <div class="sub">{{ v.period.total_cost_per_km == null ? '—' : `${money(v.period.total_cost_per_km, 3)} / km` }}</div>
            </div>
            <div class="stat" v-if="v.vehicle.type !== 'BEV'">
              <div class="label">Fuel</div>
              <div class="value">{{ money(v.period.fuel_cost) }}</div>
              <div class="sub">{{ num(v.period.fuel_l, 1) }} L<template v-if="v.period.fuel_l_per_100km != null"> · {{ num(v.period.fuel_l_per_100km, 1) }} L/100 km</template></div>
            </div>
            <div class="stat" v-if="v.vehicle.type !== 'ICE'">
              <div class="label">Electricity</div>
              <div class="value">{{ money(v.period.electricity_cost) }}</div>
              <div v-if="v.trips_since" class="sub">
                {{ num(v.period.electricity_kwh, 1) }} kWh used<template v-if="v.period.kwh_per_100km != null"> ·
                {{ num(v.period.kwh_per_100km, 1) }} kWh/100 km</template>
              </div>
              <div v-else class="sub">{{ num(v.period.electricity_kwh, 1) }} kWh · {{ v.period.charge_count }} charges</div>
            </div>
            <div class="stat">
              <div class="label">Maintenance</div>
              <div class="value">{{ money(v.period.maintenance_cost) }}</div>
              <div class="sub">{{ v.period.maintenance_count }} entries</div>
            </div>
            <div class="stat">
              <div class="label">Other costs</div>
              <div class="value">{{ money(v.period.other_cost) }}</div>
              <div class="sub">Insurance, tax, parking…</div>
            </div>
          </div>
          <p class="small muted" style="margin: 14px 0 0">
            Last 12 months: {{ km(v.rolling_12m.km) }}
            · {{ v.rolling_12m.total_cost_per_km == null ? '—' : money(v.rolling_12m.total_cost_per_km, 3) }} / km total
            · {{ v.rolling_12m.energy_cost_per_km == null ? '—' : money(v.rolling_12m.energy_cost_per_km, 3) }} / km energy
            <template v-if="v.rolling_12m.fuel_l_per_100km != null"> · {{ num(v.rolling_12m.fuel_l_per_100km, 1) }} L/100 km</template>
            <template v-if="v.rolling_12m.electric_share != null"> · {{ num(v.rolling_12m.electric_share * 100) }} % of km electric (estimate)</template>
          </p>
          <p v-if="v.last_trip" class="small" style="margin: 8px 0 0">
            Last trip {{ fmtDateTime(v.last_trip.end_ts) }}:
            <router-link :to="{ path: '/trips', query: $route.query }">{{ tripRoute(v.last_trip) }}</router-link>,
            {{ num(v.last_trip.distance_km, 1) }} km for {{ money(v.last_trip.costing?.cost) }}
          </p>
          <p v-if="v.period.idle_cost >= 0.01" class="small muted" style="margin: 4px 0 0">
            Climate &amp; standby: {{ num(v.period.idle_kwh, 1) }} kWh<template v-if="v.period.idle_fuel_l"> and
            {{ num(v.period.idle_fuel_l, 1) }} L</template> for {{ money(v.period.idle_cost) }} (in the energy cost, not in € per km)
          </p>
          <p v-if="v.open_charge" class="small" style="margin: 8px 0 0">
            <b>Charging now</b> since {{ fmtDateTime(v.open_charge.start_ts) }}: {{ num(v.open_charge.energy_kwh, 2) }} kWh,
            {{ money(v.open_charge.cost) }}
          </p>
          <p v-else-if="v.last_charge" class="small muted" style="margin: 4px 0 0">
            Last charge {{ fmtDate(v.last_charge.start_ts) }}: {{ num(v.last_charge.energy_kwh, 1) }} kWh for
            {{ money(v.last_charge.cost) }}
          </p>
          <p v-if="v.last_refuel" class="small muted" style="margin: 4px 0 0">
            Last refuel {{ fmtDate(v.last_refuel.ts) }}: {{ num(v.last_refuel.litres, 1) }} L for {{ money(v.last_refuel.total) }}
          </p>
          <p v-if="v.next_maintenance" class="small" style="margin: 8px 0 0">
            <span class="badge" :class="v.next_maintenance.status" style="margin-right: 6px">{{ DUE_STATUSES[v.next_maintenance.status] }}</span>
            <router-link :to="{ path: '/maintenance', query: $route.query }">{{ v.next_maintenance.name }}</router-link>
            {{ dueText(v.next_maintenance) }}
          </p>
          <p v-if="distanceNote(v)" class="small" style="margin: 8px 0 0">{{ distanceNote(v) }}</p>
          <p v-if="v.odometer_points_ignored" class="small" style="margin: 8px 0 0">
            {{ v.odometer_points_ignored }} odometer value(s) are lower than an earlier one and were ignored. Check the Fuel page.
          </p>
        </section>

        <section v-if="showCombined" class="card">
          <h2>All vehicles</h2>
          <div class="stats">
            <div class="stat"><div class="label">Distance</div><div class="value">{{ km(summary.combined.period.km) }}</div></div>
            <div class="stat"><div class="label">Total cost</div><div class="value">{{ money(summary.combined.period.total_cost) }}</div>
              <div class="sub">{{ summary.combined.period.total_cost_per_km == null ? '—' : `${money(summary.combined.period.total_cost_per_km, 3)} / km` }}</div></div>
            <div class="stat"><div class="label">Energy</div><div class="value">{{ money(summary.combined.period.energy_cost) }}</div></div>
            <div class="stat"><div class="label">Maintenance</div><div class="value">{{ money(summary.combined.period.maintenance_cost) }}</div></div>
            <div class="stat"><div class="label">Other costs</div><div class="value">{{ money(summary.combined.period.other_cost) }}</div></div>
          </div>
        </section>
      </div>

      <section class="card">
        <div class="page-head" style="margin-bottom: 8px">
          <h2>Last 12 months{{ state.vehicleId ? '' : ' · all vehicles' }}</h2>
          <div class="segmented" role="group" aria-label="Display">
            <button :class="{ on: view === 'chart' }" :aria-pressed="view === 'chart'" @click="view = 'chart'">Chart</button>
            <button :class="{ on: view === 'table' }" :aria-pressed="view === 'table'" @click="view = 'table'">Table</button>
          </div>
        </div>
        <template v-if="view === 'chart'">
          <h3 class="small muted" style="margin: 8px 0 4px">Cost per month</h3>
          <ChartBox :option="costOption" :height="280" label="Stacked bar chart of cost per month by category" />
          <h3 class="small muted" style="margin: 16px 0 4px">Distance per month</h3>
          <ChartBox :option="kmOption" :height="200" label="Bar chart of km driven per month" />
        </template>
        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Month</th><th class="num" scope="col">km</th><th class="num" scope="col">Fuel</th>
                <th v-if="hasElectricity" class="num" scope="col">Electricity</th>
                <th class="num" scope="col">Maintenance</th><th class="num" scope="col">Other</th>
                <th class="num" scope="col">Total</th><th class="num" scope="col">Per km</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in monthly" :key="m.month">
                <td>{{ fmtMonth(m.month) }}</td><td class="num">{{ num(m.km) }}</td><td class="num">{{ money(m.fuel_cost) }}</td>
                <td v-if="hasElectricity" class="num">{{ money(m.electricity_cost) }}</td>
                <td class="num">{{ money(m.maintenance_cost) }}</td><td class="num">{{ money(m.other_cost) }}</td>
                <td class="num">{{ money(m.total_cost) }}</td>
                <td class="num">{{ m.total_cost_per_km == null ? '—' : money(m.total_cost_per_km, 3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="small muted" style="margin: 10px 0 0">
          Cars with recorded trips count fuel and electricity when they are used. Other cars count fuel in the month you
          bought it, so single months can be uneven; the 12-month figures above smooth this out.
        </p>
      </section>
    </template>
  </div>
</template>
