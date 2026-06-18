"""
NLLB-200 model wrapper.
"""
from threading import Lock
from typing import Optional
import time

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from .formatting import translate_preserving_line_format_batched
from .generation import batched, generation_token_limit, model_load_kwargs
from .metrics import TranslationMetrics, TranslationResult


class NLLBTranslator:
    """NLLB-200 翻译器"""

    LANG_CODE_MAP = {
        "zh": "zho_Hans",
        "zt": "zho_Hant",
        "en": "eng_Latn",
        "ja": "jpn_Jpan",
        "ko": "kor_Hang",
        "fr": "fra_Latn",
        "de": "deu_Latn",
        "es": "spa_Latn",
        "ru": "rus_Cyrl",
        "ar": "arb_Arab",
        "hi": "hin_Deva",
        "th": "tha_Thai",
    }

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.tokenizer = None
        self.model = None
        self._load_lock = Lock()

    def _load_model(self):
        if self.model is not None:
            return

        with self._load_lock:
            if self.model is not None:
                return

            try:
                print(f"正在从本地缓存加载 NLLB 模型: {self.model_name}")
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=True
                )
                self.model = AutoModelForSeq2SeqLM.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    **model_load_kwargs(self.device)
                ).to(self.device)
                self.model.eval()
            except Exception as e:
                print(f"加载 NLLB 模型失败: {str(e)}")
                self.tokenizer = None
                self.model = None

    def _map_language_code(self, lang: str) -> str:
        return self.LANG_CODE_MAP.get(lang, lang)

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        return self.translate_with_metrics(text, source_lang, target_lang).text

    def translate_with_metrics(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        metrics = TranslationMetrics(backend="transformers", actual_model_name=self.model_name)

        try:
            load_start = time.perf_counter()
            self._load_model()
            metrics.model_load_time = time.perf_counter() - load_start
            if not self.tokenizer or not self.model:
                return TranslationResult(None, metrics)

            src_lang = self._map_language_code(source_lang)
            tgt_lang = self._map_language_code(target_lang)
            self.tokenizer.src_lang = src_lang

            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)
            if forced_bos_token_id is None or forced_bos_token_id < 0:
                print(f"NLLB 不支持目标语言: {target_lang} ({tgt_lang})")
                return TranslationResult(None, metrics)

            def translate_segments(segments: list[str]) -> Optional[list[str]]:
                translated_texts = []

                for chunk in batched(segments):
                    batch_start = time.perf_counter()
                    inputs = self.tokenizer(
                        chunk,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512
                    ).to(self.device)

                    with torch.inference_mode():
                        translated = self.model.generate(
                            **inputs,
                            forced_bos_token_id=forced_bos_token_id,
                            num_beams=1,
                            do_sample=False,
                            use_cache=True,
                            max_new_tokens=generation_token_limit(inputs["input_ids"].shape[1])
                        )

                    translated_texts.extend(self.tokenizer.batch_decode(translated, skip_special_tokens=True))
                    metrics.inference_time += time.perf_counter() - batch_start
                    metrics.segment_count += len(chunk)
                    metrics.batch_count += 1

                return translated_texts

            def translate_segment(segment: str) -> Optional[str]:
                segment_start = time.perf_counter()
                inputs = self.tokenizer(
                    segment,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512
                ).to(self.device)

                with torch.inference_mode():
                    translated = self.model.generate(
                        **inputs,
                        forced_bos_token_id=forced_bos_token_id,
                        num_beams=1,
                        do_sample=False,
                        use_cache=True,
                        max_new_tokens=generation_token_limit(inputs["input_ids"].shape[1])
                    )

                decoded = self.tokenizer.decode(translated[0], skip_special_tokens=True)
                metrics.inference_time += time.perf_counter() - segment_start
                metrics.segment_count += 1
                metrics.batch_count += 1
                return decoded

            format_start = time.perf_counter()
            translated_text = translate_preserving_line_format_batched(text, translate_segments, translate_segment)
            format_total = time.perf_counter() - format_start
            metrics.format_time = max(0.0, format_total - metrics.inference_time)
            return TranslationResult(translated_text, metrics)

        except Exception as e:
            print(f"NLLB 翻译失败: {str(e)}")
            return TranslationResult(None, metrics)

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        return (
            self._map_language_code(source_lang) in self.LANG_CODE_MAP.values()
            and self._map_language_code(target_lang) in self.LANG_CODE_MAP.values()
        )

    def warm_up(self, pairs=None, max_pairs: int = 1):
        """预热 NLLB 模型，不触发联网下载。"""
        warmup_pairs = pairs or ["zh-en"]

        for index, pair in enumerate(warmup_pairs):
            if index >= max_pairs:
                break
            if "-" not in pair:
                continue

            source_lang, target_lang = pair.split("-", 1)
            if not self.is_available(source_lang, target_lang):
                continue

            warmup_text = {
                "zh": "你好",
                "en": "Hello",
                "ja": "こんにちは",
                "ko": "안녕하세요",
                "fr": "Bonjour",
                "de": "Hallo",
                "es": "Hola",
                "ru": "Привет",
                "ar": "مرحبا",
                "hi": "नमस्ते",
                "th": "สวัสดี",
            }.get(source_lang, "Hello")

            try:
                print(f"正在预热 NLLB: {pair}")
                self.translate_with_metrics(warmup_text, source_lang, target_lang)
            except Exception as e:
                print(f"NLLB 预热失败 {pair}: {str(e)}")
