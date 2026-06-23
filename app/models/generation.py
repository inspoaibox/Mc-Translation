"""
Shared generation helpers for local translation models.
"""
from typing import List, Optional

import torch

from ..config import config


def generation_token_limit(input_token_count: int) -> int:
    """
    计算翻译输出的 token 上限

    翻译输出通常是输入的 1.5-2 倍：
    - 英译中：缩短 30-50%
    - 中译英：增长 50-100%

    使用 2.0 倍数确保不截断
    """
    dynamic_limit = int(input_token_count * 2.0) + 32
    return max(32, min(config.TRANSLATION_MAX_NEW_TOKENS, dynamic_limit))


def batched(items: List[str], size: Optional[int] = None):
    batch_size = max(1, size or config.TRANSLATION_BATCH_SIZE)
    for index in range(0, len(items), batch_size):
        yield items[index:index + batch_size]


def model_load_kwargs(device: str) -> dict:
    """Use fp16 on CUDA to reduce memory bandwidth and improve inference speed."""
    if device == "cuda" and torch.cuda.is_available():
        return {"torch_dtype": torch.float16}
    return {}
