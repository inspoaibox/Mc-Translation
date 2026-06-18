# 🎉 翻译 API v2.0 部署成功！

## ✅ 项目已完成

恭喜！你的**企业级安全翻译 API** 已经成功部署并运行。

### 🌐 访问地址

- **API 服务**: http://localhost:8000
- **管理后台**: http://localhost:8000/admin/login
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

### 🔑 默认登录信息

```
用户名: admin
密码: admin123
```

**⚠️ 重要：首次登录后请立即修改密码！**

---

## 📋 快速开始指南

### 1️⃣ 登录管理后台

1. 打开浏览器访问：http://localhost:8000/admin/login
2. 输入默认账号密码登录
3. 进入管理后台仪表盘

### 2️⃣ 创建 API 密钥

1. 在左侧菜单点击"API 密钥"
2. 点击"创建密钥"按钮
3. 填写信息：
   - 名称：如 "测试密钥"
   - 描述：用途说明
   - 速率限制：100（每小时请求次数）
   - 有效期：留空表示永不过期
4. 保存后复制密钥（只显示一次）

### 3️⃣ 测试翻译功能

#### 方式 A：在线测试（管理后台）

1. 点击左侧菜单"在线翻译"
2. 输入文本，选择语言和模型
3. 点击"翻译"按钮查看结果

#### 方式 B：API 调用

```bash
curl -X POST "http://localhost:8000/translate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 你的API密钥" \
  -d '{
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"
  }'
```

---

## 📊 功能清单

### ✅ 已实现功能

- [x] **多模型支持**: Argos、MarianMT、M2M100、M2M100 1.2B、NLLB-200
- [x] **安全认证**: JWT Token + API Key 双重认证
- [x] **管理后台**: 完整的 Web 管理界面
- [x] **API 密钥管理**: 创建、删除、配置速率限制
- [x] **在线测试**: Web 界面测试翻译
- [x] **调用日志**: 记录所有翻译请求
- [x] **耗时拆分**: 记录模型加载、推理、格式处理耗时
- [x] **MarianMT CTranslate2**: 支持将已下载 MarianMT 转换为 CT2 int8 本地推理
- [x] **统计分析**: 实时查看调用统计
- [x] **明确模型选择**: 指定模型失败时直接返回错误，不自动切换备用模型
- [x] **速率限制**: 防止滥用
- [x] **密钥过期**: 支持设置有效期
- [x] **完整文档**: Swagger UI 自动生成

### 🎨 管理后台页面

1. **仪表盘**: 总览统计数据
2. **API 密钥**: 管理所有密钥
3. **在线翻译**: 测试翻译功能
4. **调用日志**: 查看历史记录
5. **系统设置**: 配置系统参数
6. **API 文档**: 集成接口文档

---

## 🔒 安全配置

### 生产环境部署前必做

1. **修改管理员密码**
   - 登录后台后修改
   - 或直接修改 `.env` 文件中的 `ADMIN_PASSWORD`

2. **生成强随机密钥**
   ```bash
   # Linux/Mac
   openssl rand -hex 32
   
   # 或使用 Python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   将生成的密钥替换 `.env` 中的 `SECRET_KEY`

3. **启用 HTTPS**
   - 推荐使用 Caddy 反向代理，自动申请和续期 HTTPS 证书
   - 也可以使用 Nginx + Let's Encrypt

4. **配置防火墙**
   ```bash
   # 只开放必要端口
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

---

## 📡 API 使用示例

### Python

```python
import requests

url = "http://localhost:8000/translate"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "sk_your_api_key_here"
}
data = {
    "text": "Hello, world!",
    "source_lang": "en",
    "target_lang": "zh",
    "model": "argos"  # 可选: argos, marian, m2m100, m2m100_1_2b, nllb
}

response = requests.post(url, json=data, headers=headers)
result = response.json()

if result["success"]:
    print(f"译文: {result['translated_text']}")
    print(f"使用模型: {result['model_used']}")
    print(f"耗时: {result.get('timing')}")
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/translate', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'sk_your_api_key_here'
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

---

## 🚀 部署到公网

### 方案 1: 使用 Caddy（推荐，自动 HTTPS）

1. 域名解析到服务器公网 IP
2. 应用监听本机 `127.0.0.1:8000`
3. 在 `/etc/caddy/Caddyfile` 配置反向代理（完整配置见 README.md）
4. Caddy 自动申请和续期 HTTPS 证书

### 方案 2: 使用 Nginx

1. 安装 Nginx
2. 配置反向代理（见 README.md）
3. 配置 SSL 证书
4. 设置为系统服务

### 方案 3: 使用 PM2

```bash
cd ~/Mc-Translation
sudo apt install -y python3.10-venv python3-pip
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pm2 delete mc-translation || true
pm2 start /root/Mc-Translation/venv/bin/python \
  --name mc-translation \
  --cwd /root/Mc-Translation \
  -- -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pm2 save
