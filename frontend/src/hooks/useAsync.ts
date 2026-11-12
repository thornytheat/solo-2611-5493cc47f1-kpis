import { ref, type Ref } from 'vue'

export interface AsyncState<T> {
  data: Ref<T | null>
  loading: Ref<boolean>
  error: Ref<string>
  run: (task: () => Promise<T>) => Promise<T | null>
  reset: () => void
}

/** 统一 loading / error / 重试的轻量 composable。 */
export function useAsync<T>(initial: T | null = null): AsyncState<T> {
  const data = ref<T | null>(initial) as Ref<T | null>
  const loading = ref(false)
  const error = ref('')

  async function run(task: () => Promise<T>): Promise<T | null> {
    loading.value = true
    error.value = ''
    try {
      const result = await task()
      data.value = result
      return result
    } catch (err) {
      error.value = (err as { message?: string }).message ?? '操作失败'
      return null
    } finally {
      loading.value = false
    }
  }

  function reset() {
    data.value = initial
    error.value = ''
    loading.value = false
  }

  return { data, loading, error, run, reset }
}
