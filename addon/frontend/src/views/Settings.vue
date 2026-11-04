<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, ApiError, type Info, type Resource, type RestoreResult, type Settings } from '../api'
import ImportDialog from '../components/ImportDialog.vue'
import { fmtDateTime } from '../format'
import { setLanguagePreference, t, tn } from '../i18n'
import { LANGUAGES } from '../labels'
import { loadVehicles, state, toast } from '../store'

const initial: Settings = JSON.parse(JSON.stringify(state.settings))
// Older servers do not send a language yet.
const form = reactive<Settings>({ ...initial, language: initial.language ?? 'auto' })
const errors = ref<Record<string, string>>({})
const saving = ref(false)
const info = ref<Info | null>(null)
const token = ref('')
const tokenError = ref('')
const showToken = ref(false)
const confirmRegenerate = ref(false)

const exports = computed<{ resource: Resource; label: string }[]>(() => [
  { resource: 'vehicles', label: t('common.nav.vehicles') },
  { resource: 'refuels', label: t('settings.export.resources.refuels') },
  { resource: 'odometer-readings', label: t('settings.export.resources.odometerReadings') },
  { resource: 'charges', label: t('settings.export.resources.charges') },
  { resource: 'trips', label: t('common.nav.trips') },
  { resource: 'idle-records', label: t('settings.export.resources.idleRecords') },
  { resource: 'maintenance', label: t('common.nav.maintenance') },
  { resource: 'maintenance-schedules', label: t('settings.export.resources.maintenanceSchedules') },
  { resource: 'expenses', label: t('settings.export.resources.expenses') },
])

const importing = ref(false)
const restoreFile = ref<File | null>(null)
const restoreMode = ref<'empty' | 'merge'>('empty')
const restoreResult = ref<RestoreResult | null>(null)
const restoreError = ref('')
const restoring = ref(false)
const withFiles = ref(false)

function pickBackup(event: Event): void {
  restoreFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
  restoreResult.value = null
  restoreError.value = ''
}

async function restore(): Promise<void> {
  if (!restoreFile.value) return
  restoring.value = true
  restoreError.value = ''
  try {
    const data = JSON.parse(await restoreFile.value.text())
    restoreResult.value = await api.restoreBackup(data, restoreMode.value)
    await loadVehicles()
    toast(t('settings.restore.done'))
  } catch (err) {
    restoreError.value = err instanceof SyntaxError ? t('settings.restore.notJson') : (err as Error).message
  } finally {
    restoring.value = false
  }
}

function restoredCount(result: RestoreResult): number {
  return Object.values(result.tables).reduce((sum, table) => sum + table.inserted, 0)
}

function skippedCount(result: RestoreResult): number {
  return Object.values(result.tables).reduce((sum, table) => sum + table.skipped, 0)
}

function restoreSummary(result: RestoreResult): string {
  const parts = [tn('settings.restore.restored', restoredCount(result))]
  const skipped = skippedCount(result)
  if (skipped) parts.push(tn('settings.restore.skipped', skipped))
  const files = result.files?.written ?? 0
  if (files) parts.push(tn('settings.restore.files', files))
  return parts.join(' ')
}

async function save(): Promise<void> {
  saving.value = true
  errors.value = {}
  try {
    form.currency = form.currency.toUpperCase()
    state.settings = await api.saveSettings(form)
    setLanguagePreference(state.settings.language)
    toast(t('settings.toast.saved'))
  } catch (err) {
    if (err instanceof ApiError) errors.value = err.fields
    toast(t('settings.toast.notSaved', { error: (err as Error).message }))
  } finally {
    saving.value = false
  }
}

async function regenerate(): Promise<void> {
  if (!confirmRegenerate.value) {
    confirmRegenerate.value = true
    return
  }
  token.value = (await api.regenerateToken()).token
  confirmRegenerate.value = false
  showToken.value = true
  toast(t('settings.token.created'))
}

async function copyToken(): Promise<void> {
  await navigator.clipboard.writeText(token.value)
  toast(t('settings.token.copied'))
}

onMounted(async () => {
  info.value = await api.info()
  try {
    token.value = (await api.token()).token
  } catch (err) {
    tokenError.value = (err as Error).message
  }
})
</script>

