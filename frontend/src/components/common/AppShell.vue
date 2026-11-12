<template>
  <div class="shell">
    <aside class="rail">
      <div class="rail__brand">
        <div class="rail__stamp">
          <span class="rail__vertical serif">会 员 烘 焙 台</span>
          <span class="rail__chip">№ 05</span>
        </div>
        <div>
          <div class="rail__wordmark serif">cohortltv</div>
          <div class="eyebrow">retention &amp; ltv desk</div>
        </div>
      </div>

      <div class="rail__org">
        <div class="label">委托方</div>
        <div class="rail__org-name">沐野咖啡连锁</div>
        <div class="rail__org-sub">会员增长组 · 8 人 · 380 家门店</div>
      </div>

      <nav class="rail__nav" aria-label="主导航">
        <div class="eyebrow rail__nav-title">观察与矩阵</div>
        <RouterLink to="/matrix" class="navlink" active-class="is-active" data-test="nav-matrix">
          <span class="navlink__num">壹</span>
          <span class="navlink__label">留存矩阵</span>
        </RouterLink>
        <RouterLink to="/imports" class="navlink" active-class="is-active" data-test="nav-imports">
          <span class="navlink__num">壹＋</span>
          <span class="navlink__label">订单导入</span>
        </RouterLink>
        <RouterLink
          v-if="firstCohort"
          :to="`/cohorts/${firstCohort}`"
          class="navlink"
          active-class="is-active"
          data-test="nav-cohort"
        >
          <span class="navlink__num">貳</span>
          <span class="navlink__label">同期群详情</span>
        </RouterLink>

        <div class="eyebrow rail__nav-title">测算与复盘</div>
        <RouterLink to="/ltv" class="navlink" active-class="is-active" data-test="nav-ltv">
          <span class="navlink__num">參</span>
          <span class="navlink__label">LTV 测算</span>
        </RouterLink>
        <RouterLink to="/channels" class="navlink" active-class="is-active" data-test="nav-channels">
          <span class="navlink__num">肆</span>
          <span class="navlink__label">渠道对比</span>
        </RouterLink>

        <div v-if="auth.role === 'admin'" class="rail__audit">
          <div class="eyebrow">复核留痕</div>
          <p class="rail__audit-text">
            重建、测算、发布与越权都会写进审计日志（admin 可看）。
          </p>
        </div>
      </nav>

      <div class="rail__foot">
        <hr class="double-rule" />
        <div class="rail__user">
          <div class="rail__user-main">
            <div class="rail__user-name">{{ auth.displayName || '未登录' }}</div>
            <div class="rail__user-mail mono">{{ auth.email }}</div>
          </div>
          <StampSeal :label="roleLabel" tone="ink" />
        </div>
        <div class="rail__scope mono">
          渠道范围：{{ auth.channelScope ? channelLabel(auth.channelScope) : '全部渠道' }}
        </div>
        <button class="btn btn--quiet rail__logout" type="button" data-test="logout" @click="handleLogout">
          退出登录
        </button>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div class="topbar__left">
          <span class="label">沐野咖啡连锁 · 会员增长组</span>
          <span class="topbar__slash">/</span>
          <span class="topbar__page">{{ pageTitle }}</span>
        </div>
        <div class="topbar__right mono">
          <span>快照 {{ snapshot }}</span>
          <span class="topbar__dot"></span>
          <span>算法 v1.0.0</span>
        </div>
      </header>
      <div class="body">
        <slot />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore'
import { useCohortStore } from '../../stores/cohortStore'
import { ROLE_LABELS } from '../../constants/roles'
import { CHANNEL_LABELS, type ChannelCode } from '../../constants/enums'
import StampSeal from './StampSeal.vue'

const auth = useAuthStore()
const cohorts = useCohortStore()
const route = useRoute()
const router = useRouter()

const roleLabel = computed(() => ROLE_LABELS[auth.role] ?? auth.role)
const pageTitle = computed(() => (route.meta.title as string) ?? '工作台')
const snapshot = computed(() => cohorts.snapshot || '2026-11')
const firstCohort = computed(() => cohorts.cohorts.length ? cohorts.cohorts[cohorts.cohorts.length - 1].month : '')

