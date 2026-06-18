"""
快速启动脚本
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("本地翻译 API 服务启动中...")
    print("=" * 60)
    print(f"服务地址: http://localhost:8000")
    print(f"API 文档: http://localhost:8000/docs")
    print(f"健康检查: http://localhost:8000/health")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
