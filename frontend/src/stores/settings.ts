import { defineStore } from 'pinia'
import { ref } from 'vue'
import { settingsApi } from '@/api'
import type { Settings } from '@/types/api'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<Settings | null>(null)
  const isLoading = ref(false)
  const loadError = ref<string | null>(null)

  // 加载设置
  async function loadSettings() {
    isLoading.value = true
    loadError.value = null
    try {
      settings.value = await settingsApi.get()
    } catch (error: any) {
      loadError.value = error.message || '加载设置失败，请检查后端服务'
      console.error('加载设置失败:', error)
    } finally {
      isLoading.value = false
    }
  }

  // 更新设置
  async function updateSettings(newSettings: Settings) {
    await settingsApi.update(newSettings)
    settings.value = newSettings
  }

  return {
    settings,
    isLoading,
    loadError,
    loadSettings,
    updateSettings,
  }
})
