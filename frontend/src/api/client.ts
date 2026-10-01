/** 统一请求封装：拼后端地址、带上当前值班角色、抛网络错误。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const ROLE_STORAGE_KEY = 'operator-role'

/** 当前值班角色码，随每次请求以 X-Operator-Role 头带给后端做授权判定。 */
let operatorRole = localStorage.getItem(ROLE_STORAGE_KEY) ?? 'admin'

export function getOperatorRole(): string {
  return operatorRole
}

export function setOperatorRole(role: string): void {
  operatorRole = role
  localStorage.setItem(ROLE_STORAGE_KEY, role)
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  if (operatorRole) {
    headers.set('X-Operator-Role', operatorRole)
  }
  return fetch(url, {
    ...init,
    headers,
  }).catch((error: unknown) => {
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
