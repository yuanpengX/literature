const api = require('./utils/api.js')

App({
  onLaunch() {
    api.bootstrapWechatLogin().catch((e) => {
      console.warn('[literature] wechat login skipped:', (e && e.message) || e)
    })
  },
  globalData: {
    feedReselectCount: 0,
  },
})
