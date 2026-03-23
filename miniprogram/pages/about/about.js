const PRIVACY = 'http://47.103.51.214/privacy'
const TERMS = 'http://47.103.51.214/terms'

Page({
  copyPrivacy() {
    wx.setClipboardData({ data: PRIVACY })
  },
  copyTerms() {
    wx.setClipboardData({ data: TERMS })
  },
})
