"""
NLLB-200 model wrapper.
"""
from threading import Lock
from typing import Optional

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from .formatting import translate_preserving_line_format_batched
from .generation import batched, generation_token_limit, model_load_kwargs


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
        try:
            self._load_model()
            if not self.tokenizer or not self.model:
                return None

            src_lang = self._map_language_code(source_lang)
            tgt_lang = self._map_language_code(target_lang)
            self.tokenizer.src_lang = src_lang

            forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_lang)
            if forced_bos_token_id is None or forced_bos_token_id < 0:
                print(f"NLLB 不支持目标语言: {target_lang} ({tgt_lang})")
                return None

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
            print(f"NLLB 翻译失败: {str(e)}")
            return None

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        return (
            self._map_language_code(source_lang) in self.LANG_CODE_MAP.values()
            and self._map_language_code(target_lang) in self.LANG_CODE_MAP.values()
        )
