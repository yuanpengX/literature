const api = require('../../utils/api.js')
const {
  heuristicBlurbFromAbstract,
  heuristicBlurbFromTitle,
  isRedundantBlurb,
  stripHtmlToPlain,
} = require('../../utils/textPlain.js')

function matchesChannel(paper, ch) {
  const s = paper.source || ''
  if (ch === 'arxiv') return s === 'arxiv'
  if (ch === 'journal') {
    return s === 'openalex' || s.startsWith('openalex:journal') || s.startsWith('rss:')
  }
  if (ch === 'conference') return s.startsWith('openalex:conference')
  return true
}

/** 规范化 API 字段并兜底一句话（避免组件 observer 未触发或旧接口缺 feed_blurb） */
function normalizeFeedPaper(p) {
  if (!p || typeof p !== 'object') return p
  const fb0 = (p.feed_blurb || p.feedBlurb || '').trim()
  let fb =
    fb0 ||
    heuristicBlurbFromAbstract(p.abstract || '') ||
    heuristicBlurbFromTitle(p.title || '')
  const abstPlain = stripHtmlToPlain(p.abstract || '')
  if (isRedundantBlurb(fb, abstPlain)) {
    fb = ''
  }
  const rawStars = p.read_value_stars != null ? p.read_value_stars : p.readValueStars
  const rs = rawStars != null && rawStars !== '' ? parseInt(rawStars, 10) : NaN
  const readValueStars = Number.isFinite(rs) ? Math.min(5, Math.max(1, rs)) : 3
  return Object.assign({}, p, {
    feed_blurb: fb,
    read_value_stars: readValueStars,
    authors_text: p.authors_text != null ? p.authors_text : p.authorsText || '',
    rank_tags: p.rank_tags != null ? p.rank_tags : p.rankTags || [],
  })
}

Page({
  data: {
    channel: 'arxiv',
    sort: 'recommended',
    items: [],
    nextCursor: null,
    loading: true,
    loadingMore: false,
    error: '',
    showBackTop: false,
  },

  onLoad() {
    api.ensureLoginAttempted().then(
      () => this.loadFirst(true),
      () => this.loadFirst(true),
    )
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
      const items = raw
        .map(normalizeFeedPaper)
        .filter((p) => matchesChannel(p, this.data.channel))
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

  onPageScroll(e) {
    const st = (e && e.scrollTop) || 0
    const show = st > 480
    if (show !== this.data.showBackTop) {
      this.setData({ showBackTop: show })
    }
  },

  onBackTop() {
    wx.pageScrollTo({ scrollTop: 0, duration: 280 })
  },

  async onPullDownRefresh() {
    try {
      await api.requestSubscriptionFetch(this.data.channel)
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
      const page = raw
        .map(normalizeFeedPaper)
        .filter((p) => matchesChannel(p, this.data.channel))
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
