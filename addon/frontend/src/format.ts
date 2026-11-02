// Number, money and date formatting, plus conversions for form inputs.

let currency = 'EUR'

export function setCurrency(code: string): void {
  currency = code
}

export function money(value: number | null | undefined, digits = 2): string {
  if (value == null) return '—'
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function num(value: number | null | undefined, digits = 0): string {
  if (value == null) return '—'
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

export function km(value: number | null | undefined): string {
  return value == null ? '—' : `${num(value)} km`
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** Local calendar date as YYYY-MM-DD. */
export function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function parse(value: string): Date {
  // A bare date is a calendar day; read it as local noon so no time zone shifts it.
  return new Date(value.length === 10 ? `${value}T12:00:00` : value)
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return '—'
  return parse(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return parse(value).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtMonth(month: string): string {
  return parse(`${month}-01`).toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
}

/** ISO timestamp → value for <input type="datetime-local">. */
export function toLocalInput(value: string | null | undefined): string {
  if (!value) return ''
  const d = new Date(value)
  return `${isoDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** <input type="datetime-local"> value → ISO timestamp with time zone. */
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString()
}

export function nowLocalInput(): string {
  return toLocalInput(new Date().toISOString())
}
