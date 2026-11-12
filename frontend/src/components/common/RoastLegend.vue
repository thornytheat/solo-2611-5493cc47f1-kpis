<template>
  <div class="legend">
    <span class="label">{{ label }}</span>
    <div class="legend__scale">
      <span v-for="step in steps" :key="step" class="legend__swatch" :style="{ background: `var(--roast-${step})` }"></span>
      <span class="legend__censor" aria-hidden="true"></span>
    </div>
    <span class="legend__ends">
      <span>0%</span><span>{{ topLabel }}</span>
      <span class="legend__censor-label">右删失</span>
    </span>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ label?: string; topLabel?: string }>(), {
  label: '烘豆色阶（留存率）',
  topLabel: '100%',
})
const steps = [0, 1, 2, 3, 4, 5, 6]
</script>

<style scoped>
.legend { display: flex; flex-direction: column; gap: 6px; }
.legend__scale { display: flex; align-items: stretch; gap: 3px; }
.legend__swatch { width: 26px; height: 12px; border: 1px solid var(--rule-soft); }
.legend__censor {
  width: 26px; height: 12px; margin-left: 6px; border: 1px solid var(--rule-soft);
  background-image: repeating-linear-gradient(45deg, var(--cream-4) 0 3px, var(--cream-2) 3px 6px);
}
.legend__ends { display: flex; gap: 10px; font-family: var(--mono); font-size: 10px; color: var(--coffee-3); }
.legend__censor-label { margin-left: auto; }
</style>
