<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type Info, type Resource, type RestoreResult, type Settings } from '../api'
import ImportDialog from '../components/ImportDialog.vue'
import { fmtDateTime } from '../format'
import { loadVehicles, state, toast } from '../store'

const form = reactive<Settings>(JSON.parse(JSON.stringify(state.settings)))
const errors = ref<Record<string, string>>({})
const saving = ref(false)
const info = ref<Info | null>(null)
const token = ref('')
const tokenError = ref('')
const showToken = ref(false)
const confirmRegenerate = ref(false)

const exports: { resource: Resource; label: string }[] = [
  { resource: 'vehicles', label: 'Vehicles' },
  { resource: 'refuels', label: 'Refuels' },
  { resource: 'odometer-readings', label: 'Odometer readings' },
  { resource: 'charges', label: 'Charges' },
  { resource: 'trips', label: 'Trips' },
  { resource: 'idle-records', label: 'Climate & standby' },
  { resource: 'maintenance', label: 'Maintenance' },
  { resource: 'maintenance-schedules', label: 'Maintenance schedules' },
  { resource: 'expenses', label: 'Other costs' },
]

const importing = ref(false)
const restoreFile = ref<File | null>(null)
const restoreMode = ref<'empty' | 'merge'>('empty')
const restoreResult = ref<RestoreResult | null>(null)
const restoreError = ref('')
const restoring = ref(false)

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
    toast('Backup restored')
  } catch (err) {
    restoreError.value = err instanceof SyntaxError ? 'This file is not a JSON backup.' : (err as Error).message
  } finally {
    restoring.value = false
  }
}

function restoredCount(result: RestoreResult): number {
  return Object.values(result.tables).reduce((sum, t) => sum + t.inserted, 0)
}

function skippedCount(result: RestoreResult): number {
  return Object.values(result.tables).reduce((sum, t) => sum + t.skipped, 0)
}

async function save(): Promise<void> {
  saving.value = true
  errors.value = {}
  try {
    form.currency = form.currency.toUpperCase()
    state.settings = await api.saveSettings(form)
    toast('Settings saved')
  } catch (err) {
    if (err instanceof ApiError) errors.value = err.fields
    toast(`Not saved: ${(err as Error).message}`)
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
  toast('New token created. Update it wherever the old one was used.')
}

async function copyToken(): Promise<void> {
  await navigator.clipboard.writeText(token.value)
  toast('Token copied')
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
      <h2>Prices and currency</h2>
      <p class="small muted">Defaults used when a price is not known, also by the Collector.</p>
      <div class="form-grid">
        <label class="field half" :class="{ invalid: errors.currency }">
          <span>Currency (ISO code)</span>
          <input v-model="form.currency" maxlength="3" required />
          <small v-if="errors.currency" class="error">{{ errors.currency }}</small>
        </label>
        <label class="field half">
          <span>Electricity, fallback price per kWh</span>
          <input type="number" step="any" min="0" v-model.number="form.electricity_price" required />
        </label>
        <label class="field half">
          <span>Public charging, default price per kWh</span>
          <input type="number" step="any" min="0" v-model.number="form.public_charge_price" required />
        </label>
        <label class="field half">
          <span>Petrol, default price per litre</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.petrol" required />
        </label>
        <label class="field half">
          <span>Diesel, default price per litre</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.diesel" required />
        </label>
        <label class="field half">
          <span>LPG, default price per litre</span>
          <input type="number" step="any" min="0" v-model.number="form.fuel_prices.lpg" required />
        </label>
      </div>
      <div class="dialog-actions">
        <button type="submit" class="primary" :disabled="saving">Save</button>
      </div>
    </form>

    <section class="card">
      <h2>Export</h2>
      <p class="small muted">All records in one Excel workbook (a sheet per type), or one CSV file per type.</p>
      <div class="button-row">
        <a :href="api.recordsWorkbookUrl()" download><button type="button" class="primary">All records (XLSX)</button></a>
        <a v-for="e in exports" :key="e.resource" :href="api.exportUrl(e.resource)" download>
          <button type="button">{{ e.label }}</button>
        </a>
      </div>
    </section>

    <section class="card">
      <h2>Import</h2>
      <p class="small muted">
        Refuels, maintenance, odometer readings or other costs from a CSV file, for example history from a spreadsheet.
        You check the columns on a preview before anything is saved.
      </p>
      <div class="button-row">
        <button type="button" :disabled="!state.vehicles.length" @click="importing = true">Import CSV…</button>
      </div>
    </section>

    <section class="card">
      <h2>Backup</h2>
      <p class="small muted">
        A full JSON backup of everything in AutoLedger, to move to another installation. Home Assistant backups include
        the add-on's database as well. The API token is not in the file.
      </p>
      <div class="button-row">
        <a :href="api.backupUrl()" download><button type="button">Download backup</button></a>
      </div>
      <h3 style="margin: 16px 0 8px">Restore</h3>
      <div class="form-grid" style="margin: 0 0 12px">
        <label class="field">
          <span>Backup file</span>
          <input type="file" accept=".json,application/json" @change="pickBackup" />
        </label>
        <label class="field">
          <span>How</span>
          <select v-model="restoreMode">
            <option value="empty">Into this add-on while it is still empty</option>
            <option value="merge">Add what is missing, keep what is here</option>
          </select>
        </label>
      </div>
      <p class="small muted" style="margin: 0 0 12px">The current database is copied to /data/backups first.</p>
      <div class="button-row">
        <button type="button" class="primary" :disabled="!restoreFile || restoring" @click="restore">Restore</button>
      </div>
      <p v-if="restoreError" class="notice error" style="margin-top: 12px">{{ restoreError }}</p>
      <p v-if="restoreResult" class="notice" style="margin-top: 12px">
        Restored {{ restoredCount(restoreResult) }} records<template v-if="skippedCount(restoreResult)">;
          {{ skippedCount(restoreResult) }} were already here</template>.
      </p>
    </section>

    <section class="card">
      <h2>API token</h2>
      <p class="small muted">
        The AutoLedger Collector integration and your own scripts use this token. Keep it private.
      </p>
      <p v-if="tokenError" class="notice">{{ tokenError }}</p>
      <template v-else>
        <p><code>{{ showToken ? token : '•'.repeat(24) }}</code></p>
        <div style="display: flex; flex-wrap: wrap; gap: 8px">
          <button type="button" @click="showToken = !showToken">{{ showToken ? 'Hide' : 'Show' }}</button>
          <button type="button" @click="copyToken">Copy</button>
          <button type="button" class="danger" @click="regenerate">
            {{ confirmRegenerate ? 'Click again to replace the token' : 'Create new token' }}
          </button>
        </div>
      </template>
    </section>

    <section v-if="info" class="card">
      <h2>Collector</h2>
      <p class="small muted" style="margin-bottom: 0">
        <template v-if="info.last_ingest_at">Last data from the AutoLedger Collector: {{ fmtDateTime(info.last_ingest_at) }}.</template>
        <template v-else>The AutoLedger Collector has not sent any data yet. Install it via HACS and add the integration.</template>
      </p>
    </section>

    <section v-if="info" class="card small muted">
      {{ info.name }} {{ info.version }} · API v{{ info.api_version }} · Time zone {{ info.timezone }}
    </section>
    <ImportDialog v-if="importing" @close="importing = false"
      @imported="(n) => toast(`${n} records imported`)" />
  </div>
</template>

<style scoped>
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
