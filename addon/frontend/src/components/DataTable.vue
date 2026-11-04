<script setup lang="ts" generic="T extends { id: string }">
import { t } from '../i18n'

export interface Column<R> {
  key: string
  label: string
  value: (row: R) => string
  num?: boolean
  wrap?: boolean
}

defineProps<{
  columns: Column<T>[]
  rows: T[]
  empty: string
  loading?: boolean
  extra?: { label: (row: T) => string; run: (row: T) => void }
}>()
const emit = defineEmits<{ edit: [row: T]; delete: [row: T] }>()
// Empty and "—" cells are left out of the card layout on narrow screens.
const isBlank = (value: string) => !value || value === '—'
</script>

<template>
  <div class="table-wrap">
    <table v-if="rows.length" class="data-table">
      <thead>
        <tr>
          <th v-for="c in columns" :key="c.key" :class="{ num: c.num }" scope="col">{{ c.label }}</th>
          <th><span class="sr-only">{{ t('common.actions.actions') }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <!-- data-label: on narrow screens (a folded phone) each row is a card with labelled values -->
          <td v-for="c in columns" :key="c.key" :class="{ num: c.num, wrap: c.wrap, blank: isBlank(c.value(row)) }"
            :data-label="c.label">{{ c.value(row) }}</td>
          <td class="row-actions">
            <button class="link" @click="emit('edit', row)">{{ t('common.actions.edit') }}</button>
            <button v-if="extra" class="link" @click="extra.run(row)">{{ extra.label(row) }}</button>
            <button class="link danger" @click="emit('delete', row)">{{ t('common.actions.delete') }}</button>
          </td>
        </tr>
      </tbody>
      <tfoot v-if="$slots.foot">
        <slot name="foot" />
      </tfoot>
    </table>
    <div v-else class="empty">{{ loading ? t('common.actions.loading') : empty }}</div>
  </div>
</template>
