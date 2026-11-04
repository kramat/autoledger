<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type GroupTotals, type PeriodReport, type ReportGroup, type Totals, type Trends } from '../api'
import ChartBox from '../components/ChartBox.vue'
import { fmtDate, fmtMonth, isoDate, km, money, num } from '../format'
import { t, tn } from '../i18n'
import { state } from '../store'
import { useTheme } from '../theme'

const theme = useTheme()
const today = new Date()
const thisYear = today.getFullYear()

// The page has its own period: a calendar year by default (the year report), or a custom range.
const firstYear = computed(() => {
  const years = state.vehicles.map((v) => Number(v.start_date.slice(0, 4)))
  return Math.min(thisYear, ...years)
})
const years = computed(() => Array.from({ length: thisYear - firstYear.value + 1 }, (_, i) => thisYear - i))
const period = ref<string>(String(thisYear))
const customFrom = ref(`${thisYear}-01-01`)
const customTo = ref(isoDate(today))
const group = ref<ReportGroup>('month')
const report = ref<PeriodReport | null>(null)
const trends = ref<Trends | null>(null)
const error = ref('')
const groupView = ref<'chart' | 'table'>('chart')
const groupVehicle = ref<string>('') // '' = all vehicles combined

const range = computed(() => {
  if (period.value === 'custom') return { from: customFrom.value, to: customTo.value }
  const year = Number(period.value)
  return { from: `${year}-01-01`, to: year === thisYear ? isoDate(today) : `${year}-12-31` }
})
const params = computed(() => ({ ...range.value, group: group.value, vehicle_id: state.vehicleId || undefined }))

async function load(): Promise<void> {
  try {
    const [period_, trends_] = await Promise.all([
      api.reportPeriod(params.value),
      api.reportTrends({ vehicle_id: state.vehicleId || undefined }),
    ])
    report.value = period_
    trends.value = trends_
    error.value = ''
  } catch (err) {
    error.value = (err as Error).message
  }
}

watch(params, load, { immediate: true, deep: true })
watch(() => state.vehicleId, () => (groupVehicle.value = ''))

// --- Side by side ---------------------------------------------------------

interface Column {
  key: string
  name: string
  total: Totals
  perYear: PeriodReport['combined']['per_year']
}

const columns = computed<Column[]>(() => {
  const r = report.value
  if (!r) return []
  const cols = r.vehicles.map((v) => ({ key: v.vehicle.id, name: v.vehicle.name, total: v.total, perYear: v.per_year }))
  if (cols.length > 1) cols.push({ key: 'all', name: t('common.app.filters.allVehicles'), total: r.combined.total, perYear: r.combined.per_year })
  return cols
})

const perKm = (v: number | null | undefined) => (v == null ? '—' : `${money(v, 3)}/km`)
const pct = (v: number | null | undefined) => (v == null ? '—' : t('reports.sideBySide.percent', { value: num(v * 100) }))

// Consumption only means something per car, so the "All vehicles" column leaves it out.
const perCar = (format: (c: Column) => string) => (c: Column) => (c.key === 'all' ? '—' : format(c))
const amount = (cost: number, qty: number, unit: string) => (cost || qty ? `${money(cost)} · ${num(qty, 1)} ${unit}` : '—')

interface Row {
  id: string
  label: string
  value: (c: Column) => string
  has: (c: Column) => boolean
  strong?: boolean
}

