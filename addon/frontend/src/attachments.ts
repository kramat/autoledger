// Helpers for receipt photos and invoices (components/AttachmentList.vue).

const MAX_SIDE = 2000
const SHRINK_ABOVE = 1.5 * 1024 * 1024

/** Phone photos are 3–8 MB; a 2000 px JPEG of a receipt is still sharp and ten times smaller. */
export async function shrink(file: File): Promise<File> {
  if (!file.type.startsWith('image/') || file.type.includes('heic') || file.type.includes('heif')
    || file.size <= SHRINK_ABOVE) return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.85))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
  } catch {
    return file // a format the browser cannot draw: send it as it is
  }
}

/** Table cell for records with receipts: a paperclip and how many. */
export const clip = (row: { attachments?: unknown[] }): string =>
  row.attachments?.length ? `📎 ${row.attachments.length}` : ''
