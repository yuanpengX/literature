function reasonLabel(rr) {
  if (!rr) return ''
  if (rr === 'trending') return '热'
  if (rr === 'for_you') return '兴趣'
  return rr
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
    reasonLabel: '',
  },
  observers: {
    paper(p) {
      const rr = p && (p.rank_reason || p.rankReason)
      this.setData({ reasonLabel: reasonLabel(rr) })
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
