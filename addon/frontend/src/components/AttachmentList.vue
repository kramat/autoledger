<script setup lang="ts">
// Receipt photos and invoices of one record. A saved record uploads at once;
// a new one keeps the files in `pending` until the dialog has created it.
import { onMounted, ref } from 'vue'
import { api, type Attachment, type AttachmentResource } from '../api'
import { shrink } from '../attachments'
import { num } from '../format'
import { t } from '../i18n'
import { toast } from '../store'

const props = defineProps<{ resource: AttachmentResource; recordId: string | null }>()
const pending = defineModel<File[]>('pending', { default: () => [] })
const emit = defineEmits<{ changed: [] }>()

const items = ref<Attachment[]>([])
const busy = ref(false)
const error = ref('')
const input = ref<HTMLInputElement | null>(null)

onMounted(async () => {
  if (props.recordId) items.value = await api.attachments(props.resource, props.recordId).catch(() => [])
})

async function picked(event: Event): Promise<void> {
  const files = Array.from((event.target as HTMLInputElement).files ?? [])
  if (input.value) input.value.value = ''
  if (!files.length) return
  error.value = ''
  if (!props.recordId) {
    pending.value = [...pending.value, ...files]
    return
  }
  busy.value = true
  try {
    for (const file of files) {
      const small = await shrink(file)
      items.value.push(await api.uploadAttachment(props.resource, props.recordId, small, small.name))
    }
    emit('changed')
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

async function remove(item: Attachment): Promise<void> {
  await api.removeAttachment(item.id)
  items.value = items.value.filter((a) => a.id !== item.id)
  emit('changed')
  toast(t('common.attachments.removed', { name: item.filename }), t('common.actions.undo'), async () => {
    items.value.push(await api.restoreAttachment(item.id))
    emit('changed')
  })
}

const isImage = (mime: string) => mime.startsWith('image/') && !mime.includes('heic') && !mime.includes('heif')
const size = (bytes: number) => (bytes < 1024 * 1024 ? `${num(bytes / 1024)} kB` : `${num(bytes / 1024 / 1024, 1)} MB`)
</script>

<template>
  <div class="attachments">
    <div class="attachments-head">
      <span class="small muted">{{ t('common.attachments.title') }}</span>
      <button type="button" class="link" :disabled="busy" @click="input?.click()">
        {{ busy ? t('common.attachments.uploading') : t('common.attachments.add') }}
      </button>
      <input ref="input" type="file" accept="image/*,application/pdf" multiple hidden @change="picked" />
    </div>
    <ul v-if="items.length || pending.length" class="attachment-list">
      <li v-for="a in items" :key="a.id">
        <a :href="api.attachmentUrl(a.id)" target="_blank" rel="noopener">
          <img v-if="isImage(a.mime_type)" :src="api.attachmentUrl(a.id)" :alt="a.filename" loading="lazy" />
          <span v-else class="file-icon" aria-hidden="true">{{ a.mime_type === 'application/pdf' ? 'PDF' : 'IMG' }}</span>
          <span class="name">{{ a.filename }}</span>
        </a>
        <span class="small muted">{{ size(a.size) }}</span>
        <button type="button" class="link danger" @click="remove(a)">{{ t('common.attachments.remove') }}</button>
      </li>
      <li v-for="(f, i) in pending" :key="`p${i}`">
        <span class="file-icon" aria-hidden="true">{{ f.type === 'application/pdf' ? 'PDF' : 'IMG' }}</span>
        <span class="name">{{ f.name }}</span>
        <span class="small muted">{{ t('common.attachments.pending') }}</span>
        <button type="button" class="link danger" @click="pending = pending.filter((_, j) => j !== i)">
          {{ t('common.attachments.remove') }}
        </button>
      </li>
    </ul>
    <p v-if="error" class="small error">{{ error }}</p>
  </div>
</template>
