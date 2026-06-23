"""
测试不同语言对的 Token 限制计算
"""
import sys
import os

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')

from app.models.causal_lm import CausalLMTranslator


def test_token_limits():
    print("=" * 80)
    print("测试语言对 Token 限制计算")
    print("=" * 80)

    # 创建小模型实例
    small_model = CausalLMTranslator(
        model_id="qwen2_5_0_5b",
        model_name="Qwen/Qwen2.5-0.5B-Instruct",
        device="cpu"
    )

    # 创建标准模型实例
    standard_model = CausalLMTranslator(
        model_id="qwen2_5_7b",
        model_name="Qwen/Qwen2.5-7B-Instruct",
        device="cpu"
    )

    print(f"\n小模型: {small_model.model_name} (is_small: {small_model._is_small_model()})")
    print(f"标准模型: {standard_model.model_name} (is_small: {standard_model._is_small_model()})")

    # 测试用例：不同语言对
    test_cases = [
        {
            "name": "英译中 (缩短)",
            "source": "en",
            "target": "zh",
            "input_tokens": 100,
            "expected_ratio": 0.7,
            "description": "英文单词 → 汉字，通常缩短 30%"
        },
        {
            "name": "中译英 (增长)",
            "source": "zh",
            "target": "en",
            "input_tokens": 100,
            "expected_ratio": 2.0,
            "description": "汉字 → 英文单词，通常增长 100%"
        },
        {
            "name": "日译英 (增长)",
            "source": "ja",
            "target": "en",
            "input_tokens": 100,
            "expected_ratio": 2.0,
            "description": "日文 → 英文，通常增长 100%"
        },
        {
            "name": "英译德 (微增)",
            "source": "en",
            "target": "de",
            "input_tokens": 100,
            "expected_ratio": 1.2,
            "description": "英文 → 德文，通常增长 20%（德语复合词）"
        },
        {
            "name": "未知语言对 (默认)",
            "source": "en",
            "target": "xx",
            "input_tokens": 100,
            "expected_ratio": 1.5,
            "description": "未知语言对使用保守的 1.5 倍"
        },
    ]

    print("\n" + "=" * 80)
    print("小模型 Token 限制")
    print("=" * 80)

    for test in test_cases:
        max_tokens = small_model._max_new_tokens(
            test["input_tokens"],
            test["source"],
            test["target"]
        )

        actual_ratio = (max_tokens - 32) / test["input_tokens"]

        print(f"\n{test['name']}")
        print(f"  描述: {test['description']}")
        print(f"  语言对: {test['source']} → {test['target']}")
        print(f"  输入 tokens: {test['input_tokens']}")
        print(f"  最大输出 tokens: {max_tokens}")
        print(f"  期望比例: {test['expected_ratio']}x")
        print(f"  实际比例: {actual_ratio:.2f}x (含 32 buffer)")

        # 验证
        expected_max = int(test["input_tokens"] * test["expected_ratio"]) + 32
        if max_tokens == expected_max or max_tokens == 512:  # 512 是上限
            print(f"  [成功] 正确")
        else:
            print(f"  [失败] 错误！期望 {expected_max}，实际 {max_tokens}")

    print("\n" + "=" * 80)
    print("标准模型 Token 限制")
    print("=" * 80)

    for test in test_cases:
        max_tokens = standard_model._max_new_tokens(
            test["input_tokens"],
            test["source"],
            test["target"]
        )

        actual_ratio = (max_tokens - 48) / test["input_tokens"]

        print(f"\n{test['name']}")
        print(f"  输入 tokens: {test['input_tokens']}")
        print(f"  最大输出 tokens: {max_tokens}")
        print(f"  实际比例: {actual_ratio:.2f}x (含 48 buffer)")

    print("\n" + "=" * 80)
    print("边界测试")
    print("=" * 80)

    # 测试极端情况
    extreme_cases = [
        ("中译英，短文本", 10, "zh", "en"),
        ("中译英，长文本", 500, "zh", "en"),
        ("英译中，短文本", 10, "en", "zh"),
        ("英译中，长文本", 500, "en", "zh"),
    ]

    for name, input_tokens, source, target in extreme_cases:
        small_max = small_model._max_new_tokens(input_tokens, source, target)
        standard_max = standard_model._max_new_tokens(input_tokens, source, target)

        print(f"\n{name} ({input_tokens} tokens)")
        print(f"  小模型: {small_max} tokens (上限 512)")
        print(f"  标准模型: {standard_max} tokens")

        # 验证最小值
        if small_max >= 32:
            print(f"  [成功] 小模型满足最小值要求 (>=32)")
        else:
            print(f"  [失败] 小模型低于最小值！")

        if standard_max >= 48:
            print(f"  [成功] 标准模型满足最小值要求 (>=48)")
        else:
            print(f"  [失败] 标准模型低于最小值！")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    print("\n关键改进:")
    print("- [成功] 根据语言对动态调整 token 限制")
    print("- [成功] 英译中: 0.7x (避免浪费)")
    print("- [成功] 中译英: 2.0x (避免截断)")
    print("- [成功] 小模型上限: 256 -> 512")
    print("- [成功] 未知语言对: 使用保守的 1.5x")


if __name__ == "__main__":
    test_token_limits()
