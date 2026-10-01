import { defineStore } from 'pinia'

import { fetchJson, getOperatorRole, setOperatorRole } from '@/api/client'

type RoleItem = { code: string; label: string }

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '特种设备安全管理平台',
    role: getOperatorRole(),
    roles: [] as RoleItem[],
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    currentRoleLabel(state): string {
      return state.roles.find((item) => item.code === state.role)?.label ?? state.role
    },
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(code: string) {
      this.role = code
      setOperatorRole(code)
      this.operator = this.currentRoleLabel || code
    },
    async loadRoles() {
      try {
        const payload = await fetchJson<{ roles: RoleItem[] }>('/api/roles')
        this.roles = payload.roles
      } catch {
        // 角色清单读不到时保留本地默认管理员，不阻断页面
      }
    },
  },
})
