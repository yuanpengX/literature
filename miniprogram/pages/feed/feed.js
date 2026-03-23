const api = require('../../utils/api.js')

function matchesChannel(paper, ch) {
  const s = paper.source || ''
  if (ch === 'arxiv') return s === 'arxiv'
  if (ch === 'journal') {
    return s === 'openalex' || s.startsWith('openalex:journal') || s.startsWith('rss:')
  }
  if (ch === 'conference') return s.startsWith('openalex:conference')
  return true
}

Page({
  data: {
    channel: 'arxiv',
    // 默认与旧版后端一致；线上已支持 hot/for_you 时可改为 for_you
    sort: 'recommended',
    items: [],
    nextCursor: null,
    loading: true,
    loadingMore: false,
    error: '',
  },

  onLoad() {
    this.loadFirst(true)
  },

  onChannel(e) {
    const ch = e.currentTarget.dataset.ch
    if (ch === this.data.channel) return
    this.setData({ channel: ch, items: [], nextCursor: null, error: '' })
    this.loadFirst(true)
  },

  onSort(e) {
    const s = e.currentTarget.dataset.sort
    if (!s || s === this.data.sort) return
    this.setData({ sort: s, items: [], nextCursor: null, error: '' })
    this.loadFirst(true)
  },

  async loadFirst(showLoading) {
    if (showLoading) this.setData({ loading: true, error: '' })
    try {
      const res = await api.getFeed(null, 30, this.data.sort, this.data.channel)
      const raw = res.items || []
      const items = raw.filter((p) => matchesChannel(p, this.data.channel))
      this.setData({
        items,
        nextCursor: res.next_cursor || null,
        loading: false,
        error: '',
      })
    } catch (err) {
      this.setData({
        loading: false,
        error: err.message || '加载失败',
      })
    }
    if (showLoading) wx.stopPullDownRefresh()
  },

  async onPullDownRefresh() {
    try {
      await api.requestSubscriptionFetch()
    } catch (e) {}
    await this.loadFirst(true)
  },

  async loadMore() {
    const c = this.data.nextCursor
    if (!c || this.data.loadingMore) return
    this.setData({ loadingMore: true })
    try {
      const res = await api.getFeed(c, 30, this.data.sort, this.data.channel)
      const raw = res.items || []
      const page = raw.filter((p) => matchesChannel(p, this.data.channel))
      const items = this.data.items.concat(page)
      this.setData({
        items,
        nextCursor: res.next_cursor || null,
        loadingMore: false,
      })
    } catch (err) {
      this.setData({ loadingMore: false })
      wx.showToast({ title: err.message || '失败', icon: 'none' })
    }
  },

  onOpenPaper(e) {
    const id = e.detail.id
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id })
  },
})
