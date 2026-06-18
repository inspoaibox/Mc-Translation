# 翻译 API v2.0 - 项目总览

## 📁 项目结构

```
Mc-Translation/
├── app/                          # 应用主目录
│   ├── __init__.py              # 包初始化
│   ├── main.py                   # FastAPI 主程序（路由、认证）
│   ├── config.py                 # 配置管理
│   ├── auth.py                   # 认证逻辑（JWT、API Key）
│   ├── database.py               # 数据库模型
│   ├── db_session.py             # 数据库会话
│   ├── schemas.py                # Pydantic 数据模型
│   │
│   ├── models/                   # 翻译模型封装
│   │   ├── __init__.py
│   │   ├── argos.py             # Argos Translate
│   │   ├── marian.py            # MarianMT / CTranslate2
│   │   ├── m2m100.py            # M2M100
│   │   ├── nllb.py              # NLLB-200
│   │   ├── metrics.py           # 翻译耗时统计结构
│   │   └── ct2_utils.py         # CTranslate2 本地模型路径工具
│   │
│   ├── static/                   # 静态资源
│   │   ├── css/
│   │   │   └── admin.css        # 管理后台样式
│   │   └── js/
│   │       ├── admin.js         # 管理后台逻辑
│   │       └── login.js         # 登录页逻辑
│   │
│   └── templates/                # HTML 模板
│       ├── login.html           # 登录页面
│       └── admin.html           # 管理后台
│
├── .env                          # 环境变量（敏感信息）
├── .env.example                  # 环境变量示例
├── .gitignore                    # Git 忽略文件
├── requirements.txt              # Python 依赖
├── README.md                     # 完整文档
├── deploy.sh                     # Linux 部署脚本
├── deploy.bat                    # Windows 部署脚本
├── start.py                      # 快速启动脚本
├── test_api.py                   # 简单测试
└── test_complete.py              # 完整测试套件
```

## 🎯 核心功能模块

### 1. 认证系统 (`auth.py`)
- JWT Token 认证（管理后台）
- API Key 认证（API 调用）
- 密码哈希加密
- Token 过期管理

### 2. 数据库 (`database.py`, `db_session.py`)
- **User 表**: 管理员账号
- **APIKey 表**: API 密钥管理
- **TranslationLog 表**: 调用日志
- **SystemConfig 表**: 系统配置

### 3. 翻译引擎 (`models/`)
- **Argos**: 轻量级、快速
- **MarianMT**: 高质量、专业；已下载模型可转换 CTranslate2 int8 加速
- **M2M100**: 多语言支持
- **NLLB-200**: Meta 多语言翻译模型

### 4. 管理后台 (`templates/`, `static/`)
- 仪表盘：实时统计
- API 密钥管理
- 在线翻译测试
- 调用日志查看
- API 文档

## 🔐 安全架构

```
                  ┌─────────────────┐
                  │   客户端请求     │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  API Gateway     │
                  │  (FastAPI)       │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │  JWT    │       │ API Key │       │  CORS   │
   │  验证   │       │  验证   │       │  中间件 │
   └────┬────┘       └────┬────┘       └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                  ┌────────▼────────┐
                  │  业务逻辑层     │
                  │  - 翻译         │
                  │  - 日志记录     │
                  │  - 速率限制     │
                  └────────┬────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   ┌────▼────┐       ┌────▼────┐       ┌────▼────┐
   │  Argos  │       │ Marian  │       │ M2M100  │
   │  翻译器 │       │  翻译器 │       │  翻译器 │
   └─────────┘       └─────────┘       └─────────┘
```

## 🔄 API 调用流程

### 翻译请求流程

```
1. 客户端发送请求
   POST /translate
   Header: X-API-Key: sk_xxx
   Body: { text, source_lang, target_lang, model }

2. API Key 验证
   - 检查密钥是否存在
   - 检查密钥是否激活
   - 检查密钥是否过期
   - 更新最后使用时间

3. 速率限制检查
   - 查询该密钥的调用次数
   - 判断是否超过限制

4. 执行翻译
   - 选择指定模型
   - 指定模型失败时直接返回错误，不自动切换备用模型
   - 记录模型加载、推理、格式处理耗时

5. 记录日志
   - 保存调用记录
   - 记录响应时间
   - 记录成功/失败状态

6. 返回结果
   {
     translated_text: "...",
     model_used: "argos",
     timing: {...},
     success: true
   }
```

## 📊 数据库设计

