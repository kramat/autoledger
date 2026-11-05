<script setup lang="ts">
// Create/edit form driven by a list of field definitions.
// In edit mode only the fields the user changed are sent, so the API can
// recalculate dependent values (for example a refuel's price after the total changes).
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ApiError, api, type AttachmentResource } from '../api'
import { shrink } from '../attachments'
import { t } from '../i18n'
import { fromLocalInput, toLocalInput } from '../format'
import AttachmentList from './AttachmentList.vue'
import type { Field } from './fields'

const props = defineProps<{
  title: string
  fields: Field[]
  initial: Record<string, unknown>
  mode: 'create' | 'edit'
  save: (data: Record<string, unknown>) => Promise<{ id: string } | void>
  // Records that can carry receipt photos and invoices.
  attachments?: AttachmentResource
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
const pending = ref<File[]>([])
const recordId = typeof props.initial.id === 'string' ? props.initial.id : null

interface Share {
  vehicle_id: string
  percent: number | null
}

function toForm(field: Field, value: unknown): unknown {
  if (field.type === 'shares') {
    // Only vehicles that can be picked: a deleted vehicle drops out of the split.
    const known = new Set(field.options?.map((o) => o.value))
    return ((value as Share[] | null) ?? []).filter((s) => known.has(s.vehicle_id)).map((s) => ({ ...s }))
  }
  if (value === null || value === undefined) return field.type === 'checkbox' ? false : field.type === 'select' ? null : ''
  if (field.type === 'datetime') return toLocalInput(String(value))
  return value
}

function fromForm(field: Field, value: unknown): unknown {
  if (field.type === 'shares') {
    const percent = field.percent?.(values) ?? false
    return (value as Share[]).map((s) => ({ vehicle_id: s.vehicle_id, percent: percent ? s.percent : null }))
  }
  if (field.type === 'checkbox') return Boolean(value)
  if (field.type === 'select') return value ?? null
  if (value === '' || value === null || value === undefined) return null
  if (field.type === 'number') return Number(value)
  if (field.type === 'datetime') return fromLocalInput(String(value))
  return typeof value === 'string' ? value.trim() || null : value
}

const values = reactive<Record<string, unknown>>(
  Object.fromEntries(props.fields.map((f) => [f.key, toForm(f, props.initial[f.key])])),
)
const original = Object.fromEntries(props.fields.map((f) => [f.key, fromForm(f, values[f.key])]))
const errors = ref<Record<string, string>>({})
const message = ref('')
const busy = ref(false)

const visibleFields = computed(() => props.fields.filter((f) => !f.show || f.show(values)))

function shares(key: string): Share[] {
  return values[key] as Share[]
}

function share(key: string, vehicleId: string | null): Share | undefined {
  return shares(key).find((s) => s.vehicle_id === vehicleId)
}

function toggleShare(key: string, vehicleId: string | null, on: boolean): void {
  const list = shares(key)
  const index = list.findIndex((s) => s.vehicle_id === vehicleId)
  if (on && index < 0 && vehicleId) list.push({ vehicle_id: vehicleId, percent: null })
  if (!on && index >= 0) list.splice(index, 1)
}

function setPercent(key: string, vehicleId: string | null, raw: string): void {
  const item = share(key, vehicleId)
  if (item) item.percent = raw === '' ? null : Number(raw)
}

function percentTotal(key: string): string {
  const total = shares(key).reduce((sum, s) => sum + (s.percent ?? 0), 0)
  return String(Math.round(total * 100) / 100)
}

async function submit(): Promise<void> {
  errors.value = {}
  message.value = ''
  const visible = new Set(visibleFields.value.map((f) => f.key))
  const data: Record<string, unknown> = {}
  for (const field of props.fields) {
    const value = visible.has(field.key) ? fromForm(field, values[field.key]) : null
    if (props.mode === 'create') {
      if (value !== null) data[field.key] = value
    } else if (JSON.stringify(value) !== JSON.stringify(original[field.key])) {
      data[field.key] = value
    }
  }
  if (props.mode === 'edit' && Object.keys(data).length === 0) {
    emit('close')
    return
  }
  busy.value = true
  try {
    const saved = await props.save(data)
    if (props.attachments && saved && pending.value.length) {
      for (const file of pending.value) {
        const small = await shrink(file)
        await api.uploadAttachment(props.attachments, saved.id, small, small.name)
      }
      emit('changed')
    }
    emit('close')
  } catch (err) {
    if (err instanceof ApiError) {
      errors.value = err.fields
      const unplaced = Object.keys(err.fields).filter((key) => !visible.has(key))
      message.value = unplaced.length || !Object.keys(err.fields).length ? err.message : ''
    } else {
      message.value = (err as Error).message
    }
  } finally {
    busy.value = false
  }
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay">
    <form class="dialog" role="dialog" aria-modal="true" :aria-label="title" @submit.prevent="submit">
      <h2>{{ title }}</h2>
      <div class="form-grid">
        <template v-for="f in visibleFields" :key="f.key">
          <label v-if="f.type === 'checkbox'" class="field checkbox" :class="{ half: f.half }">
            <input type="checkbox" v-model="values[f.key]" />
            <span>{{ f.label }}<small v-if="f.hint" class="hint checkbox-hint">{{ f.hint }}</small></span>
          </label>
          <div v-else-if="f.type === 'shares'" class="field shares" :class="{ invalid: errors[f.key] }" role="group"
            :aria-label="f.label">
            <span>{{ f.label }}<template v-if="f.required"> *</template></span>
            <div v-for="o in f.options" :key="String(o.value)" class="share-row">
              <label class="checkbox">
                <input type="checkbox" :checked="!!share(f.key, o.value)"
                  @change="toggleShare(f.key, o.value, ($event.target as HTMLInputElement).checked)" />
                <span>{{ o.label }}</span>
              </label>
              <label v-if="f.percent?.(values) && share(f.key, o.value)" class="share-percent">
                <input type="number" min="0" max="100" step="any" :aria-label="`${o.label} %`"
                  :value="share(f.key, o.value)?.percent ?? ''"
                  @input="setPercent(f.key, o.value, ($event.target as HTMLInputElement).value)" />
                <span>%</span>
              </label>
            </div>
            <small v-if="errors[f.key]" class="error">{{ errors[f.key] }}</small>
            <small v-else-if="f.percent?.(values)" class="hint">
              {{ t('common.shares.total', { total: percentTotal(f.key) }) }}
            </small>
            <small v-else-if="f.hint" class="hint">{{ f.hint }}</small>
          </div>
          <label v-else class="field" :class="{ half: f.half, invalid: errors[f.key] }">
            <span>{{ f.label }}<template v-if="f.required"> *</template></span>
            <select v-if="f.type === 'select'" v-model="values[f.key]" :required="f.required">
              <option v-for="o in f.options" :key="String(o.value)" :value="o.value">{{ o.label }}</option>
            </select>
            <textarea v-else-if="f.type === 'textarea'" v-model="values[f.key] as string" rows="2" />
            <input v-else-if="f.type === 'datetime'" type="datetime-local" v-model="values[f.key] as string"
              :required="f.required" />
            <input v-else :type="f.type" v-model="values[f.key] as string" :required="f.required"
              :step="f.step ?? (f.type === 'number' ? 'any' : undefined)" :min="f.min" :placeholder="f.placeholder" />
            <small v-if="errors[f.key]" class="error">{{ errors[f.key] }}</small>
            <small v-else-if="f.hint" class="hint">{{ f.hint }}</small>
          </label>
        </template>
      </div>
      <AttachmentList v-if="attachments" v-model:pending="pending" :resource="attachments" :record-id="recordId"
        @changed="emit('changed')" />
      <p v-if="message" class="notice error">{{ message }}</p>
      <div class="dialog-actions">
        <button type="button" @click="emit('close')">{{ t('common.actions.cancel') }}</button>
        <button type="submit" class="primary" :disabled="busy">
          {{ mode === 'create' ? t('common.actions.add') : t('common.actions.save') }}
        </button>
      </div>
    </form>
  </div>
</template>