<template>
  <div class="stack">
    <form class="card" @submit.prevent="save">
      <h2>{{ t('settings.general.title') }}</h2>
      <div class="form-grid">
        <label class="field half" :class="{ invalid: errors.language }">
          <span>{{ t('settings.general.language') }}</span>
          <select v-model="form.language">
            <option v-for="l in LANGUAGES" :key="String(l.value)" :value="l.value">{{ l.label }}</option>
          </select>
          <small v-if="errors.language" class="error">{{ errors.language }}</small>
        </label>
      </div>
      <h3 style="margin: 16px 0 8px">{{ t('settings.prices.title') }}</h3>
      <p class="small muted">{{ t('settings.prices.hint') }}</p>
      <div class="form-grid">
        <label class="field half" :class="{ invalid: errors.currency }">
          <span>{{ t('settings.prices.currency') }}</span>
          <input v-model="form.currency" maxlength="3" required />
          <small v-if="errors.currency" class="error">{{ errors.currency }}</small>
        </label>
        <label class="field half">
          <span>{{ t('settings.prices.electricity') }}</span>
          <input type="number" step="any" min="0" v-model.number="form.electricity_price" required />
        </label>
        <label class="field half">
          <span>{{ t('settings.prices.publicCharge') }}</span>
          <input type="number" step="any" min="0" v-model.number="form.public_charge_price" required />
        </label>
        <label class="field half">
          <span>{{ t('settings.prices.petrol') }}</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.petrol" required />
        </label>
        <label class="field half">
          <span>{{ t('settings.prices.diesel') }}</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.diesel" required />
        </label>
        <label class="field half">
          <span>{{ t('settings.prices.lpg') }}</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.lpg" required />
        </label>
      </div>
      <div class="dialog-actions">
        <button type="submit" class="primary" :disabled="saving">{{ t('common.actions.save') }}</button>
      </div>
    </form>

    <section class="card">
      <h2>{{ t('settings.export.title') }}</h2>
      <p class="small muted">{{ t('settings.export.hint') }}</p>
      <div class="button-row">
        <a :href="api.recordsWorkbookUrl()" download><button type="button" class="primary">{{ t('settings.export.workbook') }}</button></a>
        <a v-for="e in exports" :key="e.resource" :href="api.exportUrl(e.resource)" download>
          <button type="button">{{ e.label }}</button>
        </a>
      </div>
    </section>

    <section class="card">
      <h2>{{ t('settings.import.title') }}</h2>
      <p class="small muted">{{ t('settings.import.hint') }}</p>
      <div class="button-row">
        <button type="button" :disabled="!state.vehicles.length" @click="importing = true">{{ t('settings.import.button') }}</button>
      </div>
    </section>

    <section class="card">
      <h2>{{ t('settings.backup.title') }}</h2>
      <p class="small muted">{{ t('settings.backup.hint') }}</p>
      <label class="field checkbox" style="margin: 0 0 12px">
        <input v-model="withFiles" type="checkbox" />
        <span>{{ t('settings.backup.withFiles') }}<small class="hint checkbox-hint">{{ t('settings.backup.withFilesHint') }}</small></span>
      </label>
      <div class="button-row">
        <a :href="api.backupUrl(withFiles)" download><button type="button">{{ t('settings.backup.download') }}</button></a>
      </div>
      <h3 style="margin: 16px 0 8px">{{ t('settings.restore.title') }}</h3>
      <div class="form-grid" style="margin: 0 0 12px">
        <label class="field">
          <span>{{ t('settings.restore.file') }}</span>
          <input type="file" accept=".json,application/json" @change="pickBackup" />
        </label>
        <label class="field">
          <span>{{ t('settings.restore.mode') }}</span>
          <select v-model="restoreMode">
            <option value="empty">{{ t('settings.restore.modes.empty') }}</option>
            <option value="merge">{{ t('settings.restore.modes.merge') }}</option>
          </select>
        </label>
      </div>
      <p class="small muted" style="margin: 0 0 12px">{{ t('settings.restore.copyFirst') }}</p>
      <div class="button-row">
        <button type="button" class="primary" :disabled="!restoreFile || restoring" @click="restore">{{ t('settings.restore.button') }}</button>
      </div>
      <p v-if="restoreError" class="notice error" style="margin-top: 12px">{{ restoreError }}</p>
      <p v-if="restoreResult" class="notice" style="margin-top: 12px">{{ restoreSummary(restoreResult) }}</p>
    </section>

    <section class="card">
      <h2>{{ t('settings.token.title') }}</h2>
      <p class="small muted">{{ t('settings.token.hint') }}</p>
      <p v-if="tokenError" class="notice">{{ tokenError }}</p>
      <template v-else>
        <p><code>{{ showToken ? token : '•'.repeat(24) }}</code></p>
        <div style="display: flex; flex-wrap: wrap; gap: 8px">
          <button type="button" @click="showToken = !showToken">{{ showToken ? t('settings.token.hide') : t('settings.token.show') }}</button>
          <button type="button" @click="copyToken">{{ t('settings.token.copy') }}</button>
          <button type="button" class="danger" @click="regenerate">
            {{ confirmRegenerate ? t('settings.token.confirm') : t('settings.token.create') }}
          </button>
        </div>
      </template>
    </section>

    <section v-if="info" class="card">
      <h2>{{ t('settings.collector.title') }}</h2>
      <p class="small muted" style="margin-bottom: 0">
        <template v-if="info.last_ingest_at">{{ t('settings.collector.lastData', { time: fmtDateTime(info.last_ingest_at) }) }}</template>
        <template v-else>{{ t('settings.collector.noData') }}</template>
      </p>
    </section>

    <section v-if="info" class="card small muted">
      {{ t('settings.about', { name: info.name, version: info.version, apiVersion: info.api_version, timezone: info.timezone }) }}
    </section>
    <ImportDialog v-if="importing" @close="importing = false"
      @imported="(n) => toast(tn('settings.import.imported', n))" />
  </div>
</template>

<style scoped>
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
