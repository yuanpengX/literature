/**
 * 与 Android LiteratureApi + ApiV1Paths 对齐；根地址勿含 /api/v1（路径见 ./api-paths.js）
 * 小程序：微信登录后使用 Authorization Bearer；不再发送本地随机 X-User-Id
 * 内置默认与 android/.../strings.xml 中 api_base_url 保持一致（修改时请两处同步）
 */
const paths = require('./api-paths.js')
const DEFAULT_BASE_URL = 'https://cppteam.cn'
const TOKEN_KEY = 'mp_access_token'
const STORAGE_USE_SERVER_IP = 'api_use_server_ip'
const STORAGE_IP_BASE_CACHED = 'api_http_ip_base_cached'
/** 文献 API：Feed 可能含多轮服务端 LLM，默认 60s 易误判为失败 */
const WX_REQUEST_TIMEOUT_MS = 120000

function isLikelyTransportLayerFailure(errMsg, errno) {
  const s = String(errMsg || '')
  if (errno === 600001 || errno === -118) return true
  if (
    /ERR_CONNECTION|CONNECTION_RESET|CONNECTION_REFUSED|ENOTFOUND|Failed to connect|无法连接|网络连接失败|net::ERR_/i.test(
      s,
    )
  ) {
    return true
  }
  if (/timeout|超时|TIMED_OUT/i.test(s) && /net::|ERR_CONNECTION|ERR_TIMED_OUT/i.test(s)) return true
  return false
}

/**
 * @param {object} opts
 * @param {string} opts.url
 * @param {string} [opts.method]
 * @param {object} [opts.header]
 * @param {*} [opts.data]
 * @param {number} [opts.timeout]
 */
