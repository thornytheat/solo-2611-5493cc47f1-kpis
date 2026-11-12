<template>
  <div class="login">
    <section class="card">
      <div class="card__punch" aria-hidden="true">
        <span v-for="n in 7" :key="n" class="card__hole"></span>
      </div>

      <div class="card__top">
        <span class="eyebrow">沐野咖啡连锁 · 会员增长组</span>
        <span class="label">会员卡 NO. 2026-11</span>
      </div>

      <div class="card__glyphs">
        <div class="card__seal serif">烘</div>
        <div class="card__glyph-col">
          <div class="card__vertical serif">同期群留存与 LTV 测算</div>
          <div class="card__stamp">打卡 / 留存</div>
        </div>
      </div>

      <h1 class="display card__title">
        把「拍脑袋的 <span class="card__num mono">32 × 8</span>」<br />
        换成能解释给财务的衰减曲线
      </h1>

      <p class="card__lede">
        12 个首单月同期群，M0 到 M12 的人数留存按格子上色，
        右删失格子直接标灰不参与拟合；ARPU 留存拿去做加权最小二乘，
        拿到 λ 与 R²，再折成 12 个月预测 LTV 和渠道回本周期。
      </p>

      <div class="card__strip">
        <div class="card__strip-col">
          <div class="label">上游</div>
          <ul>
            <li>会员开卡与订单事实（本地 fixture）</li>
            <li>6,000 会员 / 24,000 单 / 4 个渠道</li>
          </ul>
        </div>
        <div class="card__strip-col">
          <div class="label">下游</div>
          <ul>
            <li>月度增长复盘</li>
            <li>渠道预算与门店拉新考核</li>
          </ul>
        </div>
      </div>

      <div class="card__foot">
        <span class="mono">快照 2026-11-30</span>
        <span class="mono">algorithm v1.0.0</span>
        <span class="mono">cohortltv.io</span>
      </div>
    </section>

    <section class="form">
      <div class="form__inner">
        <div class="eyebrow">会员增长组 · 内部工具</div>
        <h2 class="form__title serif">登录烘焙台</h2>
        <p class="form__hint">
          三个演示账号职责不同：负责人可发布报告，分析师可跑矩阵与测算，渠道与门店只能看自己渠道。
        </p>

        <form class="form__body" @submit.prevent="submit">
          <label class="field">
            <span class="label">邮箱</span>
            <input
              v-model="email"
              type="email"
              autocomplete="username"
              placeholder="admin@cohortltv.io"
              data-test="login-email"
            />
          </label>
          <label class="field">
            <span class="label">密码</span>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              placeholder="Demo@2026"
              data-test="login-password"
            />
          </label>

          <ErrorNotice
            v-if="auth.error"
            title="登录失败"
            :message="auth.error"
            :retryable="false"
          />

          <button class="btn btn--solid form__submit" type="submit" :disabled="auth.loading" data-test="login-submit">
            {{ auth.loading ? '正在打卡…' : '打卡进入' }}
          </button>
        </form>

        <hr class="double-rule" />

        <div class="form__accounts">
          <div class="label">演示账号（密码统一 Demo@2026）</div>
          <button
            v-for="account in accounts"
            :key="account.email"
            type="button"
            class="account"
            :data-test="`demo-${account.role}`"
            @click="fill(account.email)"
          >
            <span class="account__role mono">{{ account.roleLabel }}</span>
            <span class="account__mail mono">{{ account.email }}</span>
            <span class="account__note">{{ account.note }}</span>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
import ErrorNotice from '../components/common/ErrorNotice.vue'

const auth = useAuthStore()
const router = useRouter()

const email = ref('admin@cohortltv.io')
const password = ref('Demo@2026')

const accounts = [
  { email: 'admin@cohortltv.io', role: 'admin', roleLabel: '增长负责人', note: '发布报告 / 看审计' },
  { email: 'analyst@cohortltv.io', role: 'analyst', roleLabel: '增长分析师', note: '跑矩阵 / 测算 / 导出' },
  { email: 'viewer@cohortltv.io', role: 'viewer', roleLabel: '门店只读', note: '只看门店渠道' },
]

