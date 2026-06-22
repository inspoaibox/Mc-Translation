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

    def _build_user_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        source = self._language_name(source_lang)
        target = self._language_name(target_lang)
        return (
            f"Translate the following text from {source} to {target}.\n"
            "Return only the translated text. Do not explain. Do not add notes.\n"
            "Do not include reasoning or chain-of-thought. /no_think\n"
            "Preserve line breaks, Markdown, HTML tags, placeholders, numbers, and code-like tokens.\n"
            "If the input is a single fragment, return a single translated fragment.\n\n"
            f"Text:\n{text}\n\n"
            "Translation:\n"
        )

    def _render_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        prompt = self._build_user_prompt(text, source_lang, target_lang)
        messages = [{"role": "user", "content": prompt}]

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

        fence_match = CODE_FENCE_PATTERN.match(text)
        if fence_match:
            text = fence_match.group(1).strip()

        text = LABEL_PATTERN.sub("", text).strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, str):
                text = parsed.strip()
        except json.JSONDecodeError:
            pass

        return text.strip()

    def _max_new_tokens(self, input_token_count: int) -> int:
        from ..config import config

        dynamic_limit = int(input_token_count * 1.8) + 24
        return max(24, min(config.LLM_TRANSLATION_MAX_NEW_TOKENS, dynamic_limit))

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

            pad_token_id = (
                self.tokenizer.pad_token_id
                if self.tokenizer.pad_token_id is not None
                else self.tokenizer.eos_token_id
            )
            with torch.inference_mode():
                generated = self.model.generate(
                    **inputs,
                    do_sample=False,
                    num_beams=1,
                    use_cache=True,
                    max_new_tokens=self._max_new_tokens(max_input_token_count),
                    pad_token_id=pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                )

        translated = []
        for row in generated:
            output_ids = row[input_width:]
            decoded = self.tokenizer.decode(output_ids, skip_special_tokens=True)
            cleaned = self._clean_output(decoded)
            if not cleaned:
                return None
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
