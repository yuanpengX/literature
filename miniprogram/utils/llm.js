/**
 * 端上 OpenAI 兼容摘要（与 Android LlmSecureStore + LlmPresets 对齐）
 * 正式环境需在小程序后台配置 request 合法域名（模型商域名）
 */

// 与 android/.../data/llm/LlmPresets.kt 保持同步（修改时请两处对齐）
const PRESETS = {
  deepseek: {
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    defaultModel: 'deepseek-chat',
  },
  moonshot: {
    defaultBaseUrl: 'https://api.moonshot.cn/v1',
    defaultModel: 'moonshot-v1-8k',
  },
  custom: {
    defaultBaseUrl: '',
    defaultModel: 'gpt-4o-mini',
  },
}

function migrateLegacyProviderId() {
  let id = wx.getStorageSync('llm_provider') || 'deepseek'
  if (id === 'openai') {
    const b = (wx.getStorageSync('llm_base_url') || '').trim()
    if (!b) wx.setStorageSync('llm_base_url', 'https://api.openai.com/v1')
    wx.setStorageSync('llm_provider', 'custom')
    id = 'custom'
  }
  if (!PRESETS[id]) {
    id = 'deepseek'
    wx.setStorageSync('llm_provider', id)
  }
  return id
}

function getLlmConfig() {
  const providerId = migrateLegacyProviderId()
  return {
    providerId,
    baseUrl: wx.getStorageSync('llm_base_url') || '',
    apiKey: wx.getStorageSync('llm_api_key') || '',
    model: wx.getStorageSync('llm_model') || '',
  }
}

function setLlmConfig(c) {
  if (c.providerId != null) wx.setStorageSync('llm_provider', c.providerId)
  if (c.baseUrl != null) wx.setStorageSync('llm_base_url', c.baseUrl)
  if (c.apiKey != null) wx.setStorageSync('llm_api_key', c.apiKey)
  if (c.model != null) wx.setStorageSync('llm_model', c.model)
}

function defaultModel(providerId) {
  const p = PRESETS[providerId]
  return (p && p.defaultModel) || PRESETS.deepseek.defaultModel
}

function resolveBaseRoot(providerId, override) {
  const o = (override || '').trim().replace(/\/+$/, '')
  if (o) return o
  const p = PRESETS[providerId] || PRESETS.deepseek
  return (p.defaultBaseUrl || '').trim().replace(/\/+$/, '')
}

function summarizePaperChinese(title, abstract, cb) {
  const { providerId, baseUrl, apiKey, model } = getLlmConfig()
  const key = (apiKey || '').trim()
  if (!key) {
    cb(new Error('请先在设置中填写 API Key'))
    return
  }
  const root = resolveBaseRoot(providerId, baseUrl)
  if (!root) {
    cb(new Error('请填写自定义 Base URL（需指向 OpenAI 兼容 /v1）'))
    return
  }
  const mid = (model || '').trim() || defaultModel(providerId)
  const url = root + '/chat/completions'
  const body = {
    model: mid,
    messages: [
      {
        role: 'system',
        content:
          '你是学术助手。请用简洁中文列出论文要点（条列），不要编造；若摘要为空则说明无法总结。',
      },
      {
        role: 'user',
        content: `标题：${title}\n\n摘要：${abstract || '（无）'}`,
      },
    ],
    temperature: 0.3,
  }
  wx.request({
    url,
    method: 'POST',
    header: {
      'Content-Type': 'application/json',
      Authorization: 'Bearer ' + key,
    },
    data: body,
    success(res) {
      if (res.statusCode !== 200) {
        cb(new Error((res.data && res.data.error && res.data.error.message) || '请求失败'))
        return
      }
      const ch = (res.data.choices && res.data.choices[0]) || {}
      const msg = (ch.message && ch.message.content) || ''
      cb(null, (msg || '').trim())
    },
    fail(err) {
      cb(new Error(err.errMsg || '网络错误'))
    },
  })
}

module.exports = {
  PRESETS,
  getLlmConfig,
  setLlmConfig,
  defaultModel,
  resolveBaseRoot,
  summarizePaperChinese,
}
