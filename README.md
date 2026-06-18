# 本地翻译 API v2.0

🔒 **企业级安全翻译 API** - 整合 Argos Translate、MarianMT、M2M100、NLLB 多个本地翻译模型，提供带认证、速率限制、日志统计的完整解决方案。

## ✨ 核心特性

### 🔐 安全性
- **JWT 身份认证** - 管理后台访问控制
- **API Key 管理** - 为每个客户端生成独立密钥
- **速率限制** - 防止滥用，可自定义限制
- **密钥过期** - 支持设置有效期
- **审计日志** - 完整的调用记录

### 🚀 功能
- **多模型支持** - Argos、MarianMT、M2M100、M2M100 1.2B、NLLB-200
- **明确模型选择** - 指定模型后只使用该模型，失败时直接返回错误
- **性能诊断** - 翻译响应和调用日志记录加载、推理、格式处理耗时
- **MarianMT 加速** - 支持将已下载 MarianMT 转换为 CTranslate2 int8 本地推理
- **在线测试** - Web 界面测试翻译功能
- **统计分析** - 实时查看调用统计
- **完整文档** - 自动生成 API 文档

### 📊 管理后台
- 仪表盘 - 实时统计数据
- API 密钥管理 - 创建、删除、配置
- 在线翻译测试 - 测试各个模型
- 调用日志 - 查看历史记录
- 系统设置 - 配置参数
- API 文档 - 集成文档

## 🎯 支持的语言

英语 (en) | 中文 (zh) | 日语 (ja) | 韩语 (ko) | 法语 (fr) | 德语 (de) | 西班牙语 (es) | 俄语 (ru)

## 📦 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并修改：

```bash
cp .env.example .env
```

**重要：修改以下配置**
```env
# 🔑 请务必修改密钥（生产环境）
SECRET_KEY=your-random-secret-key-here-change-this

# 管理员账号（首次启动后立即修改密码）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# 模型性能
MODEL_WARMUP_ENABLED=true
TRANSFORMER_WARMUP_MODELS=marian
MARIAN_BACKEND=auto
M2M100_BACKEND=auto
```

API 限流默认值在管理后台“系统设置”里配置，不再写死到 `.env`。

### 3. 启动服务

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. 访问管理后台

打开浏览器访问：`http://localhost:8000/admin/login`

- 默认用户名：`admin`
- 默认密码：`admin123`

**⚠️ 首次登录后请立即修改密码**

## 🔑 API 密钥管理

### 创建 API Key

1. 登录管理后台
2. 进入"API 密钥"页面
3. 点击"创建密钥"
4. 设置名称、速率限制、有效期
5. 保存密钥（仅显示一次，请妥善保管）

### 使用 API Key

在请求头中添加：

```http
X-API-Key: sk_your_api_key_here
```

## 📡 API 调用示例

### cURL

```bash
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_your_api_key" \
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
  }'
```

### Python

```python
import requests

url = "http://localhost:8000/translate"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "sk_your_api_key"
}
data = {
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
}

response = requests.post(url, json=data, headers=headers)
result = response.json()
print(result["translated_text"])
print(result.get("timing"))
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/translate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'sk_your_api_key'
  },
  body: JSON.stringify({
    text: 'Hello, world!',
    source_lang: 'en',
    target_lang: 'zh',
    model: 'argos'
  })
});

const result = await response.json();
console.log(result.translated_text);
```

## 🌐 部署到公网

### 方案 1: 使用 Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### 方案 2: 使用 Caddy 反向代理

Caddy 会自动申请和续期 Let's Encrypt HTTPS 证书，适合单机公网部署。

1. 确认域名 `your-domain.com` 已解析到服务器公网 IP。
2. 只开放公网 `80` / `443`，应用服务监听本机 `127.0.0.1:8000`。
3. 安装 Caddy：

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

4. 写入 Caddy 配置：

```bash
sudo nano /etc/caddy/Caddyfile
```

```caddyfile
your-domain.com {
    encode zstd gzip

    request_body {
        max_size 20MB
    }

    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
    }

    log {
        output file /var/log/caddy/translation-api.log
        format json
    }
}
```

启动或重载：

```bash
sudo mkdir -p /var/log/caddy
sudo chown -R caddy:caddy /var/log/caddy
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

反向代理模式下建议这样启动服务：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果访问域名出现 `502`，优先检查后端是否已经监听本机 `8000`：

```bash
curl http://127.0.0.1:8000/health
ss -ltnp | grep :8000
```

访问地址：

- 管理后台：`https://your-domain.com/admin/login`
- API 文档：`https://your-domain.com/docs`
- 翻译接口：`https://your-domain.com/translate`

### 方案 3: 使用 PM2 守护后端

