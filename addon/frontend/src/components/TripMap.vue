<script setup lang="ts">
// Start and end points of trips on OpenStreetMap. No route is recorded, so lines are straight.
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Trip } from '../api'
import { fmtDateTime, money, num } from '../format'
import { lang, t } from '../i18n'

const props = defineProps<{ trips: Trip[]; selected?: string | null }>()
const emit = defineEmits<{ select: [trip: Trip] }>()

const el = ref<HTMLDivElement | null>(null)
let map: L.Map | null = null
let layer: L.LayerGroup | null = null

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function escape(text: string): string {
  return text.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]!)
}

function place(address: string | null, zone: string | null): string {
  return escape(address ?? zone ?? t('trips.map.unknownPlace'))
}

function draw(): void {
  if (!map || !layer) return
  layer.clearLayers()
  const color = cssVar('--series-1')
  const highlight = cssVar('--series-2')
  const surface = cssVar('--surface')
  const bounds: L.LatLngExpression[] = []
  for (const trip of props.trips) {
    const start = trip.start_lat != null && trip.start_lon != null ? L.latLng(trip.start_lat, trip.start_lon) : null
    const end = trip.end_lat != null && trip.end_lon != null ? L.latLng(trip.end_lat, trip.end_lon) : null
    if (!start && !end) continue
    const on = trip.id === props.selected
    const stroke = on ? highlight : color
    const tip =
      `<b>${fmtDateTime(trip.start_ts)}</b><br>${place(trip.start_address, trip.start_zone)} → ` +
      `${place(trip.end_address, trip.end_zone)}<br>${num(trip.distance_km, 1)} km · ${money(trip.costing?.cost)}`
    if (start && end && !start.equals(end)) {
      L.polyline([start, end], { color: stroke, weight: on ? 3 : 2, opacity: on ? 1 : 0.6, dashArray: '4 6' })
        .bindTooltip(tip, { sticky: true })
        .on('click', () => emit('select', trip))
        .addTo(layer)
    }
    for (const [point, filled] of [[start, false], [end, true]] as const) {
      if (!point) continue
      bounds.push(point)
      L.circleMarker(point, {
        radius: on ? 7 : 5,
        color: filled ? surface : stroke,
        weight: 2,
        fillColor: filled ? stroke : surface,
        fillOpacity: 1,
      })
        .bindTooltip(tip)
        .on('click', () => emit('select', trip))
        .addTo(layer)
    }
  }
  if (bounds.length) map.fitBounds(L.latLngBounds(bounds), { padding: [24, 24], maxZoom: 15 })
}

onMounted(() => {
  if (!el.value) return
  map = L.map(el.value, { scrollWheelZoom: false }).setView([52.09, 4.4], 11)
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map)
  layer = L.layerGroup().addTo(map)
  draw()
})

watch(() => [props.trips, props.selected], draw, { deep: true })
watch(lang, draw)

onBeforeUnmount(() => {
  map?.remove()
  map = null
})
</script>

<template>
  <div class="trip-map">
    <div ref="el" class="trip-map-canvas" role="img" :aria-label="t('trips.map.ariaLabel')" />
    <p class="small muted legend">
      <span class="dot hollow" /> {{ t('trips.map.start') }} <span class="dot" /> {{ t('trips.map.end') }} · {{ t('trips.map.straightLines') }}
    </p>
  </div>
</template>

<style scoped>
.trip-map-canvas {
  height: 420px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
}
.legend {
  margin: 6px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--series-1);
  border: 2px solid var(--surface);
  box-shadow: 0 0 0 1px var(--series-1);
}
.dot.hollow {
  background: var(--surface);
  border-color: var(--series-1);
  box-shadow: none;
}
</style>
