// 卡片仅展示服务端 LLM（feed_blurb / pick_blurb），不用英文摘要启发式

function buildTagChips(p) {
  const tags = (p && p.rank_tags) || (p && p.rankTags) || []
  const out = []
  if (tags.indexOf('trending') !== -1) out.push({ text: '热', cls: 'tag-hot' })
  if (tags.indexOf('fresh') !== -1) out.push({ text: '新', cls: 'tag-new' })
  if (out.length) return out
  const rr = p && (p.rank_reason || p.rankReason)
  if (rr === 'trending') return [{ text: '热', cls: 'tag-hot' }]
  if (rr === 'for_you') return [{ text: '兴趣', cls: 'tag-hot' }]
  if (rr) return [{ text: String(rr), cls: 'tag-muted' }]
  return []
}

Component({
  properties: {
    paper: {
      type: Object,
      value: {},
    },
    position: {
      type: Number,
      value: 0,
    },
    pickBlurb: {
      type: String,
      value: '',
    },
  },
  data: {
    tagChips: [],
    summaryLine: '',
    starsFilled: '',
    starsEmpty: '',
  },
  lifetimes: {
    attached() {
      this._syncFromProps()
    },
    ready() {
      this._syncFromProps()
    },
  },
  observers: {
    'paper, pickBlurb': function () {
      this._syncFromProps()
    },
  },
  methods: {
    _syncFromProps() {
      const p = this.properties.paper || {}
      const pickRaw = this.properties.pickBlurb
      const pickStr = pickRaw != null && String(pickRaw).trim() ? String(pickRaw).trim() : ''
      const fb = (p.feed_blurb != null && String(p.feed_blurb).trim()
        ? String(p.feed_blurb).trim()
        : '') ||
        (p.feedBlurb != null && String(p.feedBlurb).trim() ? String(p.feedBlurb).trim() : '')
      const summary = pickStr || fb
      const rawStars = p.read_value_stars != null ? p.read_value_stars : p.readValueStars
      const n = rawStars != null && rawStars !== '' ? parseInt(rawStars, 10) : NaN
      const starN = Number.isFinite(n) ? Math.min(5, Math.max(1, n)) : 3
      this.setData({
        tagChips: buildTagChips(p),
        summaryLine: summary,
        starsFilled: '\u2605'.repeat(starN),
        starsEmpty: '\u2606'.repeat(5 - starN),
      })
    },
    onTap() {
      const p = this.properties.paper
      if (p && p.id != null) {
        this.triggerEvent('open', { id: p.id, paper: p })
      }
    },
  },
})
