const api = require('../../utils/api.js')

Page({
  data: {
    query: '',
    items: [],
    searched: false,
  },

  onQuery(e) {
    this.setData({ query: e.detail.value })
  },

  async doSearch() {
    const q = (this.data.query || '').trim()
    if (!q) return
    this.setData({ searched: true })
    wx.showLoading({ title: '搜索中' })
    try {
      const res = await api.search(q, 40)
      this.setData({ items: res.items || [] })
    } catch (e) {
      wx.showToast({ title: e.message || '失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  onOpenPaper(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.detail.id })
  },
})