### Users 表
```sql
- id: 主键
- username: 用户名（唯一）
- email: 邮箱（唯一）
- hashed_password: 密码哈希
- is_active: 是否激活
- is_superuser: 是否超级管理员
- created_at: 创建时间
```

### APIKeys 表
```sql
- id: 主键
- key: API 密钥（唯一）
- name: 密钥名称
- description: 描述
- is_active: 是否激活
- rate_limit: 速率限制（次/小时）
- created_by: 创建者（关联 Users）
- created_at: 创建时间
- last_used_at: 最后使用时间
- expires_at: 过期时间
```

### TranslationLogs 表
```sql
- id: 主键
- api_key_id: 关联的 API Key
- source_lang: 源语言
- target_lang: 目标语言
- model_used: 使用的模型
- model_backend: 实际后端（argos / transformers / ctranslate2）
- actual_model_name: 实际本地模型名
- char_count: 字符数
- success: 是否成功
- error_message: 错误信息
- response_time: 响应时间（秒）
- model_load_time: 模型加载耗时
- inference_time: 推理耗时
- format_time: 格式保护处理耗时
- segment_count / batch_count: 翻译段数和批次数
- created_at: 创建时间
```

## 🚀 部署方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **直接运行** | 简单快速 | 不稳定 | 开发测试 |
| **Systemd** | 自动重启 | Linux 限定 | VPS 部署 |
| **PM2** | 启停简单，支持自启动 | 依赖 Node.js/PM2 | 单机快速部署 |
| **Docker** | 隔离环境 | 资源占用 | 容器化部署 |
| **Caddy + Uvicorn** | 自动 HTTPS，配置简单 | 高级流量策略较少 | 单机公网部署 |
| **Nginx + Uvicorn** | 负载均衡 | 配置复杂 | 生产环境 |
| **Gunicorn + Workers** | 高并发 | 内存占用 | 高流量场景 |

## ⚙️ 性能调优

### 1. 并发配置
```bash
# 单 worker（默认）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 多 worker（推荐生产环境）
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

### 2. 模型优化
- 使用较小的模型（m2m100_418M vs m2m100_1.2B）
- 启用 GPU 加速（CUDA）
- 预加载常用语言对
- MarianMT 下载后转换 CTranslate2 int8，并使用 `MARIAN_BACKEND=auto`
- 通过调用日志 timing 判断慢在加载、推理还是格式处理

### 3. 缓存策略
```python
# 可添加 Redis 缓存常用翻译
from redis import Redis
cache = Redis(host='localhost', port=6379)

def translate_cached(text, source, target):
    cache_key = f"{text}:{source}:{target}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    result = translator.translate(text, source, target)
    cache.set(cache_key, result, ex=3600)  # 1小时过期
    return result
```

## 🔧 常见问题

### Q: 模型下载慢怎么办？
A: 使用 HuggingFace 镜像
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q: 如何修改管理员密码？
A: 在数据库中更新或通过代码：
```python
from app.auth import get_password_hash
new_password_hash = get_password_hash("new_password")
# 更新到数据库
```

### Q: API Key 丢失了怎么办？
A: API Key 只在创建时显示一次，丢失后需要：
1. 删除旧密钥
2. 创建新密钥

### Q: 如何备份数据？
A: 定期备份 SQLite 数据库文件
```bash
cp translation_api.db backup/translation_api_$(date +%Y%m%d).db
```

## 📈 监控指标

建议监控以下指标：

1. **请求量**: 每小时/每天的翻译请求数
2. **成功率**: 翻译成功的比例
3. **响应时间**: 平均翻译耗时
4. **错误率**: 失败请求的比例
5. **密钥使用**: 各 API Key 的调用分布
6. **模型分布**: 各模型的使用比例
7. **语言对分布**: 热门的翻译方向

## 🎓 最佳实践

1. **安全**
   - 使用强随机 SECRET_KEY
   - HTTPS 加密传输
   - 定期轮换 API Key
   - 限制登录尝试次数

2. **性能**
   - 使用连接池
   - 启用数据库索引
   - 实施缓存策略
   - 监控资源使用

3. **可靠性**
   - 自动重启机制
   - 错误日志记录
   - 健康检查端点
   - 备份恢复流程

4. **可维护性**
   - 代码注释清晰
   - 版本控制
   - 文档及时更新
   - 单元测试覆盖

## 📞 技术支持

- 问题反馈：提交 GitHub Issue
- 功能建议：Pull Request
- 文档贡献：欢迎完善

---

**版本**: 2.0.0  
**最后更新**: 2026-06-16
