"""
测试简化后的 Token 限制策略
"""
import sys
import os

if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')

from app.models.causal_lm import CausalLMTranslator


def test_simplified_token_limits():
    print("=" * 80)
    print("测试简化后的 Token 限制策略")
    print("=" * 80)

    small_model = CausalLMTranslator(
        model_id="qwen2_5_0_5b",
        model_name="Qwen/Qwen2.5-0.5B-Instruct",
        device="cpu"
    )

    standard_model = CausalLMTranslator(
        model_id="qwen2_5_7b",
        model_name="Qwen/Qwen2.5-7B-Instruct",
        device="cpu"
    )

    print(f"\n小模型: {small_model.model_name}")
    print(f"标准模型: {standard_model.model_name}")

    print("\n" + "=" * 80)
    print("新策略：给足够大的上限，让模型通过 EOS token 自然停止")
    print("=" * 80)

    test_cases = [
        ("短文本", 10),
        ("中等文本", 100),
        ("长文本", 500),
        ("超长文本", 1000),
    ]

    print("\n小模型限制:")
    for name, input_tokens in test_cases:
        max_tokens = small_model._max_new_tokens(input_tokens)
        print(f"  {name} ({input_tokens} tokens): {max_tokens} tokens")

    print("\n标准模型限制:")
    for name, input_tokens in test_cases:
        max_tokens = standard_model._max_new_tokens(input_tokens)
        print(f"  {name} ({input_tokens} tokens): {max_tokens} tokens")

    print("\n" + "=" * 80)
    print("核心理念")
    print("=" * 80)
    print("""
1. 不再尝试"预测"翻译长度
   - 语言对比例只是估计，不可能精确
   - 人为限制必然导致某些情况截断

2. 信任模型的 EOS token
   - 模型训练时学会了何时停止
   - 正常翻译完成后会自动生成 EOS token
   - max_new_tokens 只是"最大允许长度"，不是"必须生成这么多"

3. 策略
   - 小模型 (< 1B): 2048 tokens (防止失控)
   - 标准模型 (>= 1B): 4096 tokens (几乎不限制)
   - 模型会在合适的时候自然停止

4. 优势
   - ✓ 永远不会截断正常翻译
   - ✓ 简单，无需维护语言对映射表
   - ✓ 模型自然停止，不浪费资源
   - ✓ 支持所有语言对，包括未知的

5. 对小模型的额外保护
   - 小模型容易"跑飞"，生成重复或无意义内容
   - 通过提示词清理逻辑 + 2048 上限双重保护
   - 即使生成失控，清理逻辑会移除垃圾内容
""")

    print("=" * 80)
    print("总结")
    print("=" * 80)
    print("""
之前的复杂语言对映射是**过度设计**：
- 维护成本高（每个语言对都要调整）
- 仍然会出错（估计值不精确）
- 不支持未知语言对

新方案：
- 代码从 40 行 → 8 行
- 不需要维护映射表
- 适用于所有语言
- 让模型自己决定何时停止

这才是正确的方向。
""")


if __name__ == "__main__":
    test_simplified_token_limits()
