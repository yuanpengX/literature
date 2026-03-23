# TLS 证书（阿里云 SSL / 其他 CA）

Caddy 读取本目录下两个文件（**勿提交仓库**，已在根 `.gitignore` 忽略）：

| 文件 | 说明 |
|------|------|
| `fullchain.pem` | **完整证书链**：域名证书在前，中间证书在后（可多条 PEM 拼接） |
| `privkey.pem` | **私钥**（与签发时配对） |

## 从阿里云证书列表下载

1. 控制台 → SSL 证书 → 证书列表 → 对应证书 → **下载**，选择 **Nginx** 或其它 PEM 格式。
2. 解压后常见为：`*_public.crt`（或 `.pem`）域名证书、`*_chain.crt` 或 CA 链、`.key` 私钥。
3. 生成 `fullchain.pem`（**顺序**：先贴域名证书内容，再贴中间证书/链，中间无空行亦可，PEM 之间直接相连）：
   ```bash
   cat your_domain.crt your_chain.crt > fullchain.pem
   ```
   若下载包内已是「证书+链」单文件，可直接复制为 `fullchain.pem`。
4. 私钥文件复制为 `privkey.pem`（权限建议仅所有者可读：`chmod 600 privkey.pem`）。

## 校验

```bash
openssl x509 -in fullchain.pem -noout -subject -dates
openssl rsa -in privkey.pem -check -noout
```

配置完成后在项目根执行：

`docker compose --env-file deploy/compose.https.env -f docker-compose.https-stack.yml up -d --force-recreate caddy`

证书在阿里云「/ssl」等其它目录时，先改 `deploy/compose.https.env` 里的 `CERT_HOST_DIR`，再在 `deploy/https.env` 中设置 `CADDY_TLS_CERT` / `CADDY_TLS_KEY`（容器内路径均为 `/etc/caddy/certs/…`），见 `deploy/https.env.example`。
