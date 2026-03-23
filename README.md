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
| **OpenAlex** | 默认关闭（`OPENALEX_ENABLED=false`）。开启后需容器能访问 **`api.openalex.org`**；可在 [`server/docker-compose.example.env`](server/docker-compose.example.env) 配置回溯天数、可选 **venue Source ID**（会议/期刊轨道）、以及是否回填 arXiv 论文的引用数。 |
| **Docker 基础镜像** | `python:3.12-slim` 从 Docker Hub 拉取，国内请配置 **镜像加速**（阿里云、DaoCloud、`dockerproxy.com` 等）后再 `docker compose build`。 |

---

## 服务端 Docker 部署

在项目根目录：

```bash
docker compose up -d --build
```

- 接口地址：`http://<主机IP>:8000`
- 健康检查：`GET /health`
- 数据：`SQLite` 文件在卷 **`literature_data`** 内路径 `/data/literature.db`（勿删卷以免丢库）
- 可选环境变量：复制 [`server/.env.example`](server/.env.example) 为 `server/.env`（密钥勿提交）；Compose 已通过 `env_file` 加载该文件

### HTTPS（小程序真机 / 合法域名）

真机与正式版要求 **HTTPS** 且域名在公众平台配置为 **request 合法域名**。推荐用 **Caddy** 自动申请并续期 **Let’s Encrypt** 证书（`--profile https`）。

**前置条件**

1. 已有一个**解析到服务器公网 IP** 的域名（仅子域即可，如 `api.example.com`）。
2. 云安全组 / 防火墙放行 **TCP 80、443**（证书校验需访问 80；业务走 443）。
3. 服务器能访问 Let’s Encrypt（部分网络环境若失败，需换用其它证书源或境外线路，见文末说明）。

**步骤**

```bash
cp deploy/https.env.example deploy/https.env
# 编辑 deploy/https.env：填写 LITERATURE_DOMAIN=api.你的域名.com（无 https://、无端口）
docker compose --profile https up -d --build
```

- 对外地址：`https://<LITERATURE_DOMAIN>`（路径仍为 `/api/v1/...`，如 `https://api.example.com/health`）
- 小程序：把 [`miniprogram/utils/api.js`](miniprogram/utils/api.js) 中 `DEFAULT_BASE_URL` 改为上述 **https 根地址**，或在设置里写入 `api_base_url`
- 微信公众平台 → 开发设置 → **服务器域名** → request 合法域名填：`https://api.你的域名.com`（与微信后台要求一致，**不要**带尾路径）
- 内地小程序域名通常需**备案**；请按微信与管局要求自行完成
- 生产环境可在安全组**关闭 8000 对外**，仅保留 80/443，由 Caddy 反代到容器内 `literature-api:8000`

**说明**：若 Let’s Encrypt 在你所在网络不可用，可改用云厂商免费证书（如腾讯云 SSL）手动得到 `fullchain.pem` / `privkey.pem` 后，自行改写 `deploy/Caddyfile` 使用 `tls /path/to/cert.pem /path/to/key.pem` 并挂载证书目录（需自行查阅 Caddy 文档）。

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
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

主要 API：

- `GET /api/v1/feed?sort=recommended|recent`
- `GET /api/v1/search?q=...`
- `POST /api/v1/events`
- `PUT /api/v1/users/me/preferences`

定时任务：每 2 小时执行一轮抓取（arXiv、RSS、**可选 OpenAlex 与 arXiv 引用回填**）；每日清理过期数据（见 `app/config.py` 与 `docker-compose.example.env`）。

---

## Android（`android/`）

用 **Android Studio** 打开 `android` 目录同步工程。

- **模拟器**访问本机 Docker/本地后端：`res/values/strings.xml` 中 `api_base_url` 使用 `http://10.0.2.2:8000`。
- **真机**：改为电脑或服务器的 **局域网 / 公网 IP**（与手机同一网络或可路由），并放行防火墙 **8000** 端口。

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