function channelLabel(code: string): string {
  return CHANNEL_LABELS[code as ChannelCode] ?? code
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}

onMounted(() => {
  if (!cohorts.matrix) void cohorts.load()
})
</script>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--rail) minmax(0, 1fr);
  min-height: 100vh;
}

.rail {
  border-right: var(--hair);
  background: var(--cream-2);
  padding: 20px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.rail__brand { display: flex; gap: 12px; align-items: flex-start; }
.rail__stamp { display: flex; flex-direction: column; align-items: center; gap: 6px; }
.rail__vertical {
  writing-mode: vertical-rl;
  letter-spacing: 0.32em;
  font-size: 13px;
  color: var(--coffee);
  border: 1px solid var(--rule);
  padding: 10px 6px;
  background: var(--cream);
}
.rail__chip {
  font-family: var(--mono);
  font-size: 9px;
  color: var(--coffee-3);
  letter-spacing: 0.1em;
}
.rail__wordmark { font-size: 19px; letter-spacing: 0.02em; }
.rail__org { border-top: var(--hair); border-bottom: var(--hair); padding: 10px 0; }
.rail__org-name { font-size: 13.5px; font-weight: 600; margin-top: 2px; }
.rail__org-sub { font-family: var(--mono); font-size: 10px; color: var(--coffee-3); margin-top: 3px; }
.rail__nav { display: flex; flex-direction: column; gap: 4px; }
.rail__nav-title { margin: 10px 0 4px; }
.navlink {
  display: flex; align-items: center; gap: 10px;
  padding: 7px 8px;
  border-left: 2px solid transparent;
  transition: background-color 220ms var(--ease), border-color 220ms var(--ease), transform 220ms var(--ease);
}
.navlink:hover { background: var(--cream-3); transform: translateX(2px); }
.navlink.is-active { border-left-color: var(--coffee); background: var(--cream-3); }
.navlink__num { font-family: var(--mono); font-size: 10px; color: var(--coffee-3); }
.navlink__label { font-size: 13px; }
.rail__audit { margin-top: 14px; border: 1px dashed var(--rule); padding: 9px 10px; }
.rail__audit-text { margin: 5px 0 0; font-size: 11px; color: var(--coffee-2); line-height: 1.5; }
.rail__foot { margin-top: auto; }
.rail__user { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.rail__user-name { font-size: 13px; font-weight: 600; }
.rail__user-mail { font-size: 10px; color: var(--coffee-3); }
.rail__scope { font-size: 10px; color: var(--coffee-3); margin-top: 6px; }
.rail__logout { width: 100%; justify-content: center; margin-top: 10px; }

.main { min-width: 0; display: flex; flex-direction: column; }
.topbar {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 12px 26px;
  border-bottom: var(--hair);
  background: color-mix(in oklch, var(--cream-2) 82%, transparent);
  position: sticky; top: 0; z-index: 5;
  backdrop-filter: none;
}
.topbar__left { display: flex; align-items: center; gap: 8px; }
.topbar__slash { color: var(--coffee-3); }
.topbar__page { font-size: 13px; font-weight: 600; }
.topbar__right { display: flex; align-items: center; gap: 8px; font-size: 10.5px; color: var(--coffee-3); }
.topbar__dot { width: 4px; height: 4px; border-radius: 50%; background: var(--coffee-3); }
.body { padding: 22px 26px 40px; max-width: 1520px; width: 100%; }

@media (max-width: 1099px) {
  .shell { grid-template-columns: 1fr; }
  .rail {
    position: static; height: auto; flex-direction: column;
    border-right: 0; border-bottom: var(--hair);
  }
  .rail__nav { flex-direction: row; flex-wrap: wrap; gap: 6px; }
  .rail__nav-title { display: none; }
  .navlink { border-left: 0; border-bottom: 2px solid transparent; }
  .navlink.is-active { border-bottom-color: var(--coffee); }
  .rail__audit { display: none; }
  .rail__foot { margin-top: 0; }
  .rail__logout { width: auto; }
  .body { padding: 18px 16px 32px; }
  .topbar { padding: 10px 16px; position: static; }
}
</style>
