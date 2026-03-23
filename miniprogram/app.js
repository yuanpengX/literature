const api = require('./utils/api.js')

App({
  onLaunch() {
    api.ensureUserId()
  },
  globalData: {
    feedReselectCount: 0,
  },
})
