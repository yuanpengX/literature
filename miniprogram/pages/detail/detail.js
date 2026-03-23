const api = require('../../utils/api.js')
const { stripHtmlToPlain } = require('../../utils/textPlain.js')
const fav = require('../../utils/favorites.js')
const llm = require('../../utils/llm.js')

Page({
  data: {
    paperId: 0,
    paper: null,
    loading: true,
    err: '',
    isFavorite: false,
    aiSummary: '',
    aiLoading: false,
    aiError: '',
    abstractPlain: '',
  },

  onLoad(options) {
    const id = parseInt(options.id, 10)
    if (!id) {
      this.setData({ loading: false, err: '无效 id' })
      return
    }
    this.setData({ paperId: id })
    this.loadPaper(id)
  },

  async loadPaper(id) {
    this.setData({ loading: true, err: '', aiSummary: '', aiError: '' })
    try {
      const p = await api.getPaper(id)
      this.setData({
        paper: p,
        abstractPlain: stripHtmlToPlain((p && p.abstract) || ''),
        loading: false,
        isFavorite: fav.isFavorite(id),
      })
    } catch (e) {
      this.setData({ loading: false, err: e.message || '加载失败' })
    }
  },

  onFavoriteTap() {
    const p = this.data.paper
    if (!p) return
    const next = fav.toggle(p)
    this.setData({ isFavorite: next })
    wx.showToast({ title: next ? '已收藏' : '已取消', icon: 'none' })
  },

  genAi() {
    const p = this.data.paper
    if (!p) return
    this.setData({ aiLoading: true, aiError: '' })
    llm.summarizePaperChinese(p.title, stripHtmlToPlain(p.abstract || ''), (err, text) => {
      this.setData({
        aiLoading: false,
        aiError: err ? err.message || String(err) : '',
        aiSummary: text || '',
      })
    })
  },

  copyPdf() {
    const u = this.data.paper && this.data.paper.pdf_url
    if (!u) return
    wx.setClipboardData({ data: u })
  },

  copyHtml() {
    const u = this.data.paper && this.data.paper.html_url
    if (!u) return
    wx.setClipboardData({ data: u })
  },
})
