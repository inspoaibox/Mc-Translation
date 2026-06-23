"""
Generic causal language model translator for local HuggingFace chat models.
"""
import json
import re
import time
from threading import Lock
from typing import Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .formatting import translate_preserving_line_format_batched
from .generation import batched, model_load_kwargs
from .metrics import TranslationMetrics, TranslationResult


THINKING_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
CODE_FENCE_PATTERN = re.compile(r"^```(?:[a-zA-Z0-9_-]+)?\s*(.*?)\s*```$", re.DOTALL)
LABEL_PATTERN = re.compile(
    r"^(?:translation|translated text|result|output|译文|翻译结果)\s*[:：]\s*",
    re.IGNORECASE,
)
# 匹配提示词泄露：更精确的模式，避免误删正常翻译
# 只匹配完整的提示词指令行（通常单独成行，没有实际内容）
INSTRUCTION_LEAK_PATTERN = re.compile(
    r"^(?:翻译|Translation|Translate|请保留|Please preserve|文本|Text|如果输入|If the input)[：:\s]*(?:$|(?=[A-Z]|\n))",
    re.IGNORECASE
)
# 匹配重复的翻译结果标记
REPEATED_MARKER_PATTERN = re.compile(
    r"(?:translation|translated text|翻译|译文)[:：]\s*(?:translation|translated text|翻译|译文)[:：]",
    re.IGNORECASE
)


