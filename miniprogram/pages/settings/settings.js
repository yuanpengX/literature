const api = require('../../utils/api.js')
const llm = require('../../utils/llm.js')

// 与 Android LlmPresets.all 顺序、文案一致
const PROVIDERS = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'moonshot', label: 'Kimi (Moonshot)' },
  { id: 'custom', label: '自定义 Base URL' },
]

Page({
  data: {
    providers: PROVIDERS,
    providerIndex: 0,
    llmModel: '',
    llmBase: '',
    llmKey: '',
    llmHint: '',
    apiDomainInput: '',
    useServerIp: false,
  },

  onShow() {
    this.setData({
      apiDomainInput: api.getBaseUrlRaw() || '',
      useServerIp: api.getUseServerIp(),
    })
    const c = llm.getLlmConfig()
    const idx = Math.max(0, PROVIDERS.findIndex((p) => p.id === c.providerId))
    const pid = PROVIDERS[idx].id
    this.setData({
      providerIndex: idx,
      llmModel: c.model || llm.defaultModel(pid),
      llmBase: c.baseUrl || '',
      llmKey: c.apiKey || '',
      llmHint: '',
    })
  },

  onProvider(e) {
    const i = parseInt(e.detail.value, 10)
    const id = PROVIDERS[i].id
    this.setData({
      providerIndex: i,
      llmModel: llm.defaultModel(id),
    })
  },

  onModel(e) {
    this.setData({ llmModel: e.detail.value })
  },
  onLlmBase(e) {
    this.setData({ llmBase: e.detail.value })
  },
  onLlmKey(e) {
    this.setData({ llmKey: e.detail.value })
  },

  onApiDomainInput(e) {
    this.setData({ apiDomainInput: e.detail.value })
  },

  saveApiDomain() {
    api.setBaseUrl(this.data.apiDomainInput.trim())
    this.setData({ apiDomainInput: api.getBaseUrlRaw() || '' })
    wx.showToast({ title: '已保存域名', icon: 'success' })
  },

  async onServerIpSwitch(e) {
    const on = e.detail.value
    if (!on) {
      api.setUseServerIp(false)
      this.setData({ useServerIp: false })
      wx.showToast({ title: '已使用域名', icon: 'success' })
      return
    }
    wx.showLoading({ title: '拉取配置…', mask: true })
    try {
      await api.fetchServerHttpIpBase()
      api.setUseServerIp(true)
      this.setData({ useServerIp: true })
      wx.showToast({ title: '已启用直连', icon: 'success' })
    } catch (err) {
      this.setData({ useServerIp: false })
      wx.showToast({
        title: (err && err.message) || '失败',
        icon: 'none',
        duration: 3000,
      })
    } finally {
      wx.hideLoading()
    }
  },

  async refreshServerIp() {
    wx.showLoading({ title: '刷新…', mask: true })
    try {
      await api.fetchServerHttpIpBase()
      wx.showToast({ title: '已更新', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  async saveLlmLocal() {
    const id = PROVIDERS[this.data.providerIndex].id
    llm.setLlmConfig({
      providerId: id,
      baseUrl: this.data.llmBase.trim(),
      apiKey: this.data.llmKey.trim(),
      model: this.data.llmModel.trim(),
    })
    wx.showToast({ title: '已保存本机', icon: 'success' })
    const c = llm.getLlmConfig()
    const key = (c.apiKey || '').trim()
    if (!key) return
    const root = llm.resolveBaseRoot(c.providerId, c.baseUrl)
    if (!root) {
      this.setData({
        llmHint: '已保存本机；自定义模型商需填 Base URL 后再同步服务器',
      })
      return
    }
    const model = (c.model || '').trim() || llm.defaultModel(c.providerId)
    try {
      await api.putLlmCredentials({
        base_url: root,
        api_key: key,
        model,
      })
      this.setData({ llmHint: '已同步到服务器（每日精选 + Feed 摘要）' })
    } catch (e) {
      this.setData({
        llmHint: `已保存本机；同步失败：${e.message || e}`,
      })
    }
  },

  goSub() {
    wx.navigateTo({ url: '/pages/subscriptions/subscriptions' })
  },

  goAbout() {
    wx.navigateTo({ url: '/pages/about/about' })
  },

  async syncLlmServer() {
    const c = llm.getLlmConfig()
    const key = (c.apiKey || '').trim()
    if (!key) {
      wx.showToast({ title: '请先填写 API Key', icon: 'none' })
      return
    }
    const root = llm.resolveBaseRoot(c.providerId, c.baseUrl)
    if (!root) {
      wx.showToast({ title: '自定义模型商需填写 Base URL', icon: 'none' })
      return
    }
    const model = (c.model || '').trim() || llm.defaultModel(c.providerId)
    try {
      await api.putLlmCredentials({
        base_url: root,
        api_key: key,
        model,
      })
      this.setData({ llmHint: '已同步到服务器' })
      wx.showToast({ title: '已同步', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: e.message || '失败', icon: 'none' })
    }
  },

  async clearLlmServer() {
    try {
      await api.deleteLlmCredentials()
      this.setData({ llmHint: '已请求清除服务端 LLM' })
    } catch (e) {
      wx.showToast({ title: e.message || '失败', icon: 'none' })
    }
  },
})
