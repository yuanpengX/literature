/**
 * 文献后端 /api/v1 路径（与 Android ApiV1Paths.kt、FastAPI routers 一致）。
 * 根地址为后端根 URL（如 http://47.103.51.214 或 https 域名），与此处路径拼接即为完整 URL。
 * 修改服务端路由时请同步：本文件、ApiV1Paths.kt、contracts/openapi-stub.yaml。
 */
module.exports = {
  /** 公开：返回服务端 LITERATURE_HTTP_IP_BASE，供「IP 直连」开关拉取 */
  CONFIG_CLIENT: '/api/v1/config/client',
  /** 仅小程序；Android 使用 X-User-Id */
  AUTH_WECHAT_LOGIN: '/api/v1/auth/wechat/login',
  FEED: '/api/v1/feed',
  SEARCH: '/api/v1/search',
  paper: (id) => '/api/v1/papers/' + encodeURIComponent(String(id)),
  EVENTS: '/api/v1/events',
  USERS_ME_PREFERENCES: '/api/v1/users/me/preferences',
  USERS_ME_LLM: '/api/v1/users/me/llm',
  DAILY_PICKS_ME: '/api/v1/daily-picks/me',
  DAILY_PICKS_ME_RUN: '/api/v1/daily-picks/me/run',
  SUBSCRIPTIONS_CATALOG: '/api/v1/subscriptions/catalog',
  USERS_ME_SUBSCRIPTIONS: '/api/v1/users/me/subscriptions',
  USERS_ME_SUBSCRIPTIONS_FETCH_NOW: '/api/v1/users/me/subscriptions/fetch-now',
}
