const PRIVACY = 'https://example.com/privacy'
const TERMS = 'https://example.com/terms'

Page({
  copyPrivacy() {
    wx.setClipboardData({ data: PRIVACY })
  },
  copyTerms() {
    wx.setClipboardData({ data: TERMS })
  },
})
