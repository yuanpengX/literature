/** 与 Android strings.xml 的 url_privacy_policy / url_terms 保持一致 */
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
