<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

const props = defineProps<{ option: echarts.EChartsCoreOption; height?: number; label: string }>()
const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | undefined
let observer: ResizeObserver | undefined

onMounted(() => {
  chart = echarts.init(el.value!, null, { renderer: 'svg' })
  chart.setOption(props.option)
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(el.value!)
})

watch(
  () => props.option,
  (option) => chart?.setOption(option, true),
)

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div ref="el" role="img" :aria-label="label" :style="{ height: `${height ?? 260}px`, width: '100%' }" />
</template>
