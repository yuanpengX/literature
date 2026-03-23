const fav = require('../../utils/favorites.js')

function toCardPaper(row) {
  return {
    id: row.id,
    external_id: row.external_id,
    title: row.title,
    abstract: row.abstract,
    pdf_url: row.pdf_url,
    html_url: row.html_url,
    source: row.source,
    primary_category: row.primary_category,
    published_at: row.published_at,
    hot_score: row.hot_score || 0,
    rank_reason: row.rank_reason,
    citation_count: row.citation_count || 0,
  }
}

Page({
  data: {
    items: [],
  },

  onShow() {
    const rows = fav.listPapers()
    this.setData({ items: rows.map(toCardPaper) })
  },

  onOpenPaper(e) {
    wx.navigateTo({ url: '/pages/detail/detail?id=' + e.detail.id })
  },
})
