const api = require('../../utils/api.js')

function normalizeDailyItems(raw) {
  const list = Array.isArray(raw) ? raw : []
  return list.map((row) => {
    if (row && row.paper) return row
    return { paper: row, pick_blurb: '' }
  })
}

Page({
  data: {
    loading: true,
    items: [],
    pickDate: '',
    note: '',
    error: '',
    serverLlm: false,
    runLoading: false,
    subscriptionKeywords: [],
  },

  onShow() {
    this.load()
  },

  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const r = await api.getDailyPicks()
      const kws = r.subscription_keywords || []
      this.setData({
        items: normalizeDailyItems(r.items),
        pickDate: r.date || '',
        note: r.note || '',
        error: r.error || '',
        serverLlm: !!r.server_llm_configured,
        subscriptionKeywords: Array.isArray(kws) ? kws : [],
        loading: false,
      })
    } catch (e) {
      this.setData({ loading: false, error: e.message || '加载失败' })
    }
    wx.stopPullDownRefresh()
  },

  onPullDownRefresh() {
    this.load()
  },

  async runNow() {
    this.setData({ runLoading: true })
    try {
      const r = await api.runDailyPicksNow()
      const kws = r.subscription_keywords || []
      this.setData({
        items: normalizeDailyItems(r.items),
        pickDate: r.date || '',
        note: r.note || '',
        error: r.error || '',
        serverLlm: !!r.server_llm_configured,
        subscriptionKeywords: Array.isArray(kws) ? kws : [],
        runLoading: false,
      })
      wx.showToast({ title: '已更新', icon: 'success' })
    } catch (e) {
      this.setData({ runLoading: false })
      wx.showToast({ title: e.message || '失败', icon: 'none' })
    }
  },

  onOpenPaper(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.detail.id })
  },
})
