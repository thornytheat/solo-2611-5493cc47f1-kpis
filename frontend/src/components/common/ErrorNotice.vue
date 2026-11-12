<template>
  <div class="notice" role="alert">
    <div class="notice__body">
      <div class="notice__title">{{ title }}</div>
      <p class="notice__msg">{{ message }}</p>
      <p v-if="detail" class="notice__detail mono">{{ detail }}</p>
    </div>
    <button v-if="retryable" class="btn btn--sm" type="button" @click="$emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    message: string
    detail?: string
    retryable?: boolean
  }>(),
  { title: '出错了', retryable: true, detail: '' },
)
defineEmits<{ retry: [] }>()
</script>

<style scoped>
.notice {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  border: 1px solid var(--brick);
  background: var(--brick-soft);
  padding: 14px 16px;
}
.notice__title { font-weight: 600; color: var(--brick); font-size: 13px; }
.notice__msg { margin: 4px 0 0; font-size: 13px; }
.notice__detail { margin: 6px 0 0; font-size: 11px; color: var(--coffee-2); }
</style>
