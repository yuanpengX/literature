const api = require('../../utils/api.js')

function enrichJournal(item, catalog) {
  const preset = catalog && catalog.journals && catalog.journals.find((x) => x.id === item.id)
  const title = preset ? preset.name : item.name || item.id
  const sub = item.rss
    ? item.rss
    : preset
      ? [preset.abbr, preset.issn].filter(Boolean).join(' · ')
      : item.id
  return Object.assign({}, item, { _title: title, _sub: sub })
}

function enrichConf(item, catalog) {
  const preset = catalog && catalog.conferences && catalog.conferences.find((x) => x.id === item.id)
  const title = preset ? preset.name : item.name || item.id
  const oid =
    item.openalex_source_id ||
    (preset && preset.openalex_source_id) ||
    ''
  const line = oid ? 'OpenAlex: ' + oid : ''
  return Object.assign({}, item, { _title: title, _oid: line })
}

Page({
  data: {
    subTab: 0,
    catalog: null,
    keywords: [],
    journals: [],
    conferences: [],
    loadErr: '',
    hint: '',
    saving: false,
    newKw: '',
    showMj: false,
    mjName: '',
    mjRss: '',
    showMc: false,
    mcName: '',
    mcOid: '',
  },

  noop() {},

  async onLoad() {
    this.setData({ loadErr: '' })
    try {
      const [cat, me] = await Promise.all([
        api.getSubscriptionCatalog(),
        api.getMySubscriptions(),
      ])
      const journals = (me.journals || []).map((j) => enrichJournal(j, cat))
      const conferences = (me.conferences || []).map((c) => enrichConf(c, cat))
      this.setData({
        catalog: cat,
        keywords: me.keywords || [],
        journals,
        conferences,
      })
    } catch (e) {
      this.setData({ loadErr: e.message || '加载失败' })
    }
  },

  setTab(e) {
    this.setData({ subTab: parseInt(e.currentTarget.dataset.i, 10) })
  },

  pickCatalogJournal() {
    const cat = this.data.catalog
    if (!cat || !cat.journals) return
    const existing = new Set(this.data.journals.map((x) => x.id))
    const choices = cat.journals.filter((j) => !existing.has(j.id))
    if (!choices.length) {
      wx.showToast({ title: '已全部添加', icon: 'none' })
      return
    }
    const names = choices.map((j) => j.name)
    wx.showActionSheet({
      itemList: names.slice(0, 20),
      success: (res) => {
        const j = choices[res.tapIndex]
        if (!j) return
        const item = enrichJournal({ id: j.id, enabled: true }, cat)
        this.setData({ journals: this.data.journals.concat([item]) })
      },
    })
  },

  pickCatalogConf() {
    const cat = this.data.catalog
    if (!cat || !cat.conferences) return
    const existing = new Set(this.data.conferences.map((x) => x.id))
    const choices = cat.conferences.filter((c) => !existing.has(c.id))
    if (!choices.length) {
      wx.showToast({ title: '已全部添加', icon: 'none' })
      return
    }
    const names = choices.map((c) => c.name)
    wx.showActionSheet({
      itemList: names.slice(0, 20),
      success: (res) => {
        const c = choices[res.tapIndex]
        if (!c) return
        const item = enrichConf({ id: c.id, enabled: true }, cat)
        this.setData({ conferences: this.data.conferences.concat([item]) })
      },
    })
  },

  openMj() {
    this.setData({ showMj: true, mjName: '', mjRss: '' })
  },
  closeMj() {
    this.setData({ showMj: false })
  },
  eMjName(e) {
    this.setData({ mjName: e.detail.value })
  },
  eMjRss(e) {
    this.setData({ mjRss: e.detail.value })
  },
  confirmMj() {
    const rss = (this.data.mjRss || '').trim()
    const name = (this.data.mjName || '').trim() || rss.slice(0, 40)
    if (!rss.startsWith('http://') && !rss.startsWith('https://')) {
      this.setData({ hint: 'RSS 须以 http(s):// 开头' })
      return
    }
    const id = 'u:j:' + Math.random().toString(36).slice(2, 10)
    const cat = this.data.catalog
    const item = enrichJournal({ id, enabled: true, name, rss }, cat)
    this.setData({
      journals: this.data.journals.concat([item]),
      showMj: false,
      hint: '已添加，请保存',
    })
  },

  openMc() {
    this.setData({ showMc: true, mcName: '', mcOid: '' })
  },
  closeMc() {
    this.setData({ showMc: false })
  },
  eMcName(e) {
    this.setData({ mcName: e.detail.value })
  },
  eMcOid(e) {
    this.setData({ mcOid: e.detail.value })
  },
  confirmMc() {
    const oid = (this.data.mcOid || '').trim()
    if (!oid) {
      this.setData({ hint: '请填写 Source ID' })
      return
    }
    const id = 'u:c:' + Math.random().toString(36).slice(2, 10)
    const name = (this.data.mcName || '').trim() || oid
    const cat = this.data.catalog
    const item = enrichConf(
      { id, enabled: true, name, openalex_source_id: oid },
      cat,
    )
    this.setData({
      conferences: this.data.conferences.concat([item]),
      showMc: false,
      hint: '已添加，请保存',
    })
  },

  toggleJournal(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.journals.slice()
    list[i] = Object.assign({}, list[i], { enabled: e.detail.value })
    list[i] = enrichJournal(list[i], this.data.catalog)
    this.setData({ journals: list })
  },

  delJournal(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.journals.slice()
    list.splice(i, 1)
    this.setData({ journals: list })
  },

  toggleConf(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.conferences.slice()
    list[i] = Object.assign({}, list[i], { enabled: e.detail.value })
    list[i] = enrichConf(list[i], this.data.catalog)
    this.setData({ conferences: list })
  },

  delConf(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.conferences.slice()
    list.splice(i, 1)
    this.setData({ conferences: list })
  },

  onNewKw(e) {
    this.setData({ newKw: e.detail.value })
  },

  addKw() {
    const t = (this.data.newKw || '').trim()
    if (!t) return
    const keywords = this.data.keywords.concat([{ text: t, enabled: true }])
    this.setData({ keywords, newKw: '' })
  },

  toggleKw(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.keywords.slice()
    list[i] = Object.assign({}, list[i], { enabled: e.detail.value })
    this.setData({ keywords: list })
  },

  delKw(e) {
    const i = parseInt(e.currentTarget.dataset.i, 10)
    const list = this.data.keywords.slice()
    list.splice(i, 1)
    this.setData({ keywords: list })
  },

  restoreDefaults() {
    const c = this.data.catalog
    if (!c) return
    const journals = (c.default_journals || []).map((j) => enrichJournal(j, c))
    const conferences = (c.default_conferences || []).map((x) => enrichConf(x, c))
    this.setData({
      keywords: (c.default_keywords || []).slice(),
      journals,
      conferences,
      hint: '已填入推荐配置，请保存',
    })
  },

  stripUi(arr) {
    return (arr || []).map((x) => {
      const o = Object.assign({}, x)
      delete o._title
      delete o._sub
      delete o._oid
      return o
    })
  },

  async save() {
    this.setData({ saving: true, hint: '' })
    try {
      const body = {
        keywords: this.stripUi(this.data.keywords),
        journals: this.stripUi(this.data.journals),
        conferences: this.stripUi(this.data.conferences),
      }
      await api.putMySubscriptions(body)
      this.setData({ hint: '已保存', saving: false })
      wx.showToast({ title: '已保存', icon: 'success' })
    } catch (e) {
      this.setData({ saving: false, hint: e.message || '失败' })
      wx.showToast({ title: e.message || '失败', icon: 'none' })
    }
  },
})
