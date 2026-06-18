"""
MarianMT 模型封装
"""
from transformers import MarianMTModel, MarianTokenizer
from typing import Optional, Dict
from threading import Lock
import os
import torch
from .formatting import translate_preserving_line_format

class MarianTranslator:
    """MarianMT 翻译器"""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self.models: Dict[str, tuple] = {}  # 缓存已加载的模型
        self._load_lock = Lock()

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
                model = MarianMTModel.from_pretrained(model_name, local_files_only=True).to(self.device)
                model.eval()
                self.models[model_name] = (tokenizer, model)
                return tokenizer, model
            except Exception as e:
                print(f"加载 MarianMT 模型失败: {str(e)}")
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
        try:
            # 如果没有指定模型，根据语言对选择
            if not model_name:
                model_name = self._resolve_model_name(source_lang, target_lang)

                if not model_name:
                    print(f"MarianMT 不支持语言对: {source_lang}-{target_lang}")
                    return None

            # 加载模型
            tokenizer, model = self._load_model(model_name)
            if not tokenizer or not model:
                return None

            def translate_segment(segment: str) -> Optional[str]:
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
                        num_beams=1,
                        max_new_tokens=256
                    )

                return tokenizer.decode(translated[0], skip_special_tokens=True)

            return translate_preserving_line_format(text, translate_segment)

        except Exception as e:
            print(f"MarianMT 翻译失败: {str(e)}")
            return None

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        """检查语言对是否可用"""
        model_name = self._resolve_model_name(source_lang, target_lang)
        return bool(model_name and self._has_local_model_files(model_name))
