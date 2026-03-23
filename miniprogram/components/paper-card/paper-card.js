function buildTagChips(p) {
  const tags = (p && p.rank_tags) || []
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
  },
  observers: {
    paper(p) {
      const pick = this.data.pickBlurb
      const fb = (p && p.feed_blurb) || ''
      const summary = pick && String(pick).trim() ? String(pick).trim() : fb
      this.setData({
        tagChips: buildTagChips(p),
        summaryLine: summary,
      })
    },
    pickBlurb(pick) {
      const p = this.data.paper
      const fb = (p && p.feed_blurb) || ''
      const summary = pick && String(pick).trim() ? String(pick).trim() : fb
      this.setData({ summaryLine: summary })
    },
  },
  methods: {
    onTap() {
      const p = this.data.paper
      if (p && p.id != null) {
        this.triggerEvent('open', { id: p.id, paper: p })
      }
    },
  },
})
