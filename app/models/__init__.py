"""
翻译模型模块
"""
from .argos import ArgosTranslator
from .marian import MarianTranslator
from .m2m100 import M2M100Translator
from .nllb import NLLBTranslator

__all__ = ["ArgosTranslator", "MarianTranslator", "M2M100Translator", "NLLBTranslator"]
