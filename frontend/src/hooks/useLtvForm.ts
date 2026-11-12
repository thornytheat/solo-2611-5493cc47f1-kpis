import { computed, reactive, ref } from 'vue'
import { Channel, CHANNEL_LABELS } from '../constants/enums'

export interface LtvFormState {
  name: string
  observedMonths: number | null
  marginRate: number
  forecastMonths: number
  delta: number
  cac: Record<string, number>
}

const DEFAULT_CAC: Record<string, number> = {
  [Channel.Private]: 38,
  [Channel.PaidFeed]: 126,
  [Channel.Store]: 16,
  [Channel.Partner]: 58,
}

/** LTV 测算参数表单（口径可调，结果一律来自后端）。 */
export function useLtvForm() {
  const form = reactive<LtvFormState>({
    name: '',
    observedMonths: null,
    marginRate: 0.5,
    forecastMonths: 12,
    delta: 0.03,
    cac: { ...DEFAULT_CAC },
  })
  const touched = ref(false)

  const cacList = computed(() =>
    Object.values(Channel)
      .filter((code) => code !== Channel.All)
      .map((code) => ({
        code,
        label: CHANNEL_LABELS[code],
        value: form.cac[code] ?? 0,
      })),
  )

  const overridden = computed(() =>
    Object.values(Channel)
      .filter((code) => code !== Channel.All)
      .some((code) => form.cac[code] !== DEFAULT_CAC[code]),
  )

  function defaultName(snapshot: string): string {
    const stamp = new Date()
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${snapshot} 增长复盘 · ${pad(stamp.getMonth() + 1)}${pad(stamp.getDate())}-${pad(stamp.getHours())}${pad(stamp.getMinutes())}`
  }

  function payload(snapshot: string) {
    return {
      name: form.name.trim() || defaultName(snapshot),
      observed_months: form.observedMonths,
      margin_rate: form.marginRate,
      forecast_months: form.forecastMonths,
      channel_cac: { ...form.cac },
    }
  }

  function resetCac() {
    form.cac = { ...DEFAULT_CAC }
    touched.value = false
  }

  return { form, cacList, overridden, touched, payload, resetCac, defaultName }
}
