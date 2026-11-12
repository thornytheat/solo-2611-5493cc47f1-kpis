<template>
  <header class="head">
    <div class="head__main">
      <div class="eyebrow">{{ eyebrow }}</div>
      <h1 class="head__title">{{ title }}</h1>
      <p v-if="subtitle" class="head__sub">{{ subtitle }}</p>
    </div>
    <div class="head__side">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  eyebrow: string
  title: string
  subtitle?: string
}>()
</script>

<style scoped>
.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 14px;
  border-bottom: var(--double);
  margin-bottom: 20px;
}
.head__main { min-width: 0; }
.head__title {
  font-size: clamp(1.35rem, 1.05rem + 1vw, 1.85rem);
  margin-top: 4px;
}
.head__sub {
  margin: 6px 0 0;
  color: var(--coffee-2);
  font-size: 13px;
  max-width: 68ch;
}
.head__side { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
@media (max-width: 767px) {
  .head { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