const rows = computed<Row[]>(() => [
  { id: 'distance', label: t('reports.rows.distance'), value: (c) => km(c.total.km), has: (c) => c.total.km > 0 },
  { id: 'totalCost', label: t('reports.rows.totalCost'), value: (c) => money(c.total.total_cost), has: () => true, strong: true },
  { id: 'totalPerKm', label: t('reports.rows.totalPerKm'), value: (c) => perKm(c.total.total_cost_per_km), has: (c) => c.total.total_cost_per_km != null },
  { id: 'energyPerKm', label: t('reports.rows.energyPerKm'), value: (c) => perKm(c.total.energy_cost_per_km), has: (c) => c.total.energy_cost_per_km != null },
  { id: 'fuel', label: t('reports.rows.fuel'), value: (c) => amount(c.total.fuel_cost, c.total.fuel_l, 'L'), has: (c) => c.total.fuel_cost > 0 },
  { id: 'electricity', label: t('reports.rows.electricity'), value: (c) => amount(c.total.electricity_cost, c.total.electricity_kwh, 'kWh'), has: (c) => c.total.electricity_kwh > 0 },
  { id: 'maintenance', label: t('reports.rows.maintenance'), value: (c) => money(c.total.maintenance_cost), has: (c) => c.total.maintenance_cost > 0 },
  { id: 'otherCosts', label: t('reports.rows.otherCosts'), value: (c) => money(c.total.other_cost), has: (c) => c.total.other_cost > 0 },
  { id: 'depreciation', label: t('reports.rows.depreciation'), value: (c) => money(c.total.depreciation_cost), has: (c) => c.total.depreciation_cost > 0 },
  { id: 'fuelConsumption', label: t('reports.rows.fuelConsumption'), value: perCar((c) => (c.total.fuel_l_per_100km == null ? '—' : `${num(c.total.fuel_l_per_100km, 1)} L/100 km`)), has: (c) => c.total.fuel_l_per_100km != null },
  { id: 'electricConsumption', label: t('reports.rows.electricConsumption'), value: perCar((c) => (c.total.kwh_per_100km == null ? '—' : `${num(c.total.kwh_per_100km, 1)} kWh/100 km`)), has: (c) => c.total.kwh_per_100km != null },
  { id: 'electricShare', label: t('reports.rows.electricShare'), value: perCar((c) => pct(c.total.electric_share)), has: (c) => c.total.electric_share != null },
  { id: 'idle', label: t('reports.rows.idle'), value: (c) => money(c.total.idle_cost), has: (c) => c.total.idle_cost >= 0.01 },
  { id: 'trips', label: t('reports.rows.trips'), value: (c) => num(c.total.trip_count), has: (c) => c.total.trip_count > 0 },
  { id: 'refuels', label: t('reports.rows.refuels'), value: (c) => num(c.total.refuel_count), has: (c) => c.total.refuel_count > 0 },
  { id: 'charges', label: t('reports.rows.charges'), value: (c) => num(c.total.charge_count), has: (c) => c.total.charge_count > 0 },
  { id: 'maintenanceEntries', label: t('reports.rows.maintenanceEntries'), value: (c) => num(c.total.maintenance_count), has: (c) => c.total.maintenance_count > 0 },
  { id: 'perYearKm', label: t('reports.rows.perYearKm'), value: (c) => km(c.perYear.km), has: (c) => c.perYear.km != null },
  { id: 'perYearTotalCost', label: t('reports.rows.perYearTotalCost'), value: (c) => money(c.perYear.total_cost), has: (c) => c.perYear.total_cost != null },
  { id: 'perYearMaintenance', label: t('reports.rows.perYearMaintenance'), value: (c) => money(c.perYear.maintenance_cost), has: (c) => c.perYear.maintenance_cost != null },
])
const visibleRows = computed(() => rows.value.filter((r) => columns.value.some((c) => r.has(c))))

// --- Per group ------------------------------------------------------------

const groups = computed<GroupTotals[]>(() => {
  const r = report.value
  if (!r) return []
  const vehicle = r.vehicles.find((v) => v.vehicle.id === groupVehicle.value)
  return vehicle ? vehicle.groups : r.vehicles.length === 1 ? r.vehicles[0].groups : r.combined.groups
})
const hasElectricity = computed(() => groups.value.some((g) => g.electricity_cost > 0))
const hasDepreciation = computed(() => groups.value.some((g) => g.depreciation_cost > 0))
const groupLabel = (g: GroupTotals) => (report.value?.group === 'month' ? fmtMonth(g.label) : g.label)

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
  return { backgroundColor: th.surface, borderColor: th.axis, textStyle: { color: th.text } }
}

/** "month", "quarter", … as used in "Cost per {unit}". */
function groupUnit(group: ReportGroup): string {
  const units = {
    month: t('reports.groups.units.month'),
    quarter: t('reports.groups.units.quarter'),
    year: t('reports.groups.units.year'),
    none: t('reports.groups.units.none'),
  }
  return units[group]
}