class CausalLMTranslator:
    """Translate with local instruction-tuned causal language models."""

    LANG_NAME_MAP = {
        "zh": "Simplified Chinese",
        "zt": "Traditional Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
        "ar": "Arabic",
        "hi": "Hindi",
        "th": "Thai",
    }

    def __init__(self, model_id: str, model_name: str, device: str = "cpu"):
        self.model_id = model_id
        self.model_name = model_name
        self.requested_device = device
        self.device = "cuda" if device == "cuda" and torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        self._load_lock = Lock()
        self._generation_lock = Lock()

    def _is_small_model(self) -> bool:
        """检测是否为小模型（< 1B），需要特殊处理"""
        small_model_keywords = ["0.5b", "500m", "0_5b"]
        model_lower = self.model_name.lower()
        return any(keyword in model_lower for keyword in small_model_keywords)

    def _load_model(self):
        if self.model is not None:
            return

        with self._load_lock:
            if self.model is not None:
                return

            try:
                print(f"Loading local causal LM for translation: {self.model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    trust_remote_code=True,
                )
                if self.tokenizer.pad_token_id is None and self.tokenizer.eos_token:
                    self.tokenizer.pad_token = self.tokenizer.eos_token

                self.model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    trust_remote_code=True,
                    **model_load_kwargs(self.device),
                ).to(self.device)
                self.model.eval()
            except Exception as e:
                print(f"Failed to load causal LM {self.model_name}: {str(e)}")
                self.tokenizer = None
                self.model = None

    def _language_name(self, lang: str) -> str:
        return self.LANG_NAME_MAP.get(lang, lang)

    def _build_system_prompt(self, source_lang: str, target_lang: str) -> str:
        """构建系统提示词，定义翻译器的角色和规则"""
        source = self._language_name(source_lang)
        target = self._language_name(target_lang)

        return (
            f"You are a professional translator specializing in {source} to {target} translation.\n\n"
            "Core principles:\n"
            "1. Translate ALL content completely - never omit or skip any part\n"
            "2. Output ONLY the translated text, no explanations or notes\n"
            "3. Maintain one-to-one correspondence with the source text\n"
            "4. Never add phrases like 'Here is the translation:' or 'Translation:'\n"
            "5. Preserve all formatting: line breaks, Markdown, HTML, code blocks, numbers\n"
            "6. Keep special tokens like {{variables}}, placeholders unchanged\n"
            "7. Match the original tone, style, and structure exactly\n\n"
            "Your output must be complete translated content, ready to use directly."
        )

    def _build_user_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        source = self._language_name(source_lang)
        target = self._language_name(target_lang)

        # 针对小模型（< 1B）使用极简提示词，避免指令泄露
        if self._is_small_model():
            return f"Translate from {source} to {target}:\n\n{text}"

        # 标准模型：简洁的用户消息（系统提示词已定义规则）
        return text

    def _render_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        user_content = self._build_user_prompt(text, source_lang, target_lang)

        # 小模型不使用 system prompt（容易泄露）
        if self._is_small_model():
            messages = [{"role": "user", "content": user_content}]
        else:
            # 标准模型使用 system + user 结构
            system_content = self._build_system_prompt(source_lang, target_lang)
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]

        if self.tokenizer and getattr(self.tokenizer, "chat_template", None):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            except Exception:
                return prompt

        return prompt

    def _clean_output(self, output: str) -> str:
        text = THINKING_BLOCK_PATTERN.sub("", output or "").strip()

        # 移除代码围栏
        fence_match = CODE_FENCE_PATTERN.match(text)
        if fence_match:
            text = fence_match.group(1).strip()

        # 移除标签前缀（如 "Translation: " 单独成行的情况）
        text = LABEL_PATTERN.sub("", text).strip()

        # 移除提示词泄露（小模型常见问题）
        # 改进：只删除空洞的指令行，保留包含实际内容的行
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                cleaned_lines.append(line)
                continue

            # 检测是否为纯指令行（没有实际翻译内容）
            # 只有当行内容非常短（< 20 字符）且完全匹配指令模式时才删除
            if len(stripped) < 20 and INSTRUCTION_LEAK_PATTERN.match(stripped):
                continue

            # 保留所有其他行（包括以"翻译"等开头但包含实际内容的行）
            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines).strip()

        # 移除重复的标记
        text = REPEATED_MARKER_PATTERN.sub("", text).strip()

        # 尝试解析 JSON（某些模型可能返回 JSON 格式）
        try:
            parsed = json.loads(text)
            if isinstance(parsed, str):
                text = parsed.strip()
        except json.JSONDecodeError:
            pass

        # 移除开头和结尾的重复换行
        text = text.strip()

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

        return text.strip()

    def _max_new_tokens(self, input_token_count: int, source_lang: str = "en", target_lang: str = "zh") -> int:
        from ..config import config

        # 策略：给足够大的上限，让模型通过 EOS token 自然停止
        # 这避免了人为限制导致的截断问题

        # 小模型：仍需要一定限制，防止生成失控
        if self._is_small_model():
            # 使用保守的上限，但比之前大得多
            return min(2048, config.LLM_TRANSLATION_MAX_NEW_TOKENS)

        # 标准模型：给非常大的上限，几乎不限制
        # 模型会在翻译完成后自然生成 EOS token 停止
        return min(4096, config.LLM_TRANSLATION_MAX_NEW_TOKENS)

    def _batch_size(self) -> int:
        from ..config import config

        if config.LLM_TRANSLATION_BATCH_SIZE > 0:
            return config.LLM_TRANSLATION_BATCH_SIZE
        return 4 if self.device == "cuda" else 1

    def _translate_one(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        translated = self._translate_many([text], source_lang, target_lang)
        return translated[0] if translated else None

    def _translate_many(self, texts: list[str], source_lang: str, target_lang: str) -> Optional[list[str]]:
        from ..config import config

        if not self.tokenizer or not self.model:
            return None

        prompts = [self._render_prompt(text, source_lang, target_lang) for text in texts]

        with self._generation_lock:
            original_padding_side = getattr(self.tokenizer, "padding_side", "right")
            self.tokenizer.padding_side = "left"
            try:
                inputs = self.tokenizer(
                    prompts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=config.LLM_MAX_INPUT_TOKENS,
                ).to(self.device)
            finally:
                self.tokenizer.padding_side = original_padding_side

            input_width = inputs["input_ids"].shape[1]
            attention_mask = inputs.get("attention_mask")
            if attention_mask is not None:
                max_input_token_count = int(attention_mask.sum(dim=1).max().item())
            else:
                max_input_token_count = input_width

            # 检测截断警告
            if input_width >= config.LLM_MAX_INPUT_TOKENS:
                print(f"Warning: Input truncated at {config.LLM_MAX_INPUT_TOKENS} tokens. Some content may be lost.")

            pad_token_id = (
                self.tokenizer.pad_token_id
                if self.tokenizer.pad_token_id is not None
                else self.tokenizer.eos_token_id
            )
            with torch.inference_mode():
                # 使用 beam search 提高翻译质量
                generation_kwargs = {
                    "do_sample": False,
                    "num_beams": 3,  # 使用 beam search 提高质量
                    "use_cache": True,
                    "max_new_tokens": self._max_new_tokens(max_input_token_count),
                    "pad_token_id": pad_token_id,
                    "eos_token_id": self.tokenizer.eos_token_id,
                }

                # 小模型使用更保守的参数
                if self._is_small_model():
                    generation_kwargs.update({
                        "num_beams": 1,  # 小模型使用贪婪解码（beam search 太慢）
                        "repetition_penalty": 1.05,  # 降低重复惩罚（之前 1.2 太高）
                    })

                generated = self.model.generate(**inputs, **generation_kwargs)

        translated = []
        for row in generated:
            output_ids = row[input_width:]
            decoded = self.tokenizer.decode(output_ids, skip_special_tokens=True)
            cleaned = self._clean_output(decoded)

            # 如果清理后结果为空，说明模型输出无效
            if not cleaned:
                return None

            # 额外验证：检查输出是否包含过多的提示词关键字（可能是泄露）
            leak_keywords = ['translate', 'translation', 'preserve', 'markdown', 'html', '翻译', '保留']
            keyword_count = sum(1 for keyword in leak_keywords if keyword in cleaned.lower())
            # 如果关键词数量超过输出词数的 20%，可能是提示词泄露
            word_count = len(cleaned.split())
            if word_count > 5 and keyword_count > word_count * 0.2:
                print(f"Warning: Possible prompt leak detected in output: {cleaned[:100]}...")
                # 尝试提取实际内容（通常在冒号或换行后）
                for separator in [':\n', ': ', '\n\n']:
                    if separator in cleaned:
                        parts = cleaned.split(separator)
                        if len(parts) > 1 and parts[-1].strip():
                            potential_translation = parts[-1].strip()
                            # 验证提取的内容不再包含过多关键词
                            potential_word_count = len(potential_translation.split())
                            potential_keyword_count = sum(
                                1 for keyword in leak_keywords
                                if keyword in potential_translation.lower()
                            )
                            if potential_keyword_count < potential_word_count * 0.1:
                                cleaned = potential_translation
                                break

            translated.append(cleaned)

        return translated

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        return self.translate_with_metrics(text, source_lang, target_lang).text

    def translate_with_metrics(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        metrics = TranslationMetrics(backend="transformers-causal-lm", actual_model_name=self.model_name)

        try:
            load_start = time.perf_counter()
            self._load_model()
            metrics.model_load_time = time.perf_counter() - load_start
            if not self.tokenizer or not self.model:
                return TranslationResult(None, metrics)

            def translate_segments(segments: list[str]) -> Optional[list[str]]:
                translated_texts = []
                for chunk in batched(segments, self._batch_size()):
                    batch_start = time.perf_counter()
                    translated = self._translate_many(chunk, source_lang, target_lang)
                    metrics.inference_time += time.perf_counter() - batch_start
                    metrics.segment_count += len(chunk)
                    metrics.batch_count += 1
                    if translated is None:
                        return None
                    translated_texts.extend(translated)
                return translated_texts

            def translate_segment(segment: str) -> Optional[str]:
                translated = translate_segments([segment])
                return translated[0] if translated else None

            format_start = time.perf_counter()
            translated_text = translate_preserving_line_format_batched(text, translate_segments, translate_segment)
            format_total = time.perf_counter() - format_start
            metrics.format_time = max(0.0, format_total - metrics.inference_time)
            return TranslationResult(translated_text, metrics)

        except Exception as e:
            print(f"Causal LM translation failed for {self.model_name}: {str(e)}")
            return TranslationResult(None, metrics)

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        return source_lang in self.LANG_NAME_MAP and target_lang in self.LANG_NAME_MAP

    def warm_up(self, pairs=None, max_pairs: int = 1):
        warmup_pairs = pairs or ["en-zh"]
        for index, pair in enumerate(warmup_pairs):
            if index >= max_pairs:
                break
            if "-" not in pair:
                continue
            source_lang, target_lang = pair.split("-", 1)
            if not self.is_available(source_lang, target_lang):
                continue
            try:
                print(f"Warming up causal LM {self.model_id}: {pair}")
                self.translate_with_metrics("Hello", source_lang, target_lang)
            except Exception as e:
                print(f"Causal LM warmup failed {self.model_id} {pair}: {str(e)}")
