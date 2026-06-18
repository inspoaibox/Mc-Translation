"""
M2M100 模型封装
"""
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
from typing import Optional
from threading import Lock
import torch
from .formatting import translate_preserving_line_format_batched
from .generation import batched, generation_token_limit, model_load_kwargs

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
        self._load_lock = Lock()

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
        try:
            # 确保模型已加载
            self._load_model()
            if not self.tokenizer or not self.model:
                return None

            # 映射语言代码
            src_lang = self._map_language_code(source_lang)
            tgt_lang = self._map_language_code(target_lang)

            # 设置源语言
            self.tokenizer.src_lang = src_lang

            # 生成翻译（指定目标语言）
            forced_bos_token_id = self.tokenizer.get_lang_id(tgt_lang)

            def translate_segments(segments: list[str]) -> Optional[list[str]]:
                translated_texts = []

                for chunk in batched(segments):
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

                return translated_texts

            def translate_segment(segment: str) -> Optional[str]:
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

                return self.tokenizer.decode(translated[0], skip_special_tokens=True)

            return translate_preserving_line_format_batched(text, translate_segments, translate_segment)

        except Exception as e:
            print(f"M2M100 翻译失败: {str(e)}")
            return None

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        """检查语言对是否可用"""
        src_lang = self._map_language_code(source_lang)
        tgt_lang = self._map_language_code(target_lang)
        return src_lang in self.LANG_CODE_MAP.values() and tgt_lang in self.LANG_CODE_MAP.values()
