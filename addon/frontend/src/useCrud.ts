// List + create/edit dialog + delete-with-undo, shared by the list pages.

import { ref, watch, type Ref } from 'vue'
import { api, type Resource } from './api'
import { toast } from './store'

type Params = Record<string, string | number | boolean | null | undefined>

interface DialogState {
  mode: 'create' | 'edit'
  initial: Record<string, unknown>
  id?: string
}

export function useCrud<T extends { id: string }>(
  resource: Resource,
  params: () => Params,
  options: { noun: string; afterChange?: () => Promise<void> },
) {
  const items = ref([]) as Ref<T[]>
  const loading = ref(true)
  const error = ref('')
  const dialog = ref<DialogState | null>(null)

  async function load(): Promise<void> {
    loading.value = true
    try {
      items.value = (await api.list<T>(resource, params())).items
      error.value = ''
    } catch (err) {
      error.value = (err as Error).message
    } finally {
      loading.value = false
    }
  }

  async function changed(): Promise<void> {
    await options.afterChange?.()
    await load()
  }

  watch(params, load, { immediate: true, deep: true })

  async function remove(row: T): Promise<void> {
    await api.remove(resource, row.id)
    await changed()
    toast(`${options.noun} deleted`, 'Undo', async () => {
      await api.restore(resource, row.id)
      await changed()
    })
  }

  function openCreate(initial: Record<string, unknown> = {}): void {
    dialog.value = { mode: 'create', initial }
  }

  function openEdit(row: T): void {
    dialog.value = { mode: 'edit', initial: { ...row }, id: row.id }
  }

  async function save(data: Record<string, unknown>): Promise<void> {
    const current = dialog.value
    if (!current) return
    if (current.mode === 'create') await api.create(resource, data)
    else await api.update(resource, current.id!, data)
    await changed()
    toast(`${options.noun} ${current.mode === 'create' ? 'added' : 'saved'}`)
  }

  return { items, loading, error, dialog, load, remove, openCreate, openEdit, save }
}
