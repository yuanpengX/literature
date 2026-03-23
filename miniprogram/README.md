# 文献雷达 · 微信小程序

与仓库内 **Android** 客户端对齐的页面与接口：**推荐**（arXiv / 期刊 / 会议）、**每日精选**、**搜索**、**收藏**（本机存储）、**设置**（API 根地址、BYOK、同步服务端 LLM）、**订阅配置**（关键词 / 期刊 / 会议）、**论文详情**（收藏、AI 要点、复制链接）。

## 开发

1. 安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
2. 导入本目录 `miniprogram`（或项目根选择该文件夹，视工具版本而定）。
3. `project.config.json` 中 `appid` 可暂用测试号；正式发布需替换为你的小程序 AppID。
4. **文献 API 默认地址**：与 Android `res/values/strings.xml` 中 `api_base_url` 一致，内置在 `utils/api.js` 的 `DEFAULT_BASE_URL`；设置里留空即使用该默认（与 APK 未改「应用后端地址」时行为一致）。填写时**不要**带 `/api/v1`。
5. **request 合法域名**：在微信公众平台为小程序配置你的 **文献 API 域名**（HTTPS）。开发阶段可在开发者工具勾选「不校验合法域名」。

## 与 Android 的差异说明

| 能力 | 说明 |
|------|------|
| 收藏 | 使用 `wx.setStorageSync`，不共用 Android 的 Room 数据库。 |
| PDF/原文 | 小程序内不直接打开外链，使用「复制链接」到浏览器查看。 |
| AI 摘要 | 直连模型商域名，需在小程序后台将该域名加入 **request 合法域名**。 |
| 埋点 | 未默认上报 `/api/v1/events`，可按需在 `utils/api.js` 扩展。 |
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