pm2 startup systemd -u root --hp /root
```

执行 `pm2 startup` 输出的 `sudo env PATH=...` 命令后，再运行：

```bash
pm2 save
systemctl status pm2-root
curl http://127.0.0.1:8000/health
```

### 方案 4: 使用 Docker

```bash
# 构建镜像
docker build -t translation-api .

# 运行容器
docker run -d -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  --name translation-api \
  translation-api
```

### 方案 5: 使用 Systemd

详见 README.md 中的完整步骤

---

## 📝 维护指南

### 定期备份数据库

```bash
# 手动备份
cp translation_api.db backup/translation_api_$(date +%Y%m%d).db

# 自动备份（添加到 crontab）
0 2 * * * cp /path/to/translation_api.db /backup/translation_api_$(date +\%Y\%m\%d).db
```

### 查看日志

```bash
# 如果使用 systemd
sudo journalctl -u translation-api -f

# 如果使用 Docker
docker logs -f translation-api

# 如果使用 PM2
pm2 logs mc-translation

# 直接运行
# 查看终端输出
```

### 更新依赖

```bash
pip install --upgrade -r requirements.txt
```

---

## ⚡ 性能优化建议

### 如果有 GPU

修改 `.env`:
```env
DEVICE=cuda
```

安装 CUDA 版本的 PyTorch:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### Transformers 翻译速度参数

Argos 是轻量离线翻译包，通常会比 PyTorch Transformers 快。MarianMT、M2M100、NLLB 默认使用本地 `generate()` 推理，CPU 上会明显慢于 Argos。可在 `.env` 中调整：

```env
TRANSLATION_MAX_NEW_TOKENS=128
TRANSLATION_BATCH_SIZE=8
TORCH_CPU_THREADS=0
MODEL_WARMUP_ENABLED=true
TRANSFORMER_WARMUP_MODELS=marian
TRANSFORMER_WARMUP_PAIRS=zh-en,en-zh
MARIAN_BACKEND=auto
M2M100_BACKEND=auto
NLLB_BACKEND=auto
CTRANSLATE2_MODELS_DIR=./models/ctranslate2
MARIAN_CT2_COMPUTE_TYPE=int8
MARIAN_CT2_INTER_THREADS=1
MARIAN_CT2_INTRA_THREADS=0
MARIAN_CT2_MAX_QUEUED_BATCHES=0
M2M100_CT2_COMPUTE_TYPE=int8
M2M100_CT2_INTER_THREADS=1
M2M100_CT2_INTRA_THREADS=0
M2M100_CT2_MAX_QUEUED_BATCHES=0
NLLB_CT2_COMPUTE_TYPE=int8
NLLB_CT2_INTER_THREADS=1
NLLB_CT2_INTRA_THREADS=0
NLLB_CT2_MAX_QUEUED_BATCHES=0
```

MarianMT、M2M100、NLLB 下载完成后，可在管理后台“模型管理”点击“转换 CT2”。转换产物保存在 `./models/ctranslate2`，该目录已被 `.gitignore` 忽略，不应上传到 Git。

修改后重启：

```bash
pm2 restart mc-translation --update-env
pm2 save
```

### 多 Worker 运行

```bash
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

---

## 🐛 常见问题

### Q: 模型下载失败？

A: 使用 HuggingFace 镜像
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q: 端口被占用？

A: 修改 `.env` 或启动命令中的端口号

### Q: API Key 无效？

A: 检查：
1. 密钥是否正确复制
2. 密钥是否已过期
3. 密钥状态是否为"活跃"
4. 请求头格式：`X-API-Key: sk_xxx`

---

## 📚 相关文档

- `README.md` - 完整使用文档
- `PROJECT_OVERVIEW.md` - 项目架构说明
- `http://localhost:8000/docs` - API 接口文档

---

## 🎯 下一步建议

1. ✅ 修改默认密码
2. ✅ 创建第一个 API Key
3. ✅ 测试翻译功能
4. ⬜ 配置 HTTPS（生产环境）
5. ⬜ 设置自动备份
6. ⬜ 配置监控告警

---

## 💡 技术栈

- **框架**: FastAPI + Uvicorn
- **认证**: JWT + API Key
- **数据库**: SQLite (可迁移到 PostgreSQL)
- **密码加密**: Argon2
- **翻译引擎**: Argos Translate, MarianMT, M2M100, NLLB, MarianMT CTranslate2, M2M100 CTranslate2, NLLB CTranslate2
- **前端**: 原生 HTML + CSS + JavaScript

---

## 📮 获取帮助

- 查看文档：`README.md`
- 在线文档：http://localhost:8000/docs
- 提交问题：GitHub Issues

---

**🎉 恭喜你完成部署！享受安全、高效的翻译服务！**
