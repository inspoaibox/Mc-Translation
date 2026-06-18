@echo off
REM 翻译 API Windows 部署脚本

echo =================================
echo 翻译 API v2.0 部署脚本 (Windows)
echo =================================

REM 1. 检查 Python
echo 检查 Python 版本...
python --version
if errorlevel 1 (
    echo 错误: 未安装 Python
    exit /b 1
)

REM 2. 创建虚拟环境
echo 创建虚拟环境...
python -m venv venv
call venv\Scripts\activate.bat

REM 3. 安装依赖
echo 安装依赖包...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM 4. 创建 .env 文件
if not exist .env (
    echo 创建 .env 配置文件...
    (
        echo # 安全配置
        echo SECRET_KEY=change-this-to-random-secret-key-in-production
        echo ALGORITHM=HS256
        echo ACCESS_TOKEN_EXPIRE_MINUTES=30
        echo.
        echo # 数据库
        echo DATABASE_URL=sqlite+aiosqlite:///./translation_api.db
        echo.
        echo # 管理员账号
        echo ADMIN_USERNAME=admin
        echo ADMIN_PASSWORD=admin123
        echo ADMIN_EMAIL=admin@example.com
        echo.
        echo # API 配置
        echo API_RATE_LIMIT=100
        echo API_RATE_LIMIT_PERIOD=3600
        echo.
        echo # 模型配置
        echo DEFAULT_MODEL=argos
        echo DEVICE=cpu
    ) > .env
    echo [OK] .env 文件已创建
) else (
    echo [!] .env 文件已存在，跳过创建
)

echo.
echo =================================
echo [OK] 部署完成！
echo =================================
echo.
echo 启动服务:
echo   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo.
echo 访问地址:
echo   管理后台: http://localhost:8000/admin/login
echo   API 文档: http://localhost:8000/docs
echo.
echo 默认账号:
echo   用户名: admin
echo   密码: admin123
echo.
echo [!] 重要: 首次登录后请立即修改管理员密码！
echo =================================
pause
