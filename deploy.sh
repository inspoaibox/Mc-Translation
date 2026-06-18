#!/bin/bash
# 翻译 API 部署脚本

echo "================================="
echo "翻译 API v2.0 部署脚本"
echo "================================="

# 1. 检查 Python 版本
echo "检查 Python 版本..."
python3 --version || { echo "错误: 未安装 Python 3"; exit 1; }

# 2. 创建虚拟环境
echo "创建虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 3. 安装依赖
echo "安装依赖包..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. 生成密钥
echo "生成安全密钥..."
SECRET_KEY=$(openssl rand -hex 32)

# 5. 创建 .env 文件
if [ ! -f .env ]; then
    echo "创建 .env 配置文件..."
    cat > .env << EOF
# 安全配置
SECRET_KEY=$SECRET_KEY
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./translation_api.db

# 管理员账号（首次启动后请立即修改）
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@example.com

# API 配置
API_RATE_LIMIT=100
API_RATE_LIMIT_PERIOD=3600

# 模型配置
DEFAULT_MODEL=argos
DEVICE=cpu
EOF
    echo "✓ .env 文件已创建"
else
    echo "⚠ .env 文件已存在，跳过创建"
fi

# 6. 初始化数据库
echo "初始化数据库..."
python -c "
import asyncio
from app.db_session import init_db
asyncio.run(init_db())
print('✓ 数据库初始化完成')
"

# 7. 提示信息
echo ""
echo "================================="
echo "✓ 部署完成！"
echo "================================="
echo ""
echo "启动服务:"
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "或使用生产模式:"
echo "  gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000"
echo ""
echo "访问地址:"
echo "  管理后台: http://localhost:8000/admin/login"
echo "  API 文档: http://localhost:8000/docs"
echo ""
echo "默认账号:"
echo "  用户名: admin"
echo "  密码: admin123"
echo ""
echo "⚠️  重要: 首次登录后请立即修改管理员密码！"
echo "================================="