const costOption = computed(() => {
  const th = theme.value
  const data = groups.value
  // Fixed category -> color slot, the same as on the overview.
  const categories = [
    { key: 'fuel_cost', name: t('reports.categories.fuel'), color: th.series[0] },
    { key: 'electricity_cost', name: t('reports.categories.electricity'), color: th.series[1] },
    { key: 'maintenance_cost', name: t('reports.categories.maintenance'), color: th.series[2] },
    // Four colors only: depreciation shares the "Other" bar (the table shows it apart).
    {
      key: 'other_cost',
      name: hasDepreciation.value ? t('reports.categories.otherDepreciation') : t('reports.categories.other'),
      color: th.series[3],
    },
  ] as const
  const max = Math.max(0, ...data.map((g) => g.total_cost))
  const totalLabel = (amount: number) => t('reports.groups.tooltipTotal', { amount: `<b>${money(amount)}</b>` })
  return {
    animation: false,
    grid: { left: 8, right: 8, top: 36, bottom: 4, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: th.text2 } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(128,128,128,0.08)' } },
      ...tooltipStyle(),
      formatter: (items: { dataIndex: number; marker: string; seriesName: string; value: number }[]) => {
        const g = data[items[0].dataIndex]
        const lines = items.map((i) => `${i.marker} ${i.seriesName}: <b>${money(i.value)}</b>`)
        return [`<b>${groupLabel(g)}</b>`, ...lines, totalLabel(g.total_cost), `${km(g.km)}`].join('<br>')
      },
    },
    xAxis: { type: 'category', data: data.map(groupLabel), ...axisStyle(), splitLine: { show: false } },
    yAxis: {
      type: 'value', ...axisStyle(), axisLine: { show: false },
      axisLabel: { color: th.muted, formatter: (v: number) => money(v, max < 10 ? 2 : 0) },
    },
    series: categories
      .filter((c) => c.key !== 'electricity_cost' || hasElectricity.value)
      .map((c) => ({
        name: c.name,
        type: 'bar',
        stack: 'cost',
        barMaxWidth: 24,
        data: data.map((g) => Math.round((g[c.key] + (c.key === 'other_cost' ? g.depreciation_cost : 0)) * 100) / 100),
        itemStyle: { color: c.color, borderColor: th.surface, borderWidth: 2 },
        emphasis: { focus: 'series' },
      })),
  }
})

// --- Trends ---------------------------------------------------------------

// A vehicle keeps its color whatever is filtered: the slot follows its place in the vehicle list.
function vehicleColor(id: string): string {
  const index = Math.max(0, state.vehicles.findIndex((v) => v.id === id))
  return theme.value.series[index % theme.value.series.length]
}

type TrendKey = 'total_cost_per_km' | 'fuel_l_per_100km' | 'kwh_per_100km'

const trendMonths = computed(() => {
  const all = new Set<string>()
  for (const v of trends.value?.vehicles ?? []) for (const m of v.monthly) all.add(m.month)
  return [...all].sort()
})

function hasTrend(key: TrendKey): boolean {
  return (trends.value?.vehicles ?? []).some((v) => v.monthly.some((m) => m[key] != null))
}

function trendOption(key: TrendKey, format: (v: number) => string) {
  const th = theme.value
  const months = trendMonths.value
  const vehicles = (trends.value?.vehicles ?? []).filter((v) => v.monthly.some((m) => m[key] != null))
  return {
    animation: false,
    grid: { left: 8, right: 16, top: vehicles.length > 1 ? 36 : 12, bottom: 4, containLabel: true },
    legend: vehicles.length > 1
      ? { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 10, textStyle: { color: th.text2 } }
      : { show: false },
    tooltip: {
      trigger: 'axis',
      ...tooltipStyle(),
      formatter: (items: { dataIndex: number; marker: string; seriesName: string; value: number | null }[]) =>
        [`<b>${fmtMonth(months[items[0].dataIndex])}</b>`,
          ...items.map((i) => `${i.marker} ${i.seriesName}: <b>${i.value == null ? '—' : format(i.value)}</b>`)].join('<br>'),
    },
    xAxis: { type: 'category', data: months.map(fmtMonth), ...axisStyle(), splitLine: { show: false } },
    yAxis: { type: 'value', ...axisStyle(), axisLine: { show: false }, axisLabel: { color: th.muted, formatter: format } },
    series: vehicles.map((v) => {
      const byMonth = new Map(v.monthly.map((m) => [m.month, m[key]]))
      const color = vehicleColor(v.vehicle.id)
      return {
        name: v.vehicle.name,
        type: 'line',
        data: months.map((m) => byMonth.get(m) ?? null),
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 2, color, cap: 'round', join: 'round' },
        itemStyle: { color, borderColor: th.surface, borderWidth: 2 },
      }
    }),
  }
}

