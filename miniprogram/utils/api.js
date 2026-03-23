/**
 * 与 Android LiteratureApi 对齐；Base URL 勿含 /api/v1
 */
const DEFAULT_BASE_URL = 'https://example.com'

function ensureUserId() {
  let id = wx.getStorageSync('user_id')
  if (!id) {
    id = 'u-' + Math.random().toString(36).slice(2, 14)
    wx.setStorageSync('user_id', id)
  }
  return id
}

function getBaseUrlRaw() {
  const u = wx.getStorageSync('api_base_url')
  if (u && String(u).trim()) return String(u).trim()
  return DEFAULT_BASE_URL
}

function normalizeBaseUrl(raw) {
  let s = String(raw || '').trim().replace(/\/+$/, '')
  while (s.length) {
    const l = s.toLowerCase()
    if (l.endsWith('/api/v1')) {
      s = s.slice(0, -7).replace(/\/+$/, '')
      continue
    }
    if (l.endsWith('/api/v2')) {
      s = s.slice(0, -7).replace(/\/+$/, '')
      continue
    }
    break
  }
  return s.replace(/\/+$/, '')
}

function getBaseUrl() {
  return normalizeBaseUrl(getBaseUrlRaw())
}

function setBaseUrl(url) {
  const n = url && String(url).trim() ? normalizeBaseUrl(url) : ''
  wx.setStorageSync('api_base_url', n)
}

function request(path, method, data) {
  const base = getBaseUrl()
  if (!base || base === 'https://example.com') {
    return Promise.reject(new Error('请先在「设置」填写文献 API 根地址'))
  }
  const url = base + path
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: method || 'GET',
      data: method === 'GET' ? data : data,
      header: {
        'Content-Type': 'application/json',
        'X-User-Id': ensureUserId(),
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const d = res.data
          const msg =
            (d && (d.detail || d.message)) ||
            res.errMsg ||
            'HTTP ' + res.statusCode
          reject(new Error(typeof msg === 'string' ? msg : JSON.stringify(msg)))
        }
      },
      fail(err) {
        reject(new Error(err.errMsg || '网络错误'))
      },
    })
  })
}

function getFeed(cursor, limit, sort, channel) {
  const q = {}
  if (cursor) q.cursor = cursor
  if (limit) q.limit = limit
  if (sort) q.sort = sort
  if (channel) q.channel = channel
  return request('/api/v1/feed', 'GET', q)
}

function search(q, limit) {
  return request('/api/v1/search', 'GET', { q, limit: limit || 40 })
}

function getPaper(id) {
  return request('/api/v1/papers/' + id, 'GET')
}

function getDailyPicks(date) {
  const q = {}
  if (date) q.date = date
  return request('/api/v1/daily-picks/me', 'GET', q)
}

function runDailyPicksNow() {
  return request('/api/v1/daily-picks/me/run', 'POST', {})
}

function putLlmCredentials(body) {
  return request('/api/v1/users/me/llm', 'PUT', body)
}

function deleteLlmCredentials() {
  return request('/api/v1/users/me/llm', 'DELETE')
}

function getSubscriptionCatalog() {
  return request('/api/v1/subscriptions/catalog', 'GET')
}

function getMySubscriptions() {
  return request('/api/v1/users/me/subscriptions', 'GET')
}

function putMySubscriptions(body) {
  return request('/api/v1/users/me/subscriptions', 'PUT', body)
}

function requestSubscriptionFetch() {
  return request('/api/v1/users/me/subscriptions/fetch-now', 'GET')
}

function postEvents(events) {
  return request('/api/v1/events', 'POST', { events })
}

module.exports = {
  ensureUserId,
  getBaseUrl,
  setBaseUrl,
  getBaseUrlRaw,
  normalizeBaseUrl,
  DEFAULT_BASE_URL,
  getFeed,
  search,
  getPaper,
  getDailyPicks,
  runDailyPicksNow,
  putLlmCredentials,
  deleteLlmCredentials,
  getSubscriptionCatalog,
  getMySubscriptions,
  putMySubscriptions,
  requestSubscriptionFetch,
  postEvents,
}