PM2 适合已经用 Caddy/Nginx 做反向代理，只需要把 Python 后端稳定跑在本机 `127.0.0.1:8000` 的场景。

安装 PM2：

```bash
sudo apt update
sudo apt install -y nodejs npm
sudo npm install -g pm2
```

创建虚拟环境并安装依赖：

```bash
cd ~/Mc-Translation
sudo apt install -y python3.10-venv python3-pip
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果之前启动失败过，先删除 PM2 里的旧进程：

```bash
pm2 delete mc-translation || true
```

使用项目绝对路径启动服务：

```bash
pm2 start /root/Mc-Translation/venv/bin/python \
  --name mc-translation \
  --cwd /root/Mc-Translation \
  -- -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

检查服务：

```bash
pm2 status
pm2 logs mc-translation
curl http://127.0.0.1:8000/health
```

保存进程列表并设置开机自启动：

```bash
pm2 save
pm2 startup systemd -u root --hp /root
```

`pm2 startup` 会输出一条 `sudo env PATH=... pm2 startup ...` 命令，把它复制执行一次，然后再保存：

```bash
pm2 save
systemctl status pm2-root
```

更新代码或环境变量后重启：

```bash
pm2 restart mc-translation --update-env
pm2 save
```

如果日志出现 `venv/bin/python: No such file or directory`，说明虚拟环境不存在或 PM2 启动目录不对。重新执行上面的 `python3 -m venv venv`，并使用 `/root/Mc-Translation/venv/bin/python` 这种绝对路径启动。

### 方案 4: 使用 Docker

创建 `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建和运行：

```bash
docker build -t translation-api .
docker run -d -p 8000:8000 --name translation-api \
  -e SECRET_KEY=your-secret-key \
  translation-api
```

### 方案 5: 使用 Systemd 服务

创建 `/etc/systemd/system/translation-api.service`:

```ini
[Unit]
Description=Translation API Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/translation-api
Environment="PATH=/opt/translation-api/venv/bin"
ExecStart=/opt/translation-api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable translation-api
sudo systemctl start translation-api
```

## 🔒 安全建议

### 1. 生产环境配置

✅ **必须修改**
- 生成强随机 SECRET_KEY
- 修改管理员密码
- 禁用调试模式

✅ **推荐配置**
```env
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_PASSWORD=VeryStrongPassword123!@#
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 2. HTTPS 配置

**强烈建议**在公网部署时启用 HTTPS：

如果使用 Caddy，配置域名后会自动申请和续期证书。如果使用 Nginx，可以使用 Let's Encrypt 免费证书：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 3. 防火墙设置

```bash
# 仅允许 80/443 端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 4. 速率限制

根据实际需求调整 API Key 的速率限制：

- 免费用户：100 请求/小时
- 付费用户：1000 请求/小时
- 企业用户：10000 请求/小时

### 5. 数据库备份

定期备份数据库：

```bash
# 备份
cp translation_api.db translation_api.db.backup

# 自动备份（crontab）
0 2 * * * cp /path/to/translation_api.db /backup/translation_api.db.$(date +\%Y\%m\%d)
```

## 📊 监控和日志

### 查看调用日志

在管理后台的"调用日志"页面可以查看：
- 调用时间
- API Key
- 语言对
- 模型
- 响应时间
- 成功/失败状态

### 系统日志

服务日志位置：
```bash
# 如果使用 systemd
sudo journalctl -u translation-api -f

