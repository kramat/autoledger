<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  api, type CarService, type MaintenanceRecord, type MaintenanceSchedule, type ScheduleDue, type VehicleDue,
} from '../api'
import DataTable, { type Column } from '../components/DataTable.vue'
import { clip } from '../attachments'
import RecordDialog from '../components/RecordDialog.vue'
import { defaultVehicleId, vehicleField, type Field } from '../components/fields'
import { fmtDate, isoDate, km, money, num } from '../format'
import { t, tn } from '../i18n'
import { DUE_STATUSES, label, MAINTENANCE_CATEGORIES } from '../labels'
import { activeVehicles, state, vehicleName } from '../store'
import { useCrud } from '../useCrud'

const params = () => ({ vehicle_id: state.vehicleId || undefined })
const due = ref<VehicleDue[]>([])

async function loadDue(): Promise<void> {
  due.value = (await api.maintenanceDue(params())).vehicles
}

const crud = useCrud<MaintenanceRecord>('maintenance', params, {
  noun: () => t('maintenance.nouns.entry'),
  // A logged entry can move a schedule forward.
  afterChange: async () => {
    await Promise.all([loadDue(), schedules.load()])
  },
})
const schedules = useCrud<MaintenanceSchedule>('maintenance-schedules', params, {
  noun: () => t('maintenance.nouns.schedule'),
  afterChange: loadDue,
})
watch(params, () => loadDue().catch(() => undefined), { immediate: true, deep: true })

const scheduleName = (id: string | null) => schedules.items.value.find((s) => s.id === id)?.name ?? ''

const columns = computed<Column<MaintenanceRecord>[]>(() => [
  { key: 'date', label: t('maintenance.columns.date'), value: (r) => fmtDate(r.date) },
  ...(!state.vehicleId
    ? [{ key: 'vehicle', label: t('maintenance.columns.vehicle'), value: (r: MaintenanceRecord) => vehicleName(r.vehicle_id) }]
    : []),
  { key: 'category', label: t('maintenance.columns.category'), value: (r) => label(MAINTENANCE_CATEGORIES, r.category) },
  { key: 'description', label: t('maintenance.columns.description'), wrap: true, value: (r) => r.description },
  { key: 'schedule', label: t('maintenance.columns.schedule'), wrap: true, value: (r) => scheduleName(r.schedule_id) },
  { key: 'garage', label: t('maintenance.columns.garage'), wrap: true, value: (r) => r.garage ?? '' },
  { key: 'invoice', label: t('maintenance.columns.invoice'), value: clip },
  { key: 'odometer', label: t('maintenance.columns.odometer'), num: true, value: (r) => km(r.odometer_km) },
  { key: 'cost', label: t('maintenance.columns.cost'), num: true, value: (r) => money(r.cost) },
])

const scheduleOptions = computed(() => [
  { value: null, label: t('maintenance.fields.scheduleAutomatic') },
  ...schedules.items.value
    .filter((s) => s.active)
    .map((s) => ({ value: s.id, label: activeVehicles.value.length > 1 ? `${vehicleName(s.vehicle_id)} · ${s.name}` : s.name })),
])

const fields = computed<Field[]>(() => [
  vehicleField(),
  { key: 'date', label: t('maintenance.fields.date'), type: 'date', required: true, half: true },
  {
    key: 'category', label: t('maintenance.fields.category'), type: 'select', options: MAINTENANCE_CATEGORIES,
    required: true, half: true,
  },
  {
    key: 'description', label: t('maintenance.fields.description'), type: 'text', required: true,
    placeholder: t('maintenance.fields.descriptionPlaceholder'),
  },
  { key: 'odometer_km', label: t('maintenance.fields.odometer'), type: 'number', min: 0, half: true },
  { key: 'cost', label: t('maintenance.fields.cost'), type: 'number', min: 0, half: true },
  {
    key: 'schedule_id', label: t('maintenance.fields.schedule'), type: 'select', options: scheduleOptions.value,
    hint: t('maintenance.fields.scheduleHint'),
  },
  { key: 'garage', label: t('maintenance.fields.garage'), type: 'text' },
  { key: 'note', label: t('maintenance.fields.note'), type: 'textarea' },
])

