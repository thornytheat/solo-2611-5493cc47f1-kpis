<template>
  <span class="seal" :class="[`seal--${tone}`, `seal--${size}`]">
    <span class="seal__ring" aria-hidden="true"></span>
    <span class="seal__text">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    tone?: 'ink' | 'warn' | 'ok' | 'quiet'
    size?: 'sm' | 'md'
  }>(),
  { tone: 'ink', size: 'sm' },
)
</script>

<style scoped>
.seal {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  color: var(--coffee);
  font-family: var(--mono);
  letter-spacing: 0.14em;
  padding: 3px 10px;
  transform: rotate(-1.5deg);
}
.seal__ring {
  position: absolute;
  inset: 2px;
  border: 1px dashed currentColor;
  opacity: 0.45;
  border-radius: 50% / 22%;
  pointer-events: none;
}
.seal__text { position: relative; }
.seal--sm { font-size: 10px; }
.seal--md { font-size: 12px; padding: 5px 14px; }
.seal--warn { color: var(--brick); }
.seal--ok { color: var(--sage); }
.seal--quiet { color: var(--coffee-3); border-style: dashed; }
</style>
