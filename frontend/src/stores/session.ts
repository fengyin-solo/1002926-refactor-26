import { defineStore } from 'pinia'

// 与后端 app.workflow.ROLE_STEPS 保持一致：三档动作分别由这三个角色授权。
export const ROLES = ['经办人', '复核人', '审批人'] as const
export type OperatorRole = (typeof ROLES)[number]

export const useSessionStore = defineStore('session', {
  state: () => ({
    operator: '值班管理员',
    shiftLabel: '白班 08:00-20:00',
    scope: '特种设备安全管理平台',
    role: '经办人' as OperatorRole,
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
  },
  actions: {
    setShift(label: string) {
      this.shiftLabel = label
    },
    setRole(role: OperatorRole) {
      this.role = role
    },
  },
})
