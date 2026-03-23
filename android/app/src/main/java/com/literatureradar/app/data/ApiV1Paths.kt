package com.literatureradar.app.data

/**
 * 文献后端 /api/v1 路径（与 miniprogram/utils/api-paths.js、FastAPI routers 一致）。
 * Retrofit [com.literatureradar.app.ServiceLocator] 的 baseUrl 为 `https://主机/`（勿含 /api/v1），
 * 此处路径均含 `api/v1/` 前缀。
 * 修改服务端路由时请同步：本文件、api-paths.js、contracts/openapi-stub.yaml。
 */
object ApiV1Paths {
    /** 仅微信小程序；Android 使用 X-User-Id，不在 [LiteratureApi] 中声明 */
    const val AUTH_WECHAT_LOGIN = "api/v1/auth/wechat/login"

    const val FEED = "api/v1/feed"
    const val SEARCH = "api/v1/search"
    const val PAPER = "api/v1/papers/{id}"
    const val EVENTS = "api/v1/events"
    const val USERS_ME_PREFERENCES = "api/v1/users/me/preferences"
    const val USERS_ME_LLM = "api/v1/users/me/llm"
    const val DAILY_PICKS_ME = "api/v1/daily-picks/me"
    const val DAILY_PICKS_ME_RUN = "api/v1/daily-picks/me/run"
    const val SUBSCRIPTIONS_CATALOG = "api/v1/subscriptions/catalog"
    const val USERS_ME_SUBSCRIPTIONS = "api/v1/users/me/subscriptions"
    const val USERS_ME_SUBSCRIPTIONS_FETCH_NOW = "api/v1/users/me/subscriptions/fetch-now"
}