const scheduleFields = computed<Field[]>(() => [
  vehicleField(),
  {
    key: 'name', label: t('maintenance.scheduleFields.name'), type: 'text', required: true,
    placeholder: t('maintenance.scheduleFields.namePlaceholder'),
  },
  {
    key: 'category', label: t('maintenance.scheduleFields.category'), type: 'select',
    options: [{ value: null, label: t('maintenance.scheduleFields.categoryNone') }, ...MAINTENANCE_CATEGORIES],
    hint: t('maintenance.scheduleFields.categoryHint'),
  },
  {
    key: 'interval_months', label: t('maintenance.scheduleFields.intervalMonths'), type: 'number', min: 1, step: '1',
    half: true,
  },
  { key: 'interval_km', label: t('maintenance.scheduleFields.intervalKm'), type: 'number', min: 0, half: true },
  { key: 'last_done_date', label: t('maintenance.scheduleFields.lastDoneDate'), type: 'date', half: true },
  { key: 'last_done_km', label: t('maintenance.scheduleFields.lastDoneKm'), type: 'number', min: 0, half: true },
  {
    key: 'remind_before_days', label: t('maintenance.scheduleFields.remindDays'), type: 'number', min: 0, step: '1',
    half: true,
  },
  { key: 'remind_before_km', label: t('maintenance.scheduleFields.remindKm'), type: 'number', min: 0, half: true },
  { key: 'active', label: t('maintenance.scheduleFields.active'), type: 'checkbox' },
  { key: 'note', label: t('maintenance.scheduleFields.note'), type: 'textarea' },
])

const total = computed(() => crud.items.value.reduce((sum, r) => sum + r.cost, 0))

function add(initial: Record<string, unknown> = {}): void {
  crud.openCreate({ vehicle_id: defaultVehicleId(), date: isoDate(new Date()), category: 'service', cost: 0, ...initial })
}

function addSchedule(): void {
  schedules.openCreate({
    vehicle_id: defaultVehicleId(), category: 'service', interval_months: 12, remind_before_days: 30,
    remind_before_km: 1000, active: true,
  })
}

function logDone(vehicle: VehicleDue, item: VehicleDue['items'][number]): void {
  // A connected car's odometer is current; a manual car's last value can be weeks old.
  const collector = state.vehicles.find((v) => v.id === vehicle.vehicle_id)?.tracking === 'collector'
  add({
    vehicle_id: vehicle.vehicle_id, category: item.category ?? 'other', description: item.name,
    schedule_id: item.schedule_id, odometer_km: collector ? vehicle.odometer_km : null,
  })
}

function every(item: { interval_months: number | null; interval_km: number | null }): string {
  const parts: string[] = []
  if (item.interval_months) {
    parts.push(item.interval_months === 12
      ? t('maintenance.every.year')
      : tn('maintenance.every.months', item.interval_months))
  }
  if (item.interval_km) parts.push(t('maintenance.every.km', { n: num(item.interval_km) }))
  return parts.length === 2 ? t('maintenance.every.or', { a: parts[0], b: parts[1] }) : parts.join('')
}

function when(item: ScheduleDue): string {
  if (item.status === 'unknown') return t('maintenance.when.unknown')
  const parts = []
  if (item.estimated_date) {
    const days = item.days_left ?? 0
    const relative = days === 0
      ? t('maintenance.when.today')
      : days > 0
        ? tn('maintenance.when.inDays', days, { n: num(days) })
        : tn('maintenance.when.daysAgo', -days, { n: num(-days) })
    const key = item.reason === 'km' ? 'maintenance.when.dateEstimated' : 'maintenance.when.date'
    parts.push(t(key, { date: fmtDate(item.estimated_date), relative }))
  }
  if (item.km_left != null) {
    parts.push(item.km_left >= 0
      ? t('maintenance.when.kmLeft', { km: km(item.km_left) })
      : t('maintenance.when.kmOver', { km: km(-item.km_left) }))
  }
  return parts.join(' · ')
}

/** What the car itself says about its next service. */
function carService(service: CarService): string {
  let byDate = ''
  if (service.due_date) {
    const days = service.days_to_service
    const date = fmtDate(service.due_date)
    byDate = days == null
      ? t('maintenance.carService.around', { date })
      : t('maintenance.carService.byDate', { date, days: tn('maintenance.carService.days', days, { n: num(days) }) })
  }
  let byKm = ''
  if (service.distance_to_service != null) {
    const distance = km(service.distance_to_service)
    byKm = service.due_km != null
      ? t('maintenance.carService.byKmAt', { distance, odometer: km(service.due_km) })
      : t('maintenance.carService.byKm', { distance })
  }
  const whenText = byDate && byKm ? t('maintenance.carService.or', { a: byDate, b: byKm }) : byDate || byKm
  return t('maintenance.carService.text', { when: whenText, date: fmtDate(service.reported_at) })
}

function editSchedule(id: string): void {
  const schedule = schedules.items.value.find((s) => s.id === id)
  if (schedule) schedules.openEdit(schedule)
}

function removeSchedule(id: string): void {
  const schedule = schedules.items.value.find((s) => s.id === id)
  if (schedule) schedules.remove(schedule)
}

const inactive = computed(() => schedules.items.value.filter((s) => !s.active))
</script>

