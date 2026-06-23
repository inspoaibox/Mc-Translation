# Qwen2.5 0.5B 翻译问题修复说明

## 问题分析

在使用 Qwen2.5 0.5B 模型进行翻译时，发现以下问题：

### 原始输入
```
Hello Walmart Marketplace Team,

We have already submitted a WFS inventory removal request for the items noted in violation.

Affected Item IDs:

17117224910
15784570838

WFS Support Case Number: 15249362

The inventory removal request has been submitted and is currently being processed by the WFS team. We will provide any additional removal documentation or confirmation as soon as it becomes available.

Thank you for your review and consideration.
```

### 问题输出
```
你好，沃尔玛市场团队，

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

感谢您对我的审查和考虑。
```

### 核心问题

1. **提示词泄露** - 模型将提示词中的指令（"翻译："、"请保留Markdown、HTML标签和数字"）混入了输出
2. **重复标记** - 出现了多个 "翻译：" 标记
3. **内容混乱** - 原文和译文混杂，包含不必要的格式说明

这是小型模型（< 1B 参数）的典型问题：**指令遵循能力弱，容易将提示词内容泄露到输出中**。

---

## 修复方案

### 1. 小模型检测机制

**文件**: `app/models/causal_lm.py:64-68`

```python
def _is_small_model(self) -> bool:
    """检测是否为小模型（< 1B），需要特殊处理"""
    small_model_keywords = ["0.5b", "500m", "0_5b"]
    model_lower = self.model_name.lower()
    return any(keyword in model_lower for keyword in small_model_keywords)
```

**作用**: 自动识别小型模型，启用特殊处理逻辑。

---

### 2. 极简提示词策略

**文件**: `app/models/causal_lm.py:103-122`

```python
def _build_user_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
    source = self._language_name(source_lang)
    target = self._language_name(target_lang)

    # 针对小模型（< 1B）使用极简提示词，避免指令泄露
    if self._is_small_model():
        return (
            f"Translate from {source} to {target}:\n\n{text}"
        )

    # 标准模型使用详细提示词
    return (
        f"Translate the following text from {source} to {target}.\n"
        "Return only the translated text. Do not explain. Do not add notes.\n"
        "Do not include reasoning or chain-of-thought. /no_think\n"
        "Preserve line breaks, Markdown, HTML tags, placeholders, numbers, and code-like tokens.\n"
        "If the input is a single fragment, return a single translated fragment.\n\n"
        f"Text:\n{text}\n\n"
        "Translation:\n"
    )
```

**关键改进**:
- 小模型使用极简单的指令: `Translate from English to Chinese:\n\n{text}`
- 避免复杂的格式说明，减少被模型"记住"并泄露到输出的风险
- 大模型仍使用详细提示词，保持翻译质量

---

### 3. 指令泄露检测与清理

**文件**: `app/models/causal_lm.py:21-31`

新增正则表达式模式：

```python
# 匹配提示词泄露：以"翻译"、"Translation"等开头的重复指令
INSTRUCTION_LEAK_PATTERN = re.compile(
    r"^(?:翻译|Translation|Translate|请保留|Please preserve|文本|Text).*?[:：\n]",
    re.IGNORECASE | re.MULTILINE
)

# 匹配重复的翻译结果标记
REPEATED_MARKER_PATTERN = re.compile(
    r"(?:translation|translated text|翻译|译文)[:：]\s*(?:translation|translated text|翻译|译文)[:：]",
    re.IGNORECASE
)
```

**文件**: `app/models/causal_lm.py:158-183`

增强的输出清理逻辑：

```python
# 移除提示词泄露（小模型常见问题）
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
```

**作用**: 
- 逐行扫描输出，检测并移除泄露的指令
- 使用启发式规则识别真正的翻译内容
- 移除重复的标记如 "翻译：翻译："

---

### 4. 重复内容检测与截断

**文件**: `app/models/causal_lm.py:196-205`

```python
# 如果输出过长且存在明显重复，截断到第一个完整翻译
if len(text) > len(output or "") * 0.8:
    # 检测是否有内容重复（简单启发式：前半部分和后半部分相似）
    mid = len(text) // 2
    if mid > 50:
        first_half = text[:mid].strip()
        second_half = text[mid:].strip()
        # 如果后半部分以前半部分开头，说明有重复
        if second_half.startswith(first_half[:min(100, len(first_half))]):
            text = first_half
```

**作用**: 检测并移除输出中的重复翻译内容。

---

### 5. Token 生成限制

**文件**: `app/models/causal_lm.py:209-219`

```python
def _max_new_tokens(self, input_token_count: int) -> int:
    from ..config import config

    # 小模型使用更保守的 token 限制，避免生成过长内容
    if self._is_small_model():
        dynamic_limit = int(input_token_count * 1.5) + 16
        max_limit = min(256, config.LLM_TRANSLATION_MAX_NEW_TOKENS)
        return max(16, min(max_limit, dynamic_limit))

    dynamic_limit = int(input_token_count * 1.8) + 24
    return max(24, min(config.LLM_TRANSLATION_MAX_NEW_TOKENS, dynamic_limit))
```

**改进**:
- 小模型使用 1.5 倍输入长度（而非 1.8 倍），避免生成过多冗余内容
- 限制最大 token 数为 256，防止失控生成

---

## 预期效果

修复后，相同输入应产生干净的输出：

```
你好，沃尔玛市场团队，

我们已经提交了针对违规物品的WFS库存移除请求。

受影响的商品ID：

17117224910
15784570838

WFS支持案例编号：15249362

库存移除请求已提交，目前正由WFS团队处理中。一旦可用，我们将提供任何额外的移除文档或确认信息。

感谢您的审查和考虑。
```

### 改进点
✅ 无提示词泄露  
✅ 无重复标记  
✅ 结构清晰  
✅ 保留原文格式（数字、换行）

---

## 测试方法

运行测试脚本验证修复效果：

```bash
python test_qwen_translation.py
```

测试脚本会：
1. 加载 Qwen2.5 0.5B 模型
2. 测试原问题中的长文本
3. 测试其他常见场景
4. 自动检测输出质量问题

---

## 技术总结

### 根本原因
小型语言模型（< 1B）的指令遵循能力有限，复杂的提示词容易被模型当作"上下文"而非"指令"，导致混入输出。

### 解决思路
1. **源头控制** - 简化提示词，减少可泄露内容
2. **输出清理** - 多层正则表达式过滤，移除泄露的指令
3. **生成限制** - 限制 token 数量，避免冗余生成
4. **自适应策略** - 根据模型大小自动调整处理逻辑

### 适用范围
- ✅ Qwen2.5 0.5B
- ✅ 其他 < 1B 小模型
- ✅ 不影响大模型（≥ 1B）的翻译质量
