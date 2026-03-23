# 文献雷达（Literature Radar）

Monorepo：**Android 客户端** + **FastAPI 后端**。当前已实现：arXiv 拉取、RSS 可选、**可选 OpenAlex** 扩展文献与引用数、`GET /feed` 轻量推荐（热度 + 兴趣）、`POST /events` 埋点、搜索与论文详情；Android 四 Tab（推荐 / 搜索 / 收藏 / 设置）、下拉刷新、外链 PDF、列表/详情展示引用数、埋点与分析开关。

**Android**：**Room** 缓存；**EncryptedSharedPreferences** 存 **BYOK**（DeepSeek / Kimi 等 OpenAI 兼容端点）；详情页 **生成中文要点**。**WorkManager** 本地定期检查新论文并发系统通知（**不依赖谷歌 FCM**，适合中国大陆日常使用）。

**服务端**：支持 **Docker Compose** 一键部署（见下文）。`POST /api/v1/devices/fcm-token` 将 token 写入 SQLite 表 `fcm_tokens`（供海外或具备 GMS 环境后续接 Firebase Admin；**国内无 GMS 设备请以本地通知为主**）。

---

## 中国大陆使用说明

| 场景 | 说明 |
|------|------|
| **Android 构建** | [`android/settings.gradle.kts`](android/settings.gradle.kts) 已把 **阿里云 Maven** 放在 **`google()` / `mavenCentral()` 之前**，减轻同步 Gradle 依赖时的超时。Gradle 发行包若下载慢，请在 Android Studio → Settings → Gradle 配置 **国内镜像** 或使用自带 JDK 离线包策略。 |
| **大模型 API** | 设置里 **DeepSeek**、**Kimi（Moonshot）** 等为**国内可直连**的 OpenAI 兼容接口；请勿把 Key 发到本应用后端。 |
| **系统推送** | **未集成**需谷歌服务的 FCM 推送链路；日常依赖 **WorkManager + 本地通知**。若将来接 FCM，仅适合有 GMS 或海外用户。 |
| **arXiv 抓取** | 服务端访问 `export.arxiv.org`，部分网络环境可能较慢；可在 [`docker-compose.yml`](docker-compose.yml) 中为容器配置 **`HTTP_PROXY` / `HTTPS_PROXY`**（`httpx` 会读取环境变量），或在你侧网络做透明代理。 |
| **OpenAlex** | 默认关闭（`OPENALEX_ENABLED=false`）。开启后需容器能访问 **`api.openalex.org`**，并在 [`server/.env.example`](server/.env.example) 中填写 **`OPENALEX_API_KEY`**（[openalex.org/settings/api](https://openalex.org/settings/api) 免费申请）；另可配置回溯天数、可选 **venue Source ID**、是否回填 arXiv 引用数（见 [`server/docker-compose.example.env`](server/docker-compose.example.env)）。 |
| **Docker 基础镜像** | `python:3.12-slim` 从 Docker Hub 拉取，国内请配置 **镜像加速**（阿里云、DaoCloud、`dockerproxy.com` 等）后再 `docker compose build`。 |

---

## 服务端 Docker 部署

### 生产：对外仅 HTTPS（推荐）

真机小程序、正式版客户端要求 **HTTPS（默认 443）** 与**已备案**（如适用）的合法域名。请使用 **[`docker-compose.https-stack.yml`](docker-compose.https-stack.yml)**：**Caddy** 占用宿主机 **80 / 443**，反代到容器内 `literature-api:8000`（不在宿主机暴露 `:8000`）。

**前置条件**

1. 域名已解析到服务器公网 IP（如 `cppteam.cn`）。
2. 安全组放行 **TCP 80、443**。
3. 服务器能访问 Let’s Encrypt（不可用时见文末「自定义证书」说明）。

**步骤**

```bash
cp deploy/https.env.example deploy/https.env
# 编辑 deploy/https.env：
#   LITERATURE_DOMAIN=cppteam.cn（无 https://、无端口；若 API 在子域可填 api.cppteam.cn）
#   ACME_EMAIL=你的邮箱（Let’s Encrypt 账户）
cp server/.env.example server/.env   # 按需填写密钥等
docker compose -f docker-compose.https-stack.yml up -d --build
```

- 对外根地址：`https://<LITERATURE_DOMAIN>`（**443**，勿写端口；例 `https://cppteam.cn/health`）
- 客户端：将 [`miniprogram/utils/api.js`](miniprogram/utils/api.js) 的 `DEFAULT_BASE_URL` 与 [`android/.../strings.xml`](android/app/src/main/res/values/strings.xml) 的 `api_base_url` 设为同一 **https 根地址**（无尾斜杠、无 `/api/v1`）
- 微信公众平台 → **服务器域名** → request 合法域名填你的 **https 域名**（不要带路径）
- 从旧部署升级时：若仅有 `LITERATURE_DOMAIN`，请在 `https.env` 中**补充** `ACME_EMAIL`

**说明**：[`deploy/Caddyfile`](deploy/Caddyfile) 使用全局 `email` 与站点反代；API 镜像内 **uvicorn** 已加 `--proxy-headers`，以便正确识别 `X-Forwarded-Proto` 等。若 Let’s Encrypt 不可用，可自行改写 `deploy/Caddyfile` 使用 `tls` 挂载云厂商证书（见 Caddy 文档）。

### 本地 / 内网：HTTP 默认端口 80

在项目根目录：

```bash
docker compose up -d --build
```

- 接口根地址：`http://<主机IP>/`（**80**，勿写 `:8000`；容器内仍为 `:8000`，由 Compose 映射）
- 健康检查：`GET http://<主机IP>/health`
- 数据：`SQLite` 在卷 **`literature_data`** → `/data/literature.db`

可选环境变量：复制 [`server/.env.example`](server/.env.example) 为 `server/.env`。

**HTTPS** 请只用 [`docker-compose.https-stack.yml`](docker-compose.https-stack.yml），避免与根目录 compose 争抢宿主机 **80**（二者勿同时占用同一台机的 80）。

停止并删除容器（保留数据卷）：

```bash
docker compose down
```

查看日志：

```bash
docker compose logs -f literature-api
```

**国内 pip**：[`server/Dockerfile`](server/Dockerfile) 构建时**优先**使用 **清华 PyPI 镜像**，失败再回退官方 `pypi.org`。

---

## 后端本地运行（非 Docker）

需要 **Python 3.12+**。若本机默认 pip 镜像无包，可切换源：

```bash
cd server
python3.12 -m venv .venv
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
cp .env.example .env
# 与 Docker 一致使用 HTTP 默认端口（Linux 绑定 80 常需 root）：
sudo .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 80
# 若不便使用 80，可改用任意端口（如 8000），访问时须写全 URL：http://127.0.0.1:8000
```

主要 API：

- `GET /api/v1/feed?sort=recommended|recent|hot|for_you`（**小程序**：综合 `recommended`、热门 `hot`，无「为你推荐」；**Android**：热门 + 为你推荐）
- `GET /api/v1/search?q=...`
- `POST /api/v1/events`
- `PUT /api/v1/users/me/preferences`

定时任务：每 2 小时执行一轮抓取（arXiv、RSS、**可选 OpenAlex 与 arXiv 引用回填**）；每日清理过期数据（见 `app/config.py` 与 `docker-compose.example.env`）。

### 小程序 / Android 与后端路径一致（HTTPS）

生产请求形态均为 **`https://<域名>/api/v1/...`**（根 URL 勿含 `/api/v1`，由客户端常量拼接）。同一套路由定义在：

- [`miniprogram/utils/api-paths.js`](miniprogram/utils/api-paths.js)
- [`android/app/src/main/java/com/literatureradar/app/data/ApiV1Paths.kt`](android/app/src/main/java/com/literatureradar/app/data/ApiV1Paths.kt)（供 [`LiteratureApi.kt`](android/app/src/main/java/com/literatureradar/app/data/LiteratureApi.kt) 引用）

对照表见 [`contracts/openapi-stub.yaml`](contracts/openapi-stub.yaml)。改 FastAPI 路由时请同步以上三处。

---

## Android（`android/`）

用 **Android Studio** 打开 `android` 目录同步工程。

- **模拟器**连本机根目录 `docker compose`（宿主机 **80**）：Debug 默认 `http://10.0.2.2`（见 `src/debug/res/values/strings.xml`）。
- **真机 / 正式版**：与小程序一致，使用 **HTTPS 根地址**（**443**，勿写端口）；纯内网 HTTP 调试用 `http://<局域网IP>` 并放行 **80**。

---

## 目录结构

```
android/              # Kotlin + Compose
server/               # FastAPI + SQLAlchemy
docker-compose.yml    # 根目录编排
contracts/            # OpenAPI 草稿
```

## 功能缺口清单

与计划对比的细表见 **[docs/STATUS.md](docs/STATUS.md)**（未实现项、建议优先级）。

## 后续工作

- 内嵌 PDF、会议源（OpenAlex）、PostgreSQL 正式迁移与备份脚本。
- 国内厂商推送（如极光/个推）替代 FCM（按需）。
- Encrypted DataStore 替代部分 SharedPreferences（可选）。
