const PRIVACY = 'https://cppteam.cn/privacy'
const TERMS = 'https://cppteam.cn/terms'

Page({
  copyPrivacy() {
    wx.setClipboardData({ data: PRIVACY })
  },
  copyTerms() {
    wx.setClipboardData({ data: TERMS })
  },
})
