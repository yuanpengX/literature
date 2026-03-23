/**
 * 与 Android LiteratureApi + ApiV1Paths 对齐；根地址勿含 /api/v1（路径见 ./api-paths.js）
 * 小程序：微信登录后使用 Authorization Bearer；不再发送本地随机 X-User-Id
 * 内置默认与 android/.../strings.xml 中 api_base_url 保持一致（修改时请两处同步）
 */
const paths = require('./api-paths.js')
const DEFAULT_BASE_URL = 'https://cppteam.cn'
const TOKEN_KEY = 'mp_access_token'

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || ''
}

function setToken(t) {
  wx.setStorageSync(TOKEN_KEY, t || '')
}

function clearToken() {
  try {
    wx.removeStorageSync(TOKEN_KEY)
  } catch (e) {
    /* ignore */
  }
}

function wxLoginCode() {
  return new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (res.code) resolve(res.code)
        else reject(new Error('wx.login 未返回 code'))
      },
      fail: reject,
    })
  })
}

/** 不带鉴权头，仅用于登录 */
function postWechatLogin(code) {
  const base = getBaseUrl()
  if (!base) {
    return Promise.reject(new Error('文献 API 根地址无效'))
  }
  const url = joinLiteratureApiUrl(base, paths.AUTH_WECHAT_LOGIN)
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { code },
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
        reject(new Error((err && err.errMsg) || '网络错误'))
      },
    })
  })
}

let _bootstrapPromise = null

/**
 * 启动时调用：wx.login → 服务端换 JWT。失败时不弹窗（便于未配微信密钥的开发环境）。
 * 已有 token 时立即 resolve。并发只发起一次登录请求。
 */
function bootstrapWechatLogin() {
  if (getToken()) {
    return Promise.resolve({ cached: true })
  }
  if (_bootstrapPromise) {
    return _bootstrapPromise
  }
  _bootstrapPromise = wxLoginCode()
    .then((code) => postWechatLogin(code))
    .then((data) => {
      const tok = data && data.access_token
      if (tok) {
        setToken(tok)
        try {
          wx.removeStorageSync('user_id')
        } catch (e) {
          /* ignore */
        }
      }
      return data
    })
    .finally(() => {
      _bootstrapPromise = null
    })
  return _bootstrapPromise
}

/** 无 token 时先尝试登录，避免首屏请求落到 anonymous */
function ensureLoginAttempted() {
  if (getToken()) return Promise.resolve()
  return bootstrapWechatLogin().catch(() => {})
}

function buildAuthHeaders() {
  const headers = { 'Content-Type': 'application/json' }
  const tok = getToken()
  if (tok) {
    headers.Authorization = 'Bearer ' + tok
  }
  return headers
}

/** 用户覆盖项（同 Android AppPrefs.getApiBaseUrl）；为空表示使用 DEFAULT_BASE_URL */
function getBaseUrlRaw() {
  const u = wx.getStorageSync('api_base_url')
  return u && String(u).trim() ? String(u).trim() : ''
}

function stripApiVersionSuffix(s) {
  let x = String(s || '').trim().replace(/\/+$/, '')
  while (x.length) {
    const l = x.toLowerCase()
    if (l.endsWith('/api/v1')) {
      x = x.slice(0, -7).replace(/\/+$/, '')
      continue
    }
    if (l.endsWith('/api/v2')) {
      x = x.slice(0, -7).replace(/\/+$/, '')
      continue
    }
    break
  }
  return x.replace(/\/+$/, '')
}

/**
 * 文献 API 根地址：仅保留 origin（协议+主机+端口），去掉误粘贴路径、重复 scheme、默认端口表现一。
 * 与 Android AppPrefs.normalizeApiBaseUrl 行为对齐。
 */
