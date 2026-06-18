# 本地翻译 API v2.0

🔒 **企业级安全翻译 API** - 整合 Argos Translate、MarianMT、M2M100 三个翻译模型，提供带认证、速率限制、日志统计的完整解决方案。

## ✨ 核心特性

### 🔐 安全性
- **JWT 身份认证** - 管理后台访问控制
- **API Key 管理** - 为每个客户端生成独立密钥
- **速率限制** - 防止滥用，可自定义限制
- **密钥过期** - 支持设置有效期
- **审计日志** - 完整的调用记录

### 🚀 功能
- **多模型支持** - Argos、MarianMT、M2M100
- **明确模型选择** - 指定模型后只使用该模型，失败时直接返回错误
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

# API 速率限制
API_RATE_LIMIT=100
API_RATE_LIMIT_PERIOD=3600
```

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

### 方案 2: 使用 Docker

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

### 方案 3: 使用 Systemd 服务

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

使用 Let's Encrypt 免费证书：

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
- MarianMT: ~/.cache/huggingface
- M2M100: ~/.cache/huggingface

### 3. 并发配置

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
