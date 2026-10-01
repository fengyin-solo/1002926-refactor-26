/** 统一请求封装：拼后端地址、带上当前操作角色、抛网络错误、给页脚留一句可读的说明。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const session = useSessionStore()
  const headers = new Headers(init?.headers ?? { 'Content-Type': 'application/json' })
  // 服务层据此判定当前请求具备哪一档动作的授权。
  headers.set('X-Operator-Role', session.role)
  return fetch(url, { ...init, headers }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}

export type WorkflowAction = {
  name: string
  from: string
  to: string
  requiredRole: string
  step: number
}

export type WorkflowMeta = {
  roles: string[]
  modules: {
    key: string
    label: string
    statuses: string[]
    actions: WorkflowAction[]
    terminalStatus: string
    roles: string[]
  }[]
}

/** 二十个模块统一的动作口径：所有页面都从这里取状态序/动作/角色，避免各页各抄一份。 */
let workflowCache: WorkflowMeta | null = null
export async function fetchWorkflows(force = false): Promise<WorkflowMeta> {
  if (!workflowCache || force) {
    workflowCache = await fetchJson<WorkflowMeta>('/api/workflows')
  }
  return workflowCache
}

type RowShape = Record<string, unknown>

/**
 * 提交一个动作并按后端统一判定结果处理。
 * 后端永远返回 200 + { ok, code, message }，被拦截（回退/越权/跳档/重复提交）时
 * 把原因原样抛给页面展示，绝不静默当成功。
 */
export async function submitAction(
  endpoint: string,
  row: RowShape,
  action: string,
): Promise<{ ok: boolean; message: string }> {
  const response = await request(`${endpoint}/${String(row.id)}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  if (!response.ok) {
    throw new Error('动作未生效，请稍后重试')
  }
  const payload = (await response.json()) as { ok: boolean; message: string }
  if (!payload.ok) {
    throw new Error(payload.message || '动作被拦截')
  }
  return payload
}
