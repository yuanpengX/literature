# 功能实现状态（相对产品计划）

## 已实现（摘要）

- 后端：FastAPI、arXiv + 可选 RSS、**可选 OpenAlex**（可配置回溯天数与 venue Source ID、arXiv 引用数回填）、SQLite（Docker 卷）、`GET /feed` 推荐融合、**`citation_count` 对外字段**、`/search`、`/events` 埋点、`/users/me/preferences`、`/devices/fcm-token` 落库、定时抓取与 TTL、CORS、Docker Compose。
- Android：**四 Tab**（推荐 / 搜索 / **收藏** / 设置）、Room（favorites + **citationCount** 迁移）、BYOK、推荐分页、搜索写缓存、详情星标收藏 + 埋点、关于页、列表/详情 **引用数展示**（服务端开启 OpenAlex 并回填后可见）、可改 API Base URL、WorkManager 提醒、阿里云 Maven 优先。

## 未实现或仅部分实现

| 能力 | 说明 |
|------|------|
| **Firebase FCM 客户端** | 未接 `google-services.json`；国内无 GMS 场景以本地通知为主。服务端已可存 token，缺 Admin 发推送任务。 |
| **服务端主动推送** | 需 Firebase Admin（或国内厂商通道）+ 定时任务调用；未写。 |
| **账号体系** | 无登录/注册；`X-User-Id` 为匿名 id。Firebase Auth / 邀请码未做。 |
| **合规页** | 已有关于页 + **外链**（`strings.xml` 可配置）；无应用内 WebView 全文展示。 |
| **DBLP 等** | 未单独接 DBLP；会议/期刊可通过 OpenAlex `venue Source ID` 近似覆盖。 |
| **Semantic Scholar** | 未单独接；引用数以 OpenAlex 为主。 |
| **内嵌 PDF** | 现为系统浏览器打开链接。 |
| **收藏** | 本地 Room；未做服务端同步。 |
| **端上「今日精选」自动 LLM** | 详情页手动生成要点；WorkManager 未批量打分。 |
| **完整 OpenAPI 契约** | 仅有 `contracts/openapi-stub.yaml`。 |
| **PostgreSQL 正式迁移** | 仍为 SQLite；Compose 可扩展第二服务未写。 |
| **Encrypted DataStore** | LLM/部分偏好仍为 SharedPreferences + EncryptedSharedPreferences。 |

## 建议下一步（按性价比）

1. 将 `contracts/openapi-stub.yaml` 与真实 `PaperOut`（含 `citation_count`）对齐。  
2. 内嵌 PDF 阅读器（WebView / PdfRenderer）或「复制 DOI」快捷动作。  