const seasonNames = computed(() => ({
  winter: t('reports.seasons.winter'),
  spring: t('reports.seasons.spring'),
  summer: t('reports.seasons.summer'),
  autumn: t('reports.seasons.autumn'),
}))
const seasonVehicles = computed(() =>
  (trends.value?.vehicles ?? []).filter((v) =>
    Object.values(v.seasons).some((s) => s.kwh_per_100km != null || s.fuel_l_per_100km != null),
  ),
)

const exportParams = computed(() => params.value)
</script>

<template>
  <div class="stack">
    <div class="page-head">
      <h2>{{ t('common.nav.reports') }}</h2>
      <div class="actions report-controls">
        <label class="sr-only" for="report-period">{{ t('common.app.filters.period') }}</label>
        <select id="report-period" v-model="period">
          <option v-for="y in years" :key="y" :value="String(y)">{{ y === thisYear ? t('reports.controls.yearSoFar', { year: y }) : y }}</option>
          <option value="custom">{{ t('common.presets.custom') }}</option>
        </select>
        <template v-if="period === 'custom'">
          <input type="date" v-model="customFrom" :aria-label="t('common.app.filters.from')" />
          <input type="date" v-model="customTo" :aria-label="t('common.app.filters.to')" />
        </template>
        <label class="sr-only" for="report-group">{{ t('reports.controls.group') }}</label>
        <select id="report-group" v-model="group">
          <option value="month">{{ t('reports.controls.perMonth') }}</option>
          <option value="quarter">{{ t('reports.controls.perQuarter') }}</option>
          <option value="year">{{ t('reports.controls.perYear') }}</option>
        </select>
        <a :href="api.reportExportUrl('xlsx', exportParams)" download><button>{{ t('reports.controls.exportXlsx') }}</button></a>
        <a :href="api.reportExportUrl('csv', exportParams)" download><button>{{ t('reports.controls.exportCsv') }}</button></a>
      </div>
    </div>
    <p v-if="error" class="notice error">{{ error }}</p>

    <template v-if="report">
      <section class="card">
        <h2>{{ fmtDate(report.from) }} – {{ fmtDate(report.to) }}</h2>
        <p class="small muted" style="margin: 4px 0 12px">
          <template v-if="columns.length > 2">{{ t('reports.sideBySide.intro') }} </template>
          {{ tn('reports.sideBySide.perYearNote', report.days, { n: num(report.days) }) }}
        </p>
        <div class="table-wrap">
          <table class="matrix">
            <thead>
              <tr>
                <th scope="col"><span class="sr-only">{{ t('reports.sideBySide.figure') }}</span></th>
                <th v-for="c in columns" :key="c.key" class="num" scope="col">{{ c.name }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in visibleRows" :key="r.id">
                <th scope="row" class="row-label">{{ r.label }}</th>
                <td v-for="c in columns" :key="c.key" class="num">
                  <b v-if="r.strong">{{ r.value(c) }}</b><template v-else>{{ r.value(c) }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card">
        <div class="page-head" style="margin-bottom: 8px">
          <h2>{{ t('reports.groups.title', { unit: groupUnit(report.group) }) }}</h2>
          <div class="actions">
            <select v-if="report.vehicles.length > 1" v-model="groupVehicle" :aria-label="t('common.app.filters.vehicle')">
              <option value="">{{ t('common.app.filters.allVehicles') }}</option>
              <option v-for="v in report.vehicles" :key="v.vehicle.id" :value="v.vehicle.id">{{ v.vehicle.name }}</option>
            </select>
            <div class="segmented" role="group" :aria-label="t('reports.groups.display')">
              <button :class="{ on: groupView === 'chart' }" :aria-pressed="groupView === 'chart'" @click="groupView = 'chart'">{{ t('reports.groups.chart') }}</button>
              <button :class="{ on: groupView === 'table' }" :aria-pressed="groupView === 'table'" @click="groupView = 'table'">{{ t('reports.groups.table') }}</button>
            </div>
          </div>
        </div>
        <ChartBox v-if="groupView === 'chart'" :option="costOption" :height="280"
          :label="t('reports.groups.chartLabel', { unit: groupUnit(report.group) })" />
        <div v-else class="table-wrap">
          <table class="matrix">
            <thead>
              <tr>
                <th scope="col">{{ t('common.app.filters.period') }}</th><th class="num" scope="col">{{ t('reports.table.km') }}</th>
                <th class="num" scope="col">{{ t('reports.table.fuel') }}</th>
                <th v-if="hasElectricity" class="num" scope="col">{{ t('reports.table.electricity') }}</th>
                <th class="num" scope="col">{{ t('reports.table.maintenance') }}</th><th class="num" scope="col">{{ t('reports.table.other') }}</th>
                <th v-if="hasDepreciation" class="num" scope="col">{{ t('reports.table.depreciation') }}</th>
                <th class="num" scope="col">{{ t('reports.table.total') }}</th><th class="num" scope="col">{{ t('reports.table.perKm') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in groups" :key="g.label">
                <td>{{ groupLabel(g) }}</td><td class="num">{{ num(g.km) }}</td><td class="num">{{ money(g.fuel_cost) }}</td>
                <td v-if="hasElectricity" class="num">{{ money(g.electricity_cost) }}</td>
                <td class="num">{{ money(g.maintenance_cost) }}</td><td class="num">{{ money(g.other_cost) }}</td>
                <td v-if="hasDepreciation" class="num">{{ money(g.depreciation_cost) }}</td>
                <td class="num">{{ money(g.total_cost) }}</td>
                <td class="num">{{ g.total_cost_per_km == null ? '—' : money(g.total_cost_per_km, 3) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <section v-if="trends && trendMonths.length" class="card">
      <h2>{{ t('reports.trends.title') }}</h2>
      <p class="small muted" style="margin: 4px 0 8px">{{ t('reports.trends.intro') }}</p>
      <h3 class="small muted" style="margin: 8px 0 4px">{{ t('reports.trends.costPerKm') }}</h3>
      <ChartBox v-if="hasTrend('total_cost_per_km')" :option="trendOption('total_cost_per_km', (v) => money(v, 2))"
        :height="220" :label="t('reports.trends.costPerKmLabel')" />
      <template v-if="hasTrend('fuel_l_per_100km')">
        <h3 class="small muted" style="margin: 16px 0 4px">{{ t('reports.trends.fuel') }}</h3>
        <ChartBox :option="trendOption('fuel_l_per_100km', (v) => num(v, 1))" :height="200"
          :label="t('reports.trends.fuelLabel')" />
      </template>
      <template v-if="hasTrend('kwh_per_100km')">
        <h3 class="small muted" style="margin: 16px 0 4px">{{ t('reports.trends.electric') }}</h3>
        <ChartBox :option="trendOption('kwh_per_100km', (v) => num(v, 1))" :height="200"
          :label="t('reports.trends.electricLabel')" />
      </template>

      <template v-if="seasonVehicles.length">
        <h3 style="margin: 20px 0 4px">{{ t('reports.seasons.title') }}</h3>
        <p class="small muted" style="margin: 0 0 8px">{{ t('reports.seasons.intro') }}</p>
        <div class="table-wrap">
          <table class="matrix">
            <thead>
              <tr>
                <th scope="col">{{ t('reports.seasons.season') }}</th>
                <template v-for="v in seasonVehicles" :key="v.vehicle.id">
                  <th v-if="v.vehicle.type !== 'BEV'" class="num" scope="col">{{ v.vehicle.name }} L/100 km</th>
                  <th v-if="v.vehicle.type !== 'ICE'" class="num" scope="col">{{ v.vehicle.name }} kWh/100 km</th>
                </template>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(name, key) in seasonNames" :key="key">
                <td>{{ name }}</td>
                <template v-for="v in seasonVehicles" :key="v.vehicle.id">
                  <td v-if="v.vehicle.type !== 'BEV'" class="num">{{ num(v.seasons[key].fuel_l_per_100km, 1) }}</td>
                  <td v-if="v.vehicle.type !== 'ICE'" class="num">{{ num(v.seasons[key].kwh_per_100km, 1) }}</td>
                </template>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.report-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.row-label {
  text-align: left;
  font-weight: normal;
  color: var(--text-2);
  white-space: nowrap;
}
</style>
