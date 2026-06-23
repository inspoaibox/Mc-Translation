"""
MarianMT 模型封装
"""
from transformers import MarianMTModel, MarianTokenizer
from typing import Optional, Dict
from threading import Lock
import os
import time
import torch
from .formatting import translate_preserving_line_format_batched
from .generation import batched, generation_token_limit, model_load_kwargs
from .metrics import TranslationMetrics, TranslationResult
from .ct2_utils import get_ct2_model_dir, has_ct2_model_files

class MarianTranslator:
    """MarianMT 翻译器"""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self.models: Dict[str, tuple] = {}  # 缓存已加载的模型
        self.ct2_models: Dict[str, tuple] = {}
        self._load_lock = Lock()
        self._ct2_load_lock = Lock()

    def _load_model(self, model_name: str) -> tuple:
        """加载模型和分词器"""
        if model_name in self.models:
            return self.models[model_name]

        with self._load_lock:
            if model_name in self.models:
                return self.models[model_name]

            try:
                print(f"正在从本地缓存加载 MarianMT 模型: {model_name}")
                tokenizer = MarianTokenizer.from_pretrained(model_name, local_files_only=True)
                model = MarianMTModel.from_pretrained(
                    model_name,
                    local_files_only=True,
                    **model_load_kwargs(self.device)
                ).to(self.device)
                model.eval()
                self.models[model_name] = (tokenizer, model)
                return tokenizer, model
            except Exception as e:
                print(f"加载 MarianMT 模型失败: {str(e)}")
                return None, None

    def _load_ct2_model(self, model_name: str) -> tuple:
        """加载已转换的 CTranslate2 MarianMT 模型。"""
        if model_name in self.ct2_models:
            return self.ct2_models[model_name]

        with self._ct2_load_lock:
            if model_name in self.ct2_models:
                return self.ct2_models[model_name]

            try:
                import ctranslate2
                from ..config import config

                model_dir = get_ct2_model_dir(model_name)
                if not has_ct2_model_files(model_name):
                    return None, None

                print(f"正在加载 MarianMT CTranslate2 模型: {model_dir}")
                tokenizer = MarianTokenizer.from_pretrained(model_name, local_files_only=True)
                translator = ctranslate2.Translator(
                    model_dir,
                    device="cuda" if self.device == "cuda" else "cpu",
                    compute_type=config.MARIAN_CT2_COMPUTE_TYPE,
                    inter_threads=max(1, config.MARIAN_CT2_INTER_THREADS),
                    intra_threads=max(0, config.MARIAN_CT2_INTRA_THREADS),
                    max_queued_batches=config.MARIAN_CT2_MAX_QUEUED_BATCHES
                )
                self.ct2_models[model_name] = (tokenizer, translator)
                return tokenizer, translator
            except Exception as e:
                print(f"加载 MarianMT CTranslate2 模型失败: {str(e)}")
                return None, None

    def _has_local_model_files(self, model_name: str) -> bool:
        cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
        model_dir_name = model_name.replace("/", "--")
        model_path = os.path.join(cache_dir, f"models--{model_dir_name}")

        if not os.path.isdir(model_path):
            return False

        no_exist_marker = f"{os.sep}.no_exist{os.sep}"
        for root, _, files in os.walk(model_path):
            if no_exist_marker in root:
                continue

            if any(
                file_name in {"pytorch_model.bin", "model.safetensors"}
                or file_name.endswith(".safetensors")
                for file_name in files
            ):
                return True

        return False

    def _resolve_model_name(self, source_lang: str, target_lang: str) -> Optional[str]:
        from ..config import config

        lang_pair = f"{source_lang}-{target_lang}"
        configured_model = config.MARIAN_MODELS.get(lang_pair)
        if configured_model and self._has_local_model_files(configured_model):
            return configured_model

        candidate = f"Helsinki-NLP/opus-mt-{source_lang}-{target_lang}"
        if self._has_local_model_files(candidate):
            return candidate

        return configured_model

    def translate(self, text: str, source_lang: str, target_lang: str,
                  model_name: Optional[str] = None) -> Optional[str]:
        """
        执行翻译

        Args:
            text: 要翻译的文本
            source_lang: 源语言代码
            target_lang: 目标语言代码
            model_name: 可选的模型名称，如果不提供则根据语言对自动选择

        Returns:
            翻译后的文本，失败返回 None
        """
        return self.translate_with_metrics(text, source_lang, target_lang, model_name).text

    def _select_backend(self, model_name: str) -> str:
        from ..config import config

        backend = config.MARIAN_BACKEND
        if backend == "ctranslate2":
            return "ctranslate2"
        if backend == "transformers":
            return "transformers"
        if has_ct2_model_files(model_name):
            return "ctranslate2"
        return "transformers"

    def _translate_with_ct2(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        model_name: str
    ) -> TranslationResult:
        metrics = TranslationMetrics(backend="ctranslate2", actual_model_name=model_name)

        load_start = time.perf_counter()
        tokenizer, translator = self._load_ct2_model(model_name)
        metrics.model_load_time = time.perf_counter() - load_start
        if not tokenizer or not translator:
            return TranslationResult(None, metrics)

        def encode_segment(segment: str) -> list[str]:
            token_ids = tokenizer.encode(
                segment,
                truncation=True,
                max_length=512
            )
            return tokenizer.convert_ids_to_tokens(token_ids)

        def decode_tokens(tokens: list[str]) -> str:
            token_ids = tokenizer.convert_tokens_to_ids(tokens)
            return tokenizer.decode(token_ids, skip_special_tokens=True)

        def translate_segments(segments: list[str]) -> Optional[list[str]]:
            translated_texts = []

            for chunk in batched(segments):
                batch_start = time.perf_counter()
                source_tokens = [encode_segment(item) for item in chunk]
                max_input_length = max((len(item) for item in source_tokens), default=1)
                results = translator.translate_batch(
                    source_tokens,
                    beam_size=1,
                    max_batch_size=len(source_tokens),
                    max_input_length=512,
                    max_decoding_length=generation_token_limit(max_input_length)
                )
                translated_texts.extend(decode_tokens(result.hypotheses[0]) for result in results)
                metrics.inference_time += time.perf_counter() - batch_start
                metrics.segment_count += len(chunk)
                metrics.batch_count += 1

            return translated_texts

        def translate_segment(segment: str) -> Optional[str]:
            translated = translate_segments([segment])
            return translated[0] if translated else None

        format_start = time.perf_counter()
        translated_text = translate_preserving_line_format_batched(text, translate_segments, translate_segment)
        format_total = time.perf_counter() - format_start
        metrics.format_time = max(0.0, format_total - metrics.inference_time)
        return TranslationResult(translated_text, metrics)

    def translate_with_metrics(self, text: str, source_lang: str, target_lang: str,
                               model_name: Optional[str] = None) -> TranslationResult:
        metrics = TranslationMetrics(backend="transformers")

        try:
            # 如果没有指定模型，根据语言对选择
            if not model_name:
                model_name = self._resolve_model_name(source_lang, target_lang)

                if not model_name:
                    print(f"MarianMT 不支持语言对: {source_lang}-{target_lang}")
                    return TranslationResult(None, metrics)

            backend = self._select_backend(model_name)
            if backend == "ctranslate2":
                # 优先使用 CTranslate2 后端；若 CT2 模型不可用或翻译失败，
                # 回退到 transformers 后端（下方代码）。
                ct2_result = self._translate_with_ct2(text, source_lang, target_lang, model_name)
                if ct2_result.text is not None:
                    return ct2_result
                print(f"MarianMT CTranslate2 不可用或失败，回退到 transformers: {model_name}")

            # 加载模型
            metrics.actual_model_name = model_name
            load_start = time.perf_counter()
            tokenizer, model = self._load_model(model_name)
            metrics.model_load_time = time.perf_counter() - load_start
            if not tokenizer or not model:
                return TranslationResult(None, metrics)

            def translate_segments(segments: list[str]) -> Optional[list[str]]:
                translated_texts = []

                for chunk in batched(segments):
                    batch_start = time.perf_counter()
                    inputs = tokenizer(
                        chunk,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=512
                    ).to(self.device)

                    with torch.inference_mode():
                        translated = model.generate(
                            **inputs,
                            num_beams=3,
                            do_sample=False,
                            use_cache=True,
                            max_new_tokens=generation_token_limit(inputs["input_ids"].shape[1])
                        )

                    translated_texts.extend(tokenizer.batch_decode(translated, skip_special_tokens=True))
                    metrics.inference_time += time.perf_counter() - batch_start
                    metrics.segment_count += len(chunk)
                    metrics.batch_count += 1

                return translated_texts

            def translate_segment(segment: str) -> Optional[str]:
                segment_start = time.perf_counter()
                inputs = tokenizer(
                    segment,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                ).to(self.device)

                with torch.inference_mode():
                    translated = model.generate(
                        **inputs,
                        num_beams=3,
                        do_sample=False,
                        use_cache=True,
                        max_new_tokens=generation_token_limit(inputs["input_ids"].shape[1])
                    )

                decoded = tokenizer.decode(translated[0], skip_special_tokens=True)
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
            print(f"MarianMT 翻译失败: {str(e)}")
            return TranslationResult(None, metrics)

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        """检查语言对是否可用"""
        model_name = self._resolve_model_name(source_lang, target_lang)
        return bool(model_name and self._has_local_model_files(model_name))

    def warm_up(self, pairs=None, max_pairs: int = 2):
        """预热已下载的 MarianMT 模型，不触发联网下载。"""
        warmup_pairs = pairs or ["zh-en", "en-zh"]

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
            }.get(source_lang, "Hello")

            try:
                print(f"正在预热 MarianMT: {pair}")
                self.translate_with_metrics(warmup_text, source_lang, target_lang)
            except Exception as e:
                print(f"MarianMT 预热失败 {pair}: {str(e)}")
