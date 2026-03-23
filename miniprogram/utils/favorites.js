/** 本地收藏：与 Android Room favorites 行为对齐（仅存本机） */
const KEY = 'favorite_papers_v1'

function loadMap() {
  try {
    const raw = wx.getStorageSync(KEY)
    if (raw && typeof raw === 'object') return raw
  } catch (e) {}
  return {}
}

function saveMap(m) {
  wx.setStorageSync(KEY, m)
}

function isFavorite(paperId) {
  const m = loadMap()
  return !!m[String(paperId)]
}

function toggle(paper) {
  const id = String(paper.id)
  const m = loadMap()
  if (m[id]) {
    delete m[id]
    saveMap(m)
    return false
  }
  m[id] = {
    id: paper.id,
    external_id: paper.external_id,
    title: paper.title,
    abstract: paper.abstract,
    pdf_url: paper.pdf_url,
    html_url: paper.html_url,
    source: paper.source,
    primary_category: paper.primary_category,
    published_at: paper.published_at,
    hot_score: paper.hot_score,
    rank_reason: paper.rank_reason,
    citation_count: paper.citation_count,
    savedAt: Date.now(),
  }
  saveMap(m)
  return true
}

function listPapers() {
  const m = loadMap()
  return Object.values(m).sort((a, b) => (b.savedAt || 0) - (a.savedAt || 0))
}

module.exports = { isFavorite, toggle, listPapers }