function wxLiteratureRequest(opts) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: opts.url,
      method: opts.method || 'GET',
      data: opts.data,
      header: opts.header || {},
      timeout: opts.timeout != null ? opts.timeout : WX_REQUEST_TIMEOUT_MS,
      success: resolve,
      fail: reject,
    })
  })
}

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
  function loginWithBase(base) {
    if (!base) {
      return Promise.reject(new Error('文献 API 根地址无效'))
    }
    const url = joinLiteratureApiUrl(base, paths.AUTH_WECHAT_LOGIN)
    return wxLiteratureRequest({
      url,
      method: 'POST',
      header: { 'Content-Type': 'application/json' },
      data: { code },
    }).then((res) => {
      if (res.statusCode >= 200 && res.statusCode < 300) {
        return res.data
      }
      const d = res.data
      const msg =
        (d && (d.detail || d.message)) || res.errMsg || 'HTTP ' + res.statusCode
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    })
  }
  const primary = getBaseUrl()
  return loginWithBase(primary).catch((err) => {
    const isWx = !!(err && typeof err === 'object' && err.errMsg)
    if (
      !isWx ||
      !getUseServerIp() ||
      !isLikelyTransportLayerFailure(err.errMsg, err.errno)
    ) {
      return Promise.reject(err)
    }
    const ipB = canonicalizeLiteratureApiBase(getCachedServerIpBase())
    const dom = getDomainBaseUrl()
    if (!ipB || !dom || primary !== ipB || dom === ipB) {
      return Promise.reject(err)
    }
    setUseServerIp(false)
    return loginWithBase(dom)
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

/** 域名模式下的根地址（用于拉取 /config/client；不受「直连开关」影响） */
function getDomainBaseUrl() {
  const raw = getBaseUrlRaw() || DEFAULT_BASE_URL
  return canonicalizeLiteratureApiBase(raw) || canonicalizeLiteratureApiBase(DEFAULT_BASE_URL) || ''
}

function getUseServerIp() {
  try {
    return !!wx.getStorageSync(STORAGE_USE_SERVER_IP)
  } catch (e) {
    return false
  }
}

function setUseServerIp(on) {
  wx.setStorageSync(STORAGE_USE_SERVER_IP, !!on)
}

function getCachedServerIpBase() {
  try {
    return wx.getStorageSync(STORAGE_IP_BASE_CACHED) || ''
  } catch (e) {
    return ''
  }
}

function setCachedServerIpBase(url) {
  const n = url && String(url).trim() ? canonicalizeLiteratureApiBase(String(url).trim()) : ''
  wx.setStorageSync(STORAGE_IP_BASE_CACHED, n)
}

/**
 * 使用当前域名根请求公开接口，写入缓存并返回规范化根地址。
 * @param {string} [domainRoot] 省略则用 getDomainBaseUrl()
 */
function fetchServerHttpIpBase(domainRoot) {
  const base = canonicalizeLiteratureApiBase(domainRoot || getDomainBaseUrl())
  if (!base) {
    return Promise.reject(new Error('域名根地址无效'))
  }
  const url = joinLiteratureApiUrl(base, paths.CONFIG_CLIENT)
  return wxLiteratureRequest({
    url,
    method: 'GET',
    header: { 'Content-Type': 'application/json' },
  }).then((res) => {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      const raw = res.data && res.data.http_ip_base
      const n = canonicalizeLiteratureApiBase(raw)
      if (n) {
        setCachedServerIpBase(n)
        return n
      }
      throw new Error('服务端未配置 LITERATURE_HTTP_IP_BASE')
    }
    const d = res.data
    const msg = (d && (d.detail || d.message)) || 'HTTP ' + res.statusCode
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  })
}

function getBaseUrl() {
  if (getUseServerIp()) {
    const n = canonicalizeLiteratureApiBase(getCachedServerIpBase())
    if (n) return n
  }
  return getDomainBaseUrl()
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

/** 微信常见拦截文案 → 可操作的排查提示（与 Network 里 0 B / failed 对应） */
function wxRequestFailHints(errMsg, fullUrl) {
  const s = String(errMsg || '')
  const parts = []
  if (/domain list|合法域名|url not in domain|不在以下 request/i.test(s)) {
    parts.push(
      '公众平台「开发 → 开发管理 → 服务器域名」将 ' +
        (fullUrl ? String(fullUrl).replace(/^https?:\/\/([^/]+).*/i, '$1') : 'API 域名') +
        ' 加入 request 合法域名',
    )
    parts.push('开发者工具：右上角「详情 → 本地设置」勾选「不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书」')
  }
  if (/ssl|certificate|证书|handshake|TLS|tls/i.test(s)) {
    parts.push('检查服务器 HTTPS 证书是否完整、是否被系统信任（勿用自签证书在未勾选不校验的环境）')
  }
  if (/timeout|超时/i.test(s)) {
    if (/ERR_CONNECTION|net::ERR_CONNECTION|TIMED_OUT.*CONNECTION|连接超时/i.test(s)) {
      parts.push(
        '连接阶段超时：多为 DNS、运营商网络、安全组未放行 443，或服务端直连基址失效；可关闭直连开关仅用 HTTPS 域名',
      )
    } else {
      parts.push('若已能打开 /health：可能是单次请求耗时过长（如 Feed 多轮摘要），已延长客户端超时，仍失败可稍后再试')
    }
  }
  if (/^http:\/\//i.test(String(fullUrl || ''))) {
    parts.push('真机与体验版必须使用 HTTPS（默认 443），勿用纯 HTTP')
  }
  return parts
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

function request(path, method, data, retry401, reqExtra) {
  const extra = reqExtra || {}
  const base = extra.baseOverride != null ? extra.baseOverride : getBaseUrl()
  if (!base) {
    return Promise.reject(new Error('文献 API 根地址无效'))
  }
  const url = joinLiteratureApiUrl(base, path)
  const usedDomainAfterIpFail = !!extra.usedDomainAfterIpFail

  const exec = () =>
    wxLiteratureRequest({
      url,
      method: method || 'GET',
      data: data,
      header: buildAuthHeaders(),
    })
      .then((res) => {
        if (res.statusCode === 401 && getToken() && !retry401) {
          clearToken()
          return bootstrapWechatLogin()
            .then(() => request(path, method, data, true))
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          if (usedDomainAfterIpFail) {
            setUseServerIp(false)
          }
          return res.data
        }
        const d = res.data
        const msg =
          (d && (d.detail || d.message)) || res.errMsg || 'HTTP ' + res.statusCode
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
      })
      .catch((err) => {
        const raw = (err && err.errMsg) || String(err || '网络错误')
        const errno = err && err.errno
        const isWxRequestFail = !!(err && typeof err === 'object' && err.errMsg)
        if (
          isWxRequestFail &&
          !usedDomainAfterIpFail &&
          getUseServerIp() &&
          isLikelyTransportLayerFailure(raw, errno)
        ) {
          const ipB = canonicalizeLiteratureApiBase(getCachedServerIpBase())
          const dom = getDomainBaseUrl()
          if (ipB && dom && base === ipB && dom !== ipB) {
            return request(path, method, data, retry401, {
              baseOverride: dom,
              usedDomainAfterIpFail: true,
            })
          }
        }
        let msg = humanizeSystemConnectMsg(raw)
        if (errno != null && String(errno) !== '') {
          msg += ' (errno:' + errno + ')'
        }
        const hints = wxRequestFailHints(raw, url)
        if (raw.indexOf('fail') !== -1 || raw === 'request:fail') {
          hints.push('确认 API 根地址在「设置」中为 https://你的域名（无 /api/v1 后缀）')
          hints.push('确认服务器与防火墙已放行 443，本机可先用浏览器打开同域名 /health')
        }
        if (hints.length) {
          msg += ' — ' + hints.join('；')
        }
        return Promise.reject(new Error(msg))
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
  getDomainBaseUrl,
  getUseServerIp,
  setUseServerIp,
  getCachedServerIpBase,
  setCachedServerIpBase,
  fetchServerHttpIpBase,
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
