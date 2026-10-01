<template>
  <section class="page" data-module="elevator">
    <header class="page-head">
      <div>
        <h2>电梯管理管理</h2>
        <p class="page-desc">维护电梯，围绕电梯编号、电梯类型、额定载重、层站数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记电梯</button>
        <button class="btn" type="button" @click="exportRows">导出电梯管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <template v-for="action in rowActions(row)" :key="action">
              <button class="link" type="button" @click="runAction(action, row)">
                {{ action }}
              </button>
            </template>
            <span v-if="!rowActions(row).length" class="muted">—</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无电梯管理数据，可先登记电梯</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条电梯管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request, submitAction } from '@/api/client'

type Row = Record<string, string | number | string[] | null>

const ENDPOINT = '/api/elevator'
const columns = ["电梯编号", "电梯类型", "额定载重", "层站数", "维保单位", "上次维保", "下次维保日", "电梯状态"]
const actions = ["安排维保", "困人救援", "故障检修"]
const statuses = ["正常运行", "维保中", "困人", "检修中"]
const stats = [{"label": "正常运行电梯", "value": 0}, {"label": "维保电梯", "value": 0}, {"label": "检修电梯", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function rowActions(row: Row): string[] {
  const allowed = row.allowedActions
  // 服务层按当前状态+角色实时给出可执行动作；异常时退回本页静态动作表，不致空白。
  return Array.isArray(allowed) ? (allowed as string[]) : actions
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '电梯登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const result = await submitAction(ENDPOINT, row, action)
    await reload()
    errorMessage.value = result.message
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('电梯列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '电梯管理列表读取失败'
  }
}

onMounted(reload)
</script>
