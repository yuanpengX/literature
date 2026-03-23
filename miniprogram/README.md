# 文献雷达 · 微信小程序

与仓库内 **Android** 客户端对齐的页面与接口：**推荐**（arXiv / 期刊 / 会议）、**每日精选**、**搜索**、**收藏**（本机存储）、**设置**（API 根地址、BYOK、同步服务端 LLM）、**订阅配置**（关键词 / 期刊 / 会议）、**论文详情**（收藏、AI 要点、复制链接）。

## 开发

1. 安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
2. 导入本目录 `miniprogram`（或项目根选择该文件夹，视工具版本而定）。
3. `project.config.json` 中 `appid` 可暂用测试号；正式发布需替换为你的小程序 AppID。
4. **文献 API 默认地址**：与 Android `res/values/strings.xml` 中 `api_base_url` 一致，内置在 `utils/api.js` 的 `DEFAULT_BASE_URL`；设置里留空即使用该默认（与 APK 未改「应用后端地址」时行为一致）。填写时**不要**带 `/api/v1`。
5. **request 合法域名**：在微信公众平台为小程序配置你的 **文献 API 域名**（HTTPS）。开发阶段可在开发者工具勾选「不校验合法域名」。
6. **若订阅页等出现 `request:fail`**：真机须使用 **HTTPS**（443）并在公众平台配置 request 合法域名（勿带非标准端口）。生产已与 `docker-compose.https-stack.yml` 对齐；仅本地调试可用根目录 `docker-compose.yml` 的 `http://局域网IP:80` 并勾选开发者工具「不校验合法域名」。
7. **开发者工具 Network 里 `feed` / `fetch-now` 显示 (failed)、Size 0 B**：表示请求未拿到 HTTP 响应（被微信拦截、TLS/证书失败或连不上服务器）。请打开该请求的 **Headers** 或控制台里的 **`errMsg`**；常见处理：勾选「详情 → 本地设置 → 不校验合法域名…」、在公众平台补全 request 域名、用浏览器访问 `https://你的域名/health` 确认服务与证书。更新后的 `utils/api.js` 会在 `fail` 回调里拼接更具体的中文提示。

## 微信登录与用户隔离

小程序使用[官方登录能力](https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login)：`app.js` 启动时调用 `wx.login` 获取 `code`，请求服务端 `POST /api/v1/auth/wechat/login`，换取 **JWT**（`access_token`），后续所有 API 使用请求头 `Authorization: Bearer <token>`。服务端用 `openid` 生成用户主键 `wx:{openid}`，写入 `user_profiles`，订阅 / LLM / 每日精选等均按该用户隔离。

**服务端环境变量**（见 [server/.env.example](../server/.env.example) 与 `docker-compose.yml` 注释）：

| 变量 | 说明 |
|------|------|
| `WECHAT_MINIPROGRAM_APP_ID` | 与小程序 `project.config.json` / 公众平台 **AppID** 一致 |
| `WECHAT_MINIPROGRAM_APP_SECRET` | 仅服务端保存，勿写入小程序代码 |
| `JWT_SECRET` | 签发 access_token 的 HMAC 密钥（长随机串） |
| `JWT_EXPIRES_DAYS` | 可选，默认 30 |

未配置微信或 JWT 时，`/auth/wechat/login` 返回 503，小程序会静默失败；此时请求不带 token，后端将用户视为 `anonymous`（与旧行为类似）。**正式环境务必配齐**，否则无法分用户。

**与 Android**：APK 仍通过 `X-User-Id` 识别用户，**不**使用本登录接口；两者用户体系独立。

**升级说明**：曾使用本地随机 `user_id` 的存储已废弃；登录成功后会清除。同一微信账号会得到稳定的 `wx:…` 画像；与旧随机 ID 下的订阅数据**不会自动合并**。

## 与 Android 的差异说明

| 能力 | 说明 |
|------|------|
| 用户身份 | 小程序：`wx.login` + JWT；Android：`X-User-Id`。 |
| 收藏 | 使用 `wx.setStorageSync`，不共用 Android 的 Room 数据库。 |
| PDF/原文 | 小程序内不直接打开外链，使用「复制链接」到浏览器查看。 |
| AI 摘要 | 直连模型商域名，需在小程序后台将该域名加入 **request 合法域名**。 |
| 埋点 | `utils/api.js` 已提供 `postEvents`（路径与 Android 一致，见 `utils/api-paths.js`）；页面可按需调用。 |
| Tab 再次点击刷新 | 微信 TabBar 无与 Android 完全一致的「同 Tab 再点」事件；推荐页请用 **下拉刷新**（会请求 `fetch-now` 并拉取 feed）。 |

## 主题

全局色与 Android `Theme.kt` 浅色主色一致：主色 `#3D5AFE`，背景 `#F7F2FA` / `#FFFBFE`。

## Tab 图标

`images/tab-*.png` 为 **81×81** PNG，语义与 Android `AppNav.kt` 底部栏一致（Material Filled：`Home` / `AutoAwesome` / `Search` / `Star` / `Settings`），未选中 `#49454F`、选中 `#3D5AFE`。

重新生成（仅需 Python 3 标准库）：

```bash
python3 miniprogram/scripts/gen_tab_icons.py
```

若需与官方位图完全一致，可自行从 [material-design-icons](https://github.com/google/material-design-icons) 导出对应 PNG 覆盖 `images/`。