# 如果使用 Docker
docker logs -f translation-api
```

## 🛠 性能优化

### 1. 启用 GPU 加速（如果有 GPU）

修改 `.env`:
```env
DEVICE=cuda
```

需要安装 CUDA 版本的 PyTorch：
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 2. 模型缓存

首次运行会下载模型，后续使用缓存：
- Argos: 按需下载语言包
- MarianMT: `~/.cache/huggingface`
- MarianMT CTranslate2: `./models/ctranslate2`，已被 `.gitignore` 忽略
- M2M100 / NLLB: `~/.cache/huggingface`

### 3. 翻译速度优化

Argos 是轻量离线翻译包，通常会比 PyTorch Transformers 快。MarianMT、M2M100、NLLB 默认使用本地 `model.generate()`，CPU 上会明显慢于 Argos。可在 `.env` 中调整：

```env
TRANSLATION_MAX_NEW_TOKENS=128
TRANSLATION_BATCH_SIZE=8
TORCH_CPU_THREADS=0
MODEL_WARMUP_ENABLED=true
TRANSFORMER_WARMUP_MODELS=marian
TRANSFORMER_WARMUP_PAIRS=zh-en,en-zh
MARIAN_BACKEND=auto
M2M100_BACKEND=auto
CTRANSLATE2_MODELS_DIR=./models/ctranslate2
MARIAN_CT2_COMPUTE_TYPE=int8
MARIAN_CT2_INTER_THREADS=1
MARIAN_CT2_INTRA_THREADS=0
MARIAN_CT2_MAX_QUEUED_BATCHES=0
M2M100_CT2_COMPUTE_TYPE=int8
M2M100_CT2_INTER_THREADS=1
M2M100_CT2_INTRA_THREADS=0
M2M100_CT2_MAX_QUEUED_BATCHES=0
```

- `TRANSLATION_MAX_NEW_TOKENS`: 单段最大生成长度，越大越慢；短句会自动按输入长度降低上限。
- `TRANSLATION_BATCH_SIZE`: 多行普通文本会批量送入模型，提高吞吐。
- `TORCH_CPU_THREADS`: `0` 表示使用 PyTorch 默认线程；小机器可尝试 `2` 或 `4`，避免线程调度过重。
- `MODEL_WARMUP_ENABLED`: 启动后后台预热模型，减少第一个客户请求承担的加载成本。
- `TRANSFORMER_WARMUP_MODELS`: 默认只预热 `marian`，避免启动时加载 M2M100/NLLB 这类大模型；需要时可设为 `marian,m2m100,nllb`。
- `MARIAN_BACKEND`: `auto` 会优先使用已转换的 CTranslate2 模型；也可设为 `transformers` 或 `ctranslate2`。
- `M2M100_BACKEND`: `auto` 会优先使用已转换的 M2M100 CTranslate2 模型；也可设为 `transformers` 或 `ctranslate2`。
- `MARIAN_CT2_COMPUTE_TYPE`: CPU 推荐 `int8`；GPU 可按环境改为 `float16` 或 `int8_float16`。
- `M2M100_CT2_COMPUTE_TYPE`: M2M100 的 CTranslate2 量化类型，CPU 推荐 `int8`。
- `MARIAN_CT2_INTER_THREADS`: CTranslate2 并行翻译 worker 数。官方 `Translator` 参数用于并行 translations；CPU 小机器建议从 `1` 开始压测。
- `MARIAN_CT2_INTRA_THREADS`: 每个 CTranslate2 worker 的 OpenMP 线程数，`0` 使用默认值。
- `MARIAN_CT2_MAX_QUEUED_BATCHES`: CTranslate2 队列上限，`0` 使用自动值；设置过小会让请求等待，设置过大可能增加内存占用。
- `M2M100_CT2_INTER_THREADS` / `M2M100_CT2_INTRA_THREADS` / `M2M100_CT2_MAX_QUEUED_BATCHES`: M2M100 的 CTranslate2 并行与队列参数。

管理后台“模型管理”中，MarianMT 和 M2M100 模型下载完成后可以点击“转换 CT2”。转换只使用本地已下载模型，不会在翻译请求中联网。转换完成后 `MARIAN_BACKEND=auto` / `M2M100_BACKEND=auto` 会优先调用 CTranslate2。

`/translate` 响应会返回可选 `timing` 字段，调用日志也会展示拆分耗时：

```json
{
  "model_backend": "ctranslate2",
  "actual_model_name": "Helsinki-NLP/opus-mt-zh-en",
  "timing": {
    "model_load_ms": 0.21,
    "inference_ms": 35.4,
    "format_ms": 0.18
  }
}
```

修改后重启服务：

```bash
pm2 restart mc-translation --update-env
```

### 4. 并发配置

使用 Gunicorn + Uvicorn workers：

```bash
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 🔧 故障排查

### 模型下载失败

使用 HuggingFace 镜像：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 端口被占用

```bash
# 查看占用进程
netstat -ano | grep 8000

# Windows
taskkill /PID <进程ID> /F

# Linux
kill -9 <进程ID>
```

### API Key 无效

1. 检查密钥是否过期
2. 确认密钥状态为"活跃"
3. 检查请求头格式：`X-API-Key: sk_xxx`

## 📝 API 端点列表

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/` | GET | 无 | 服务信息 |
| `/health` | GET | 无 | 健康检查 |
| `/docs` | GET | 无 | Swagger 文档 |
| `/translate` | POST | API Key | 翻译接口 |
| `/admin/login` | GET/POST | 无 | 管理员登录 |
| `/admin/dashboard` | GET | JWT | 管理后台 |
| `/admin/api-keys` | GET/POST | JWT | API 密钥管理 |
| `/admin/stats` | GET | JWT | 统计数据 |

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题或建议，请提交 Issue。

---

**⚠️ 重要提示**

1. 生产环境必须修改默认密码
2. 使用 HTTPS 保护数据传输
3. 定期备份数据库
4. 监控 API Key 使用情况
5. 及时更新依赖包

**🎉 享受安全、高效的翻译服务！**
