"""
Translation timing metadata shared by all model backends.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TranslationMetrics:
    backend: str = "unknown"
    actual_model_name: Optional[str] = None
    model_load_time: float = 0.0
    inference_time: float = 0.0
    format_time: float = 0.0
    segment_count: int = 0
    batch_count: int = 0

    def to_response_ms(self) -> dict:
        return {
            "backend": self.backend,
            "actual_model_name": self.actual_model_name,
            "model_load_ms": round(self.model_load_time * 1000, 2),
            "inference_ms": round(self.inference_time * 1000, 2),
            "format_ms": round(self.format_time * 1000, 2),
            "segment_count": self.segment_count,
            "batch_count": self.batch_count,
        }


@dataclass
class TranslationResult:
    text: Optional[str]
    metrics: TranslationMetrics = field(default_factory=TranslationMetrics)