function fill(value: string) {
  email.value = value
  password.value = 'Demo@2026'
}

async function submit() {
  try {
    await auth.login(email.value, password.value)
    router.push('/matrix')
  } catch {
    /* 错误已在 store.error 展示 */
  }
}
</script>

<style scoped>
.login {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
  gap: 0;
}

.card {
  position: relative;
  margin: 34px 0 34px 34px;
  padding: 26px 30px 20px;
  background: var(--cream-2);
  border: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow: hidden;
}
.card::after {
  content: '';
  position: absolute;
  inset: 7px;
  border: 1px dashed var(--rule-soft);
  pointer-events: none;
}
.card__punch { position: absolute; top: 12px; left: 22px; display: flex; gap: 9px; }
.card__hole {
  width: 11px; height: 11px; border-radius: 50%;
  border: 1px solid var(--rule);
  background: var(--cream);
}
.card__top { display: flex; justify-content: space-between; align-items: center; padding-top: 12px; }
.card__glyphs { display: flex; gap: 18px; align-items: flex-start; }
.card__seal {
  font-size: 40px; line-height: 1;
  border: 2px solid var(--brick);
  color: var(--brick);
  padding: 8px 10px;
  transform: rotate(-3deg);
}
.card__glyph-col { display: flex; flex-direction: column; align-items: flex-start; gap: 10px; }
.card__vertical {
  writing-mode: vertical-rl;
  letter-spacing: 0.3em;
  font-size: 12px;
  color: var(--coffee-2);
}
.card__stamp {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.16em;
  border: 1px solid var(--coffee-3); color: var(--coffee-3);
  padding: 2px 8px; transform: rotate(-1.5deg);
}
.card__title { font-size: clamp(1.5rem, 1.1rem + 1.5vw, 2.25rem); max-width: 22ch; }
.card__num { color: var(--brick); }
.card__lede { margin: 0; max-width: 58ch; color: var(--coffee-2); font-size: 13.5px; }
.card__strip {
  display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
  border-top: var(--hair); border-bottom: var(--hair);
  padding: 12px 0;
}
.card__strip-col ul { margin: 6px 0 0; padding-left: 16px; font-size: 12.5px; color: var(--coffee-2); }
.card__strip-col li { margin-bottom: 3px; }
.card__foot {
  margin-top: auto; display: flex; justify-content: space-between; gap: 10px;
  font-size: 10px; color: var(--coffee-3);
}

.form {
  border-left: var(--hair);
  background: var(--cream-3);
  display: flex; align-items: center; justify-content: center;
  padding: 34px;
}
.form__inner { width: 100%; max-width: 380px; display: flex; flex-direction: column; gap: 12px; }
.form__title { font-size: 24px; }
.form__hint { margin: 0; font-size: 12.5px; color: var(--coffee-2); }
.form__body { display: flex; flex-direction: column; gap: 12px; margin-top: 6px; }
.form__submit { justify-content: center; padding: 10px 14px; font-size: 12px; letter-spacing: 0.16em; }
.form__accounts { display: flex; flex-direction: column; gap: 6px; }
.account {
  display: grid;
  grid-template-columns: 84px 1fr auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  text-align: left;
  border: 1px solid var(--rule-soft);
  background: var(--cream-2);
  padding: 7px 10px;
  transition: transform 200ms var(--ease), border-color 200ms var(--ease);
}
.account:hover { transform: translateX(2px); border-color: var(--coffee-3); }
.account__role { font-size: 10px; letter-spacing: 0.08em; color: var(--coffee); }
.account__mail { font-size: 11px; }
.account__note { font-size: 10px; color: var(--coffee-3); }

@media (max-width: 999px) {
  .login { grid-template-columns: 1fr; }
  .card { margin: 18px 18px 0; }
  .form { border-left: 0; border-top: var(--hair); padding: 24px 18px 34px; }
  .card__strip { grid-template-columns: 1fr; gap: 12px; }
  .account { grid-template-columns: 76px 1fr; }
  .account__note { display: none; }
}
</style>
