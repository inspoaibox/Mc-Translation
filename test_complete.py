"""
完整的 API 测试脚本（包含认证测试）
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"
TOKEN = None
API_KEY = None

def test_health():
    """测试健康检查"""
    print("\n" + "="*60)
    print("测试 1: 健康检查")
    print("="*60)

    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
    assert response.status_code == 200

def test_login():
    """测试管理员登录"""
    global TOKEN

    print("\n" + "="*60)
    print("测试 2: 管理员登录")
    print("="*60)

    response = requests.post(
        f"{BASE_URL}/admin/login",
        json={
            "username": "admin",
            "password": "admin123"
        }
    )
    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        TOKEN = data["access_token"]
        print(f"✓ 登录成功，获得 Token")
        print(f"Token: {TOKEN[:20]}...")
    else:
        print(f"✗ 登录失败: {response.json()}")

def test_create_api_key():
    """测试创建 API Key"""
    global API_KEY

    print("\n" + "="*60)
    print("测试 3: 创建 API Key")
    print("="*60)

    if not TOKEN:
        print("✗ 跳过测试（需要先登录）")
        return

    response = requests.post(
        f"{BASE_URL}/admin/api-keys",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={
            "name": "测试密钥",
            "description": "用于测试的 API 密钥",
            "rate_limit": 100
        }
    )

    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        API_KEY = data["key"]
        print(f"✓ API Key 创建成功")
        print(f"密钥: {API_KEY}")
    else:
        print(f"✗ 创建失败: {response.json()}")

def test_translation():
    """测试翻译功能"""
    print("\n" + "="*60)
    print("测试 4: 翻译功能")
    print("="*60)

    if not API_KEY:
        print("✗ 跳过测试（需要先创建 API Key）")
        return

    test_cases = [
        {
            "text": "Hello, world!",
            "source_lang": "en",
            "target_lang": "zh",
            "model": "argos"
        },
        {
            "text": "你好，世界！",
            "source_lang": "zh",
            "target_lang": "en",
            "model": "argos"
        }
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  测试用例 {i}:")
        print(f"  原文: {test_case['text']}")
        print(f"  {test_case['source_lang']} -> {test_case['target_lang']}")

        start = time.time()
        response = requests.post(
            f"{BASE_URL}/translate",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "application/json"
            },
            json=test_case
        )
        elapsed = time.time() - start

        print(f"  状态码: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ 译文: {data['translated_text']}")
            print(f"  使用模型: {data['model_used']}")
            print(f"  响应时间: {elapsed:.2f}秒")
        else:
            print(f"  ✗ 翻译失败: {response.json()}")

def test_stats():
    """测试统计接口"""
    print("\n" + "="*60)
    print("测试 5: 获取统计数据")
    print("="*60)

    if not TOKEN:
        print("✗ 跳过测试（需要先登录）")
        return

    response = requests.get(
        f"{BASE_URL}/admin/stats",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )

    print(f"状态码: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✓ 统计数据:")
        print(f"  总翻译次数: {data.get('total_translations', 0)}")
        print(f"  成功率: {data.get('success_rate', 0)}%")
        print(f"  活跃密钥数: {data.get('active_keys', 0)}")
        print(f"  平均响应时间: {data.get('avg_response_time', 0)}ms")
    else:
        print(f"✗ 获取失败: {response.json()}")

def test_invalid_api_key():
    """测试无效 API Key"""
    print("\n" + "="*60)
    print("测试 6: 无效 API Key（预期失败）")
    print("="*60)

    response = requests.post(
        f"{BASE_URL}/translate",
        headers={
            "X-API-Key": "invalid_key",
            "Content-Type": "application/json"
        },
        json={
            "text": "Test",
            "source_lang": "en",
            "target_lang": "zh"
        }
    )

    print(f"状态码: {response.status_code}")

    if response.status_code == 401:
        print(f"✓ 正确拒绝了无效密钥")
    else:
        print(f"✗ 预期 401，实际 {response.status_code}")

if __name__ == "__main__":
    print("="*60)
    print("翻译 API 完整测试")
    print("="*60)
    print(f"目标服务器: {BASE_URL}")
    print()

    try:
        # 依次执行测试
        test_health()
        test_login()
        test_create_api_key()
        test_translation()
        test_stats()
        test_invalid_api_key()

        print("\n" + "="*60)
        print("✓ 所有测试完成")
        print("="*60)

    except requests.exceptions.ConnectionError:
        print("\n✗ 错误: 无法连接到服务器")
        print("请确保服务已启动: python -m uvicorn app.main:app --port 8000")
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
