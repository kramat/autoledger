<script setup lang="ts" generic="T extends { id: string }">
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
</script>

<template>
  <div class="table-wrap">
    <table v-if="rows.length">
      <thead>
        <tr>
          <th v-for="c in columns" :key="c.key" :class="{ num: c.num }" scope="col">{{ c.label }}</th>
          <th><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.id">
          <td v-for="c in columns" :key="c.key" :class="{ num: c.num, wrap: c.wrap }">{{ c.value(row) }}</td>
          <td class="row-actions">
            <button class="link" @click="emit('edit', row)">Edit</button>
            <button v-if="extra" class="link" @click="extra.run(row)">{{ extra.label(row) }}</button>
            <button class="link danger" @click="emit('delete', row)">Delete</button>
          </td>
        </tr>
      </tbody>
      <tfoot v-if="$slots.foot">
        <slot name="foot" />
      </tfoot>
    </table>
    <div v-else class="empty">{{ loading ? 'Loading…' : empty }}</div>
  </div>
</template>
