"""
M2M100 模型封装
"""
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
from typing import Optional
from threading import Lock
import time
import torch
from .formatting import translate_preserving_line_format_batched
from .generation import batched, generation_token_limit, model_load_kwargs
from .metrics import TranslationMetrics, TranslationResult
from .ct2_utils import get_ct2_model_dir, has_ct2_model_files

class M2M100Translator:
    """M2M100 翻译器"""

    # 语言代码映射（M2M100 使用特定的语言代码）
    LANG_CODE_MAP = {
        "zh": "zh",
        "en": "en",
        "ja": "ja",
        "ko": "ko",
        "fr": "fr",
        "de": "de",
        "es": "es",
        "ru": "ru",
    }

    def __init__(self, model_name: str = "facebook/m2m100_418M", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.tokenizer: Optional[M2M100Tokenizer] = None
        self.model: Optional[M2M100ForConditionalGeneration] = None
        self.ct2_tokenizer: Optional[M2M100Tokenizer] = None
        self.ct2_translator = None
        self._load_lock = Lock()
        self._ct2_load_lock = Lock()
        self._tokenizer_lock = Lock()

    def _load_model(self):
        """延迟加载模型"""
        if self.model is not None:
            return

        with self._load_lock:
            if self.model is not None:
                return

            try:
                print(f"正在从本地缓存加载 M2M100 模型: {self.model_name}")
                self.tokenizer = M2M100Tokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=True
                )
                self.model = M2M100ForConditionalGeneration.from_pretrained(
                    self.model_name,
                    local_files_only=True,
                    **model_load_kwargs(self.device)
                ).to(self.device)
                self.model.eval()
            except Exception as e:
                print(f"加载 M2M100 模型失败: {str(e)}")
                self.tokenizer = None
                self.model = None

    def _load_ct2_model(self):
        """延迟加载已转换的 CTranslate2 M2M100 模型。"""
        if self.ct2_translator is not None:
            return

        with self._ct2_load_lock:
            if self.ct2_translator is not None:
                return

            try:
                import ctranslate2
                from ..config import config

                model_dir = get_ct2_model_dir(self.model_name)
                if not has_ct2_model_files(self.model_name):
                    return

                print(f"正在加载 M2M100 CTranslate2 模型: {model_dir}")
                self.ct2_tokenizer = M2M100Tokenizer.from_pretrained(
                    self.model_name,
                    local_files_only=True
                )
                self.ct2_translator = ctranslate2.Translator(
                    model_dir,
                    device="cuda" if self.device == "cuda" else "cpu",
                    compute_type=config.M2M100_CT2_COMPUTE_TYPE,
                    inter_threads=max(1, config.M2M100_CT2_INTER_THREADS),
                    intra_threads=max(0, config.M2M100_CT2_INTRA_THREADS),
                    max_queued_batches=config.M2M100_CT2_MAX_QUEUED_BATCHES
                )
            except Exception as e:
                print(f"加载 M2M100 CTranslate2 模型失败: {str(e)}")
                self.ct2_tokenizer = None
                self.ct2_translator = None

    def _map_language_code(self, lang: str) -> str:
        """映射语言代码到 M2M100 格式"""
        return self.LANG_CODE_MAP.get(lang, lang)

    def translate(self, text: str, source_lang: str, target_lang: str) -> Optional[str]:
        """
        执行翻译

        Args:
            text: 要翻译的文本
            source_lang: 源语言代码
            target_lang: 目标语言代码

        Returns:
            翻译后的文本，失败返回 None
        """
        return self.translate_with_metrics(text, source_lang, target_lang).text

    def _select_backend(self) -> str:
        from ..config import config

        backend = config.M2M100_BACKEND
        if backend == "ctranslate2":
            return "ctranslate2"
        if backend == "transformers":
            return "transformers"
        if has_ct2_model_files(self.model_name):
            return "ctranslate2"
        return "transformers"

    def _translate_with_ct2(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        metrics = TranslationMetrics(backend="ctranslate2", actual_model_name=self.model_name)

        load_start = time.perf_counter()
        self._load_ct2_model()
        metrics.model_load_time = time.perf_counter() - load_start
        if not self.ct2_tokenizer or not self.ct2_translator:
            return TranslationResult(None, metrics)

        src_lang = self._map_language_code(source_lang)
        tgt_lang = self._map_language_code(target_lang)
        target_lang_token = self.ct2_tokenizer.convert_ids_to_tokens(
            self.ct2_tokenizer.get_lang_id(tgt_lang)
        )

        def encode_segment(segment: str) -> list[str]:
            with self._tokenizer_lock:
                self.ct2_tokenizer.src_lang = src_lang
                token_ids = self.ct2_tokenizer.encode(
                    segment,
                    truncation=True,
                    max_length=1024
                )
            return self.ct2_tokenizer.convert_ids_to_tokens(token_ids)

        def decode_tokens(tokens: list[str]) -> str:
            if tokens and tokens[0] == target_lang_token:
                tokens = tokens[1:]
            token_ids = self.ct2_tokenizer.convert_tokens_to_ids(tokens)
            return self.ct2_tokenizer.decode(token_ids, skip_special_tokens=True)

        def translate_segments(segments: list[str]) -> Optional[list[str]]:
            translated_texts = []

            for chunk in batched(segments):
                batch_start = time.perf_counter()
                source_tokens = [encode_segment(item) for item in chunk]
                max_input_length = max((len(item) for item in source_tokens), default=1)
                target_prefix = [[target_lang_token] for _ in source_tokens]
                results = self.ct2_translator.translate_batch(
                    source_tokens,
                    target_prefix=target_prefix,
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

    def translate_with_metrics(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        metrics = TranslationMetrics(backend="transformers", actual_model_name=self.model_name)

        try:
            backend = self._select_backend()
            if backend == "ctranslate2":
                try:
                    return self._translate_with_ct2(text, source_lang, target_lang)
                except Exception as e:
                    print(f"M2M100 CTranslate2 翻译失败: {str(e)}")
                    return TranslationResult(
                        None,
                        TranslationMetrics(
                            backend="ctranslate2",
                            actual_model_name=self.model_name
                        )
                    )

            # 确保模型已加载
            load_start = time.perf_counter()
            self._load_model()
            metrics.model_load_time = time.perf_counter() - load_start
            if not self.tokenizer or not self.model:
                return TranslationResult(None, metrics)

            # 映射语言代码
            src_lang = self._map_language_code(source_lang)
            tgt_lang = self._map_language_code(target_lang)

            # 生成翻译（指定目标语言）
            forced_bos_token_id = self.tokenizer.get_lang_id(tgt_lang)

            def translate_segments(segments: list[str]) -> Optional[list[str]]:
                translated_texts = []

                for chunk in batched(segments):
                    batch_start = time.perf_counter()
                    with self._tokenizer_lock:
                        self.tokenizer.src_lang = src_lang
                        inputs = self.tokenizer(
                            chunk,
                            return_tensors="pt",
                            padding=True,
                            truncation=True,
                            max_length=1024
                        ).to(self.device)

                    with torch.inference_mode():
                        translated = self.model.generate(
                            **inputs,
                            forced_bos_token_id=forced_bos_token_id,
                            num_beams=3,
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
                with self._tokenizer_lock:
                    self.tokenizer.src_lang = src_lang
                    inputs = self.tokenizer(
                        segment,
                        return_tensors="pt",
                        truncation=True,
                        max_length=1024
                    ).to(self.device)

                with torch.inference_mode():
                    translated = self.model.generate(
                        **inputs,
                        forced_bos_token_id=forced_bos_token_id,
                        num_beams=3,
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
            print(f"M2M100 翻译失败: {str(e)}")
            return TranslationResult(None, metrics)

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        """检查语言对是否可用"""
        src_lang = self._map_language_code(source_lang)
        tgt_lang = self._map_language_code(target_lang)
        return src_lang in self.LANG_CODE_MAP.values() and tgt_lang in self.LANG_CODE_MAP.values()

    def warm_up(self, pairs=None, max_pairs: int = 1):
        """预热 M2M100 模型，不触发联网下载。"""
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
            }.get(source_lang, "Hello")

            try:
                print(f"正在预热 M2M100: {pair}")
                self.translate_with_metrics(warmup_text, source_lang, target_lang)
            except Exception as e:
                print(f"M2M100 预热失败 {pair}: {str(e)}")
