<template>
  <div class="empty">
    <div class="empty__mark" aria-hidden="true">
      <span class="empty__hole"></span>
      <span class="empty__hole"></span>
      <span class="empty__hole"></span>
    </div>
    <div>
      <div class="empty__title">{{ title }}</div>
      <p class="empty__hint">{{ hint }}</p>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string; hint: string }>()
</script>

<style scoped>
.empty {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  border: 1px dashed var(--rule);
  background: var(--cream-2);
  padding: 22px;
}
.empty__mark { display: flex; gap: 6px; padding-top: 4px; }
.empty__hole {
  width: 12px; height: 12px; border: 1px solid var(--rule); border-radius: 50%;
}
.empty__title { font-weight: 600; }
.empty__hint { margin: 6px 0 12px; color: var(--coffee-2); font-size: 13px; max-width: 60ch; }
</style>
