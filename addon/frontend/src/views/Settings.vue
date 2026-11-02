<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { api, ApiError, type Info, type Resource, type Settings } from '../api'
import { fmtDateTime } from '../format'
import { state, toast } from '../store'

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
  { resource: 'maintenance', label: 'Maintenance' },
  { resource: 'expenses', label: 'Other costs' },
]

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
      <p class="small muted">Defaults used when a price is not known. The collector (coming in M2) uses them too.</p>
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
      <p class="small muted">Download all records as CSV (one file per type).</p>
      <div class="actions" style="display: flex; flex-wrap: wrap; gap: 8px">
        <a v-for="e in exports" :key="e.resource" :href="api.exportUrl(e.resource)" download>
          <button type="button">{{ e.label }}</button>
        </a>
      </div>
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
  </div>
</template>