function canonicalizeLiteratureApiBase(raw) {
  let s = String(raw || '')
    .trim()
    .replace(/\s+/g, '')
  if (!s) return ''
  while (/^https:\/\/https:\/\//i.test(s)) s = s.slice(8)
  while (/^http:\/\/https:\/\//i.test(s)) s = s.slice(7)
  while (/^https:\/\/http:\/\//i.test(s)) s = s.slice(8)
  while (/^http:\/\/http:\/\//i.test(s)) s = s.slice(7)
  if (!/^https?:\/\//i.test(s)) s = 'https://' + s
  try {
    if (typeof URL !== 'undefined') {
      const u = new URL(s)
      if (!u.hostname) return ''
      return stripApiVersionSuffix(u.origin)
    }
  } catch (e) {
    /* fall through */
  }
  const m = s.match(/^(https?:\/\/)([^/?#\s]+)/i)
  if (!m) return ''
  return stripApiVersionSuffix(m[1] + m[2])
}

function normalizeBaseUrl(raw) {
  return canonicalizeLiteratureApiBase(raw)
}

function getBaseUrl() {
  const raw = getBaseUrlRaw() || DEFAULT_BASE_URL
  return canonicalizeLiteratureApiBase(raw) || canonicalizeLiteratureApiBase(DEFAULT_BASE_URL) || ''
}

function setBaseUrl(url) {
  const t = url && String(url).trim() ? String(url).trim() : ''
  const n = t ? canonicalizeLiteratureApiBase(t) : ''
  wx.setStorageSync('api_base_url', n)
}

/** 拼接文献 API 完整 URL，避免双斜杠或漏斜杠 */
function joinLiteratureApiUrl(base, path) {
  const b = String(base || '').replace(/\/+$/, '')
  const p = path && String(path).startsWith('/') ? path : '/' + (path || '')
  return b + p
}

/** OkHttp 风格：Failed to connect to host/ip:port — 斜杠是诊断格式，不是 URL 拼错 */
function humanizeSystemConnectMsg(s) {
  const m = String(s).match(/Failed to connect to\s+([^/\s]+)\/([^:\s]+):(\d+)/i)
  if (m) {
    return (
      '无法连接 ' +
      m[1] +
      '（HTTPS 端口 ' +
      m[3] +
      '）。「' +
      m[1] +
      '/' +
      m[2] +
      '」为系统显示的域名与解析 IP，并非把接口地址拼成「域名/IP」。请检查网络与 443 服务。'
    )
  }
  return s
}

function request(path, method, data, retry401) {
  const base = getBaseUrl()
  if (!base) {
    return Promise.reject(new Error('文献 API 根地址无效'))
  }
  const url = joinLiteratureApiUrl(base, path)
  const exec = () =>
    new Promise((resolve, reject) => {
    wx.request({
      url,
      method: method || 'GET',
      data: method === 'GET' ? data : data,
      header: buildAuthHeaders(),
      success(res) {
        if (res.statusCode === 401 && getToken() && !retry401) {
          clearToken()
          bootstrapWechatLogin()
            .then(() => request(path, method, data, true))
            .then(resolve)
            .catch(reject)
          return
        }
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
        const raw = (err && err.errMsg) || '网络错误'
        const errno = err && err.errno
        let msg = humanizeSystemConnectMsg(raw)
        if (errno != null && String(errno) !== '') {
          msg += ' (errno:' + errno + ')'
        }
        if (raw.indexOf('fail') !== -1 || raw === 'request:fail') {
          const parts = []
          if (/^http:\/\//i.test(url)) parts.push('真机请使用 HTTPS 域名并在公众平台配置 request 合法域名')
          parts.push('开发工具可开「不校验合法域名」')
          parts.push('确认服务已启动且域名解析、防火墙正确')
          msg += ' — ' + parts.join('；')
        }
        reject(new Error(msg))
      },
    })
  })
  if (retry401) {
    return exec()
  }
  return ensureLoginAttempted().then(exec)
}

function getFeed(cursor, limit, sort, channel) {
  const q = {}
  if (cursor) q.cursor = cursor
  if (limit) q.limit = limit
  if (sort) q.sort = sort
  if (channel) q.channel = channel
  return request(paths.FEED, 'GET', q)
}

function search(q, limit) {
  return request(paths.SEARCH, 'GET', { q, limit: limit || 40 })
}

function getPaper(id) {
  return request(paths.paper(id), 'GET')
}

function getDailyPicks(date) {
  const q = {}
  if (date) q.date = date
  return request(paths.DAILY_PICKS_ME, 'GET', q)
}

function runDailyPicksNow() {
  return request(paths.DAILY_PICKS_ME_RUN, 'POST', {})
}

function putPreferences(keywords) {
  return request(paths.USERS_ME_PREFERENCES, 'PUT', { keywords: keywords || '' })
}

function putLlmCredentials(body) {
  return request(paths.USERS_ME_LLM, 'PUT', body)
}

function deleteLlmCredentials() {
  return request(paths.USERS_ME_LLM, 'DELETE')
}

function getSubscriptionCatalog() {
  return request(paths.SUBSCRIPTIONS_CATALOG, 'GET')
}

function getMySubscriptions() {
  return request(paths.USERS_ME_SUBSCRIPTIONS, 'GET')
}

function putMySubscriptions(body) {
  return request(paths.USERS_ME_SUBSCRIPTIONS, 'PUT', body)
}

function requestSubscriptionFetch(channel) {
  const ch = channel && String(channel).trim()
  const q = ch ? { channel: ch } : undefined
  return request(paths.USERS_ME_SUBSCRIPTIONS_FETCH_NOW, 'GET', q)
}

function postEvents(events) {
  return request(paths.EVENTS, 'POST', { events })
}

module.exports = {
  bootstrapWechatLogin,
  ensureLoginAttempted,
  getToken,
  setToken,
  clearToken,
  getBaseUrl,
  setBaseUrl,
  getBaseUrlRaw,
  normalizeBaseUrl,
  canonicalizeLiteratureApiBase,
  joinLiteratureApiUrl,
  DEFAULT_BASE_URL,
  getFeed,
  search,
  getPaper,
  getDailyPicks,
  runDailyPicksNow,
  putPreferences,
  putLlmCredentials,
  deleteLlmCredentials,
  getSubscriptionCatalog,
  getMySubscriptions,
  putMySubscriptions,
  requestSubscriptionFetch,
  postEvents,
}