<template>
  <div class="stack">
    <section class="card">
      <div class="page-head">
        <h2>{{ t('maintenance.schedules.title') }}</h2>
        <div class="actions">
          <button :disabled="!activeVehicles.length" @click="addSchedule">{{ t('maintenance.schedules.add') }}</button>
        </div>
      </div>
      <p v-if="schedules.error.value" class="notice error">{{ schedules.error.value }}</p>
      <template v-for="v in due" :key="v.vehicle_id">
        <h3 v-if="!state.vehicleId && due.length > 1" class="small muted" style="margin: 12px 0 4px">{{ v.vehicle_name }}</h3>
        <div v-if="v.items.length" class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th scope="col">{{ t('maintenance.schedules.columns.schedule') }}</th>
                <th scope="col">{{ t('maintenance.schedules.columns.status') }}</th>
                <th scope="col">{{ t('maintenance.schedules.columns.nextDue') }}</th>
                <th scope="col">{{ t('maintenance.schedules.columns.lastDone') }}</th>
                <th><span class="sr-only">{{ t('common.actions.actions') }}</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in v.items" :key="item.schedule_id">
                <td class="wrap"><b>{{ item.name }}</b><br /><span class="small muted">{{ every(item) }}</span></td>
                <td :data-label="t('maintenance.schedules.columns.status')">
                  <span class="badge" :class="item.status">{{ DUE_STATUSES[item.status] }}</span>
                </td>
                <td class="wrap" :data-label="t('maintenance.schedules.columns.nextDue')">{{ when(item) }}</td>
                <td class="wrap" :data-label="t('maintenance.schedules.columns.lastDone')">
                  {{ item.last_done_date ? fmtDate(item.last_done_date) : '—' }}<template v-if="item.last_done_km != null">
                    · {{ km(item.last_done_km) }}</template>
                </td>
                <td class="row-actions">
                  <button class="link" @click="logDone(v, item)">{{ t('maintenance.schedules.logDone') }}</button>
                  <button class="link" @click="editSchedule(item.schedule_id)">{{ t('common.actions.edit') }}</button>
                  <button class="link danger" @click="removeSchedule(item.schedule_id)">{{ t('common.actions.delete') }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="v.car_service" class="small muted" style="margin: 8px 0 0">{{ carService(v.car_service) }}</p>
        <p v-if="v.items.length && v.km_per_day != null" class="small muted" style="margin: 4px 0 0">
          {{ t('maintenance.schedules.kmPerDay', { n: num(v.km_per_day) }) }}
        </p>
      </template>
      <div v-if="!due.some((v) => v.items.length)" class="empty">{{ t('maintenance.schedules.empty') }}</div>
      <p v-if="inactive.length" class="small muted" style="margin: 8px 0 0">
        {{ t('maintenance.schedules.paused') }} <template v-for="(s, i) in inactive" :key="s.id"><button class="link"
            @click="schedules.openEdit(s)">{{ s.name }}</button><template v-if="i < inactive.length - 1">, </template></template>
      </p>
    </section>

    <section>
      <div class="page-head">
        <h2>{{ t('maintenance.log.title') }}</h2>
        <div class="actions">
          <a :href="api.exportUrl('maintenance', params())" download><button>{{ t('maintenance.log.exportCsv') }}</button></a>
          <button class="primary" :disabled="!activeVehicles.length" @click="add()">{{ t('maintenance.log.add') }}</button>
        </div>
      </div>
      <p v-if="crud.error.value" class="notice error">{{ crud.error.value }}</p>
      <DataTable :columns="columns" :rows="crud.items.value" :loading="crud.loading.value"
        :empty="t('maintenance.log.empty')" @edit="crud.openEdit" @delete="crud.remove">
        <template v-if="crud.items.value.length" #foot>
          <tr>
            <td :colspan="columns.length - 1">
              {{ tn('maintenance.log.count', crud.items.value.length, { n: num(crud.items.value.length) }) }}
            </td>
            <td class="num">{{ money(total) }}</td>
            <td></td>
          </tr>
        </template>
      </DataTable>
    </section>

    <RecordDialog v-if="crud.dialog.value"
      :title="crud.dialog.value.mode === 'create' ? t('maintenance.dialogs.addEntry') : t('maintenance.dialogs.editEntry')"
      :fields="fields" :initial="crud.dialog.value.initial" :mode="crud.dialog.value.mode" :save="crud.save"
      attachments="maintenance" @changed="crud.load" @close="crud.dialog.value = null" />
    <RecordDialog v-if="schedules.dialog.value"
      :title="schedules.dialog.value.mode === 'create'
        ? t('maintenance.dialogs.addSchedule') : t('maintenance.dialogs.editSchedule')"
      :fields="scheduleFields" :initial="schedules.dialog.value.initial" :mode="schedules.dialog.value.mode"
      :save="schedules.save" @close="schedules.dialog.value = null" />
  </div>
</template>
