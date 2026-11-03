<script setup lang="ts">
// CSV import: pick a file, check the column mapping on a preview, then import the valid rows.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { api, type ImportPreview, type ImportResource } from '../api'
import { IMPORT_FIELDS, IMPORT_RESOURCES } from '../labels'
import { activeVehicles } from '../store'
import { defaultVehicleId } from './fields'

const emit = defineEmits<{ close: []; imported: [count: number] }>()

const resource = ref<ImportResource>('refuels')
const vehicleId = ref<string>(defaultVehicleId() ?? activeVehicles.value[0]?.id ?? '')
const content = ref('')
const fileName = ref('')
const mapping = ref<Record<string, string>>({})
const decimal = ref<'.' | ','>('.')
const dateOrder = ref<'dmy' | 'mdy' | 'ymd'>('dmy')
const preview = ref<ImportPreview | null>(null)
const error = ref('')
const busy = ref(false)
// After the first preview the user's choices are sent; before it, the server guesses.
const guessed = ref(false)

async function pick(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  fileName.value = file.name
  content.value = await file.text()
  guessed.value = false
  await run()
}

async function run(commit = false): Promise<void> {
  if (!content.value || !vehicleId.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await api.importCsv(
      {
        resource: resource.value,
        vehicle_id: vehicleId.value,
        content: content.value,
        ...(guessed.value ? { mapping: mapping.value, decimal: decimal.value, date_order: dateOrder.value } : {}),
      },
      commit,
    )
    if (commit) {
      emit('imported', result.created)
      emit('close')
      return
    }
    preview.value = result
    mapping.value = { ...result.mapping }
    decimal.value = result.decimal
    dateOrder.value = result.date_order
    guessed.value = true
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

function changeResource(): void {
  guessed.value = false // other fields: guess the mapping again
  run()
}

function setColumn(field: string, column: string): void {
  const next = { ...mapping.value }
  if (column) next[field] = column
  else delete next[field]
  mapping.value = next
  run()
}

// Mapped fields, plus the refuel amounts: the missing one of the three is calculated.
const DERIVED = new Set(['litres', 'price_per_l', 'total'])
const previewColumns = computed(() =>
  (preview.value?.fields ?? [])
    .map((f) => f.name)
    .filter((f) => mapping.value[f] || (resource.value === 'refuels' && DERIVED.has(f))),
)

function show(value: unknown): string {
  if (value == null) return ''
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) return value.slice(0, 16).replace('T', ' ')
  return String(value)
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay">
    <div class="dialog wide" role="dialog" aria-modal="true" aria-label="Import CSV">
      <h2>Import CSV</h2>
      <p class="small muted" style="margin: 4px 0 0">
        From a spreadsheet or another app. Nothing is saved until you click Import; rows that are already in AutoLedger
        are skipped.
      </p>
      <div class="form-grid">
        <label class="field half">
          <span>What is in the file</span>
          <select v-model="resource" @change="changeResource">
            <option v-for="r in IMPORT_RESOURCES" :key="String(r.value)" :value="r.value">{{ r.label }}</option>
          </select>
        </label>
        <label class="field half">
          <span>Vehicle</span>
          <select v-model="vehicleId" @change="run()">
            <option v-for="v in activeVehicles" :key="v.id" :value="v.id">{{ v.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>CSV file</span>
          <input type="file" accept=".csv,.txt,text/csv" @change="pick" />
        </label>
      </div>

      <template v-if="preview">
        <h3 style="margin: 4px 0 8px">Columns</h3>
        <div class="form-grid" style="margin-top: 0">
          <label v-for="f in preview.fields" :key="f.name" class="field half">
            <span>{{ IMPORT_FIELDS[f.name] ?? f.name }}<template v-if="f.required"> *</template></span>
            <select :value="mapping[f.name] ?? ''" @change="setColumn(f.name, ($event.target as HTMLSelectElement).value)">
              <option value="">— not in the file —</option>
              <option v-for="c in preview.columns" :key="c" :value="c">{{ c }}</option>
            </select>
          </label>
          <label class="field half">
            <span>Decimal separator</span>
            <select v-model="decimal" @change="run()">
              <option value=",">Comma (12,50)</option>
              <option value=".">Point (12.50)</option>
            </select>
          </label>
          <label class="field half">
            <span>Dates</span>
            <select v-model="dateOrder" @change="run()">
              <option value="dmy">Day first (31-12-2025)</option>
              <option value="mdy">Month first (12/31/2025)</option>
              <option value="ymd">Year first (2025-12-31)</option>
            </select>
          </label>
        </div>

        <p class="small" style="margin: 0 0 8px">
          {{ fileName }}: {{ preview.total_rows }} rows · <b>{{ preview.counts.ok }} to import</b>
          <template v-if="preview.counts.duplicate"> · {{ preview.counts.duplicate }} already there</template>
          <template v-if="preview.counts.error"> · {{ preview.counts.error }} with errors</template>
          <template v-if="preview.total_rows > preview.rows.length"> (first {{ preview.rows.length }} shown)</template>
        </p>
        <div class="table-wrap preview">
          <table>
            <thead>
              <tr>
                <th scope="col">Line</th>
                <th v-for="f in previewColumns" :key="f" scope="col">{{ IMPORT_FIELDS[f] ?? f }}</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in preview.rows" :key="r.line">
                <td class="num">{{ r.line }}</td>
                <td v-for="f in previewColumns" :key="f">{{ show(r.values[f]) }}</td>
                <td class="wrap">
                  <span v-if="r.status === 'ok'" class="badge ok">✓ ok</span>
                  <span v-else-if="r.status === 'duplicate'" class="badge">= already there</span>
                  <span v-else class="error">⛔ {{ r.error }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <p v-if="error" class="notice error">{{ error }}</p>
      <p v-if="!activeVehicles.length" class="notice">Add a vehicle first.</p>
      <div class="dialog-actions">
        <button type="button" @click="emit('close')">Cancel</button>
        <button type="button" class="primary" :disabled="busy || !preview || !preview.counts.ok" @click="run(true)">
          Import {{ preview?.counts.ok ?? '' }} rows
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog.wide {
  width: min(860px, 100%);
}

.preview {
  max-height: 320px;
  overflow: auto;
}

.preview td {
  white-space: nowrap;
}
</style>
