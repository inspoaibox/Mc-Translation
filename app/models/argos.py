"""
Argos Translate 模型封装
"""
import argostranslate.package
import argostranslate.translate
from typing import Dict, Optional
from .formatting import translate_preserving_line_format

class ArgosTranslator:
    """Argos 翻译器"""

    def __init__(self):
        self._translations: Dict[str, object] = {}
        self._installed_pairs = set()
        self.refresh_installed_languages()

    def refresh_installed_languages(self):
        """刷新已安装语言包缓存，不在翻译请求中联网下载。"""
        self._installed_pairs.clear()
        self._translations.clear()

        try:
            languages = argostranslate.translate.get_installed_languages()
            language_by_code = {language.code: language for language in languages}

            for source in languages:
                for target in languages:
                    if source.code == target.code:
                        continue

                    try:
                        translation = source.get_translation(target)
                    except Exception:
                        translation = None

                    if translation:
                        pair = f"{source.code}-{target.code}"
                        self._installed_pairs.add(pair)
                        self._translations[pair] = translation

            print(f"Argos 已缓存语言对: {len(self._installed_pairs)}")
        except Exception as e:
            print(f"刷新 Argos 语言缓存失败: {str(e)}")

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
            pair = f"{source_lang}-{target_lang}"
            translation = self._translations.get(pair)

            if not translation:
                # 管理后台刚安装语言包后，当前进程可能还没刷新缓存。
                self.refresh_installed_languages()
                translation = self._translations.get(pair)

            if not translation:
                print(f"Argos 未安装语言包: {source_lang} -> {target_lang}")
                return None

            return translate_preserving_line_format(text, translation.translate)

        except Exception as e:
            print(f"Argos 翻译失败: {str(e)}")
            return None

    def is_available(self, source_lang: str, target_lang: str) -> bool:
        """检查语言对是否可用"""
        return f"{source_lang}-{target_lang}" in self._installed_pairs

    def warm_up(self, pairs=None, max_pairs: int = 4):
        """预热常用语言包，避免首个客户请求承担初始化成本。"""
        warmup_pairs = pairs or sorted(self._installed_pairs)

        for index, pair in enumerate(warmup_pairs):
            if index >= max_pairs:
                break

            if pair not in self._installed_pairs:
                continue

            source_lang, target_lang = pair.split("-", 1)
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
                print(f"正在预热 Argos: {pair}")
                self.translate(warmup_text, source_lang, target_lang)
            except Exception as e:
                print(f"Argos 预热失败 {pair}: {str(e)}")
