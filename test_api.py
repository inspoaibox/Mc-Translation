"""
API 测试脚本
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("\n[测试] 健康检查")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

def test_translation(text, source_lang, target_lang, model=None):
    """测试翻译"""
    print(f"\n[测试] 翻译 - {source_lang} -> {target_lang}")
    print(f"原文: {text}")

    data = {
        "text": text,
        "source_lang": source_lang,
        "target_lang": target_lang
    }
    if model:
        data["model"] = model
        print(f"模型: {model}")

    response = requests.post(f"{BASE_URL}/translate", json=data)
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"译文: {result['translated_text']}")
        print(f"使用模型: {result['model_used']}")
    else:
        print(f"错误: {response.json()}")

def test_models():
    """测试模型列表"""
    print("\n[测试] 获取模型列表")
    response = requests.get(f"{BASE_URL}/models")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    print("=" * 60)
    print("本地翻译 API 测试")
    print("=" * 60)

    try:
        # 健康检查
        test_health()

        # 模型列表
        test_models()

        # 英译中
        test_translation(
            text="Hello, world! This is a translation test.",
            source_lang="en",
            target_lang="zh"
        )

        # 中译英
        test_translation(
            text="你好，世界！这是一个翻译测试。",
            source_lang="zh",
            target_lang="en"
        )

        # 指定模型
        test_translation(
            text="Good morning!",
            source_lang="en",
            target_lang="zh",
            model="argos"
        )

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n[错误] 无法连接到服务器，请确保服务已启动: python start.py")
    except Exception as e:
        print(f"\n[错误] 测试失败: {str(e)}")
