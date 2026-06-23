"""
测试翻译输出清理逻辑（不需要实际加载模型）
"""
import sys
import re

# 模拟 causal_lm.py 中的清理逻辑
INSTRUCTION_LEAK_PATTERN = re.compile(
    r"^(?:翻译|Translation|Translate|请保留|Please preserve|文本|Text|如果输入|If the input).*",
    re.IGNORECASE
)

REPEATED_MARKER_PATTERN = re.compile(
    r"(?:translation|translated text|翻译|译文)[:：]\s*(?:translation|translated text|翻译|译文)[:：]",
    re.IGNORECASE
)

LABEL_PATTERN = re.compile(
    r"^(?:translation|translated text|result|output|译文|翻译结果)\s*[:：]\s*",
    re.IGNORECASE,
)

def clean_translation_output(text: str) -> str:
    """模拟 _clean_output 方法"""
    # 移除标签前缀
    text = LABEL_PATTERN.sub("", text).strip()

    # 移除提示词泄露
    lines = text.split('\n')
    cleaned_lines = []
    skip_mode = False

    for line in lines:
        # 检测是否为泄露的指令
        if INSTRUCTION_LEAK_PATTERN.match(line.strip()):
            skip_mode = True
            continue

        # 检测到实际翻译内容后，停止跳过模式
        stripped = line.strip()
        if skip_mode and stripped and not any(
            keyword in stripped.lower()
            for keyword in ['翻译', 'translation', 'translate', '保留', 'preserve', 'markdown', 'html']
        ):
            skip_mode = False

        if not skip_mode:
            cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines).strip()

    # 移除重复的标记
    text = REPEATED_MARKER_PATTERN.sub("", text).strip()

    return text


def test_case_1_instruction_leak():
    """测试用例 1: 原始问题 - 提示词泄露"""
    print("\n" + "="*80)
    print("测试用例 1: 提示词泄露问题")
    print("="*80)

    problematic_output = """你好，沃尔玛市场团队，

翻译：
Hello Walmart Market Team

我们已经提交了WFS库存移除请求，针对标记为违规的物品。

受影响的条形码：

翻译：
受影响的条形码：

17117224910
15784570838

WFS Support Case Number: 15249362

请保留Markdown、HTML标签和数字。如果输入是单个片段，返回一个单独的翻译片段。

文本：
库存移除请求已提交，并由WFS团队处理中。我们将尽快提供任何额外的移除文档或确认信息。

感谢您对我的审查和考虑。"""

    print("\n原始输出 (有问题):")
    print(problematic_output)

    cleaned = clean_translation_output(problematic_output)

    print("\n清理后输出:")
    print(cleaned)

    # 验证
    issues = []
    if "翻译：" in cleaned or "Translation:" in cleaned:
        issues.append("- 仍包含 '翻译：' 标记")
    if "请保留" in cleaned or "Please preserve" in cleaned:
        issues.append("- 仍包含提示词指令")
    if "文本：" in cleaned or "Text:" in cleaned:
        issues.append("- 仍包含 '文本：' 标记")

    if issues:
        print("\n[失败] 清理不完整:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n[成功] 清理完成，无提示词泄露")
        return True


def test_case_2_repeated_markers():
    """测试用例 2: 重复标记"""
    print("\n" + "="*80)
    print("测试用例 2: 重复标记问题")
    print("="*80)

    problematic_output = """Translation: Translation: Hello world
译文：译文：你好世界"""

    print("\n原始输出:")
    print(problematic_output)

    cleaned = clean_translation_output(problematic_output)

    print("\n清理后输出:")
    print(cleaned)

    if "translation: translation:" in cleaned.lower() or "译文：译文：" in cleaned:
        print("\n[失败] 仍存在重复标记")
        return False
    else:
        print("\n[成功] 重复标记已移除")
        return True


def test_case_3_normal_output():
    """测试用例 3: 正常输出不应被过度清理"""
    print("\n" + "="*80)
    print("测试用例 3: 正常输出保持不变")
    print("="*80)

    normal_output = """你好，世界！

这是一段正常的翻译内容。
它不包含任何提示词泄露。"""

    print("\n原始输出:")
    print(normal_output)

    cleaned = clean_translation_output(normal_output)

    print("\n清理后输出:")
    print(cleaned)

    if cleaned.strip() == normal_output.strip():
        print("\n[成功] 正常输出未被修改")
        return True
    else:
        print("\n[警告] 正常输出被意外修改")
        return False


def test_case_4_label_prefix():
    """测试用例 4: 标签前缀移除"""
    print("\n" + "="*80)
    print("测试用例 4: 标签前缀移除")
    print("="*80)

    outputs = [
        "Translation: 你好世界",
        "译文：你好世界",
        "翻译结果: 你好世界",
        "Result: 你好世界"
    ]

    for output in outputs:
        print(f"\n原始: {output}")
        cleaned = clean_translation_output(output)
        print(f"清理: {cleaned}")

        if cleaned.strip() == "你好世界":
            print("[成功]")
        else:
            print(f"[失败] 期望 '你好世界'，实际 '{cleaned}'")
            return False

    return True


def main():
    print("="*80)
    print("翻译输出清理逻辑测试")
    print("="*80)
    print("\n这些测试验证修复后的清理逻辑能否正确处理:")
    print("1. 提示词泄露")
    print("2. 重复标记")
    print("3. 正常输出保护")
    print("4. 标签前缀移除")

    results = []

    results.append(("提示词泄露", test_case_1_instruction_leak()))
    results.append(("重复标记", test_case_2_repeated_markers()))
    results.append(("正常输出", test_case_3_normal_output()))
    results.append(("标签前缀", test_case_4_label_prefix()))

    print("\n" + "="*80)
    print("测试总结")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "[成功]" if result else "[失败]"
        print(f"{status} {name}")

    print(f"\n通过率: {passed}/{total} ({100*passed//total}%)")

    if passed == total:
        print("\n[成功] 所有测试通过！修复逻辑工作正常。")
    else:
        print("\n[失败] 部分测试未通过，需要进一步调整。")


if __name__ == "__main__":
    main()
