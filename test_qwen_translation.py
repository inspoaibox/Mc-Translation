"""
测试 Qwen2.5 0.5B 模型翻译修复效果
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

# 测试用例
test_cases = [
    {
        "text": "Hello Walmart Marketplace Team,\n\nWe have already submitted a WFS inventory removal request for the items noted in violation.\n\nAffected Item IDs:\n\n17117224910\n15784570838\n\nWFS Support Case Number: 15249362\n\nThe inventory removal request has been submitted and is currently being processed by the WFS team. We will provide any additional removal documentation or confirmation as soon as it becomes available.\n\nThank you for your review and consideration.",
        "source_lang": "en",
        "target_lang": "zh",
        "description": "长文本翻译（Walmart 邮件）"
    },
    {
        "text": "Hello world",
        "source_lang": "en",
        "target_lang": "zh",
        "description": "简单短文本"
    },
    {
        "text": "The quick brown fox jumps over the lazy dog.",
        "source_lang": "en",
        "target_lang": "zh",
        "description": "中等长度句子"
    }
]

def main():
    print("=" * 80)
    print("测试 Qwen2.5 0.5B 模型翻译修复效果")
    print("=" * 80)

    # 初始化翻译器
    translator = CausalLMTranslator(
        model_id="qwen2_5_0_5b",
        model_name="Qwen/Qwen2.5-0.5B-Instruct",
        device="cpu"
    )

    # 先检查模型是否可用
    translator._load_model()

    if translator.model is None:
        print("\n[错误] 模型加载失败！")
        print("\n可能的原因:")
        print("1. 模型未下载到本地")
        print("2. 模型路径配置错误")
        print("\n解决方案:")
        print("请确保已下载 Qwen/Qwen2.5-0.5B-Instruct 模型到 Hugging Face 缓存目录")
        print("或使用其他已下载的模型进行测试")
        return

    print(f"\n模型: {translator.model_name}")
    print(f"设备: {translator.device}")
    print(f"小模型模式: {translator._is_small_model()}")
    print("\n" + "=" * 80)

    # 运行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}: {test_case['description']}")
        print("-" * 80)
        print(f"输入文本 ({test_case['source_lang']} -> {test_case['target_lang']}):")
        print(test_case['text'][:200] + "..." if len(test_case['text']) > 200 else test_case['text'])
        print("\n翻译中...")

        try:
            result = translator.translate_with_metrics(
                text=test_case['text'],
                source_lang=test_case['source_lang'],
                target_lang=test_case['target_lang']
            )

            if result.text:
                print("\n[成功] 翻译成功!")
                print(f"\n翻译结果:")
                print(result.text)
                print(f"\n性能指标:")
                print(f"  - 模型加载时间: {result.metrics.model_load_time:.3f}s")
                print(f"  - 推理时间: {result.metrics.inference_time:.3f}s")
                print(f"  - 格式化时间: {result.metrics.format_time:.3f}s")
                print(f"  - 片段数: {result.metrics.segment_count}")
                print(f"  - 批次数: {result.metrics.batch_count}")

                # 检查问题
                issues = []
                if "translate" in result.text.lower() or "翻译" in result.text:
                    if result.text.lower().count("translate") > 2 or result.text.count("翻译") > 2:
                        issues.append("[警告] 可能存在提示词泄露")

                if len(result.text) > len(test_case['text']) * 3:
                    issues.append("[警告] 输出过长，可能存在重复")

                lines = result.text.split('\n')
                if any("markdown" in line.lower() or "html" in line.lower() for line in lines):
                    issues.append("[警告] 可能包含格式化指令")

                if issues:
                    print(f"\n问题检测:")
                    for issue in issues:
                        print(f"  {issue}")
                else:
                    print(f"\n[成功] 质量检查通过，无明显问题")

            else:
                print("\n[失败] 翻译失败: 返回 None")

        except Exception as e:
            print(f"\n[错误] 翻译出错: {str(e)}")
            import traceback
            traceback.print_exc()

        print("\n" + "=" * 80)

    print("\n测试完成!")

if __name__ == "__main__":
    main()
