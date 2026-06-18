"""
Helpers for local CTranslate2 model conversion and discovery.
"""
import os
import re
from typing import Optional

from ..config import config


def safe_model_dir_name(model_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", model_name).strip("_")


def get_ct2_model_dir(model_name: str) -> str:
    return os.path.abspath(os.path.join(
        os.path.expanduser(config.CTRANSLATE2_MODELS_DIR),
        safe_model_dir_name(model_name),
    ))


def has_ct2_model_files(model_name: str) -> bool:
    model_dir = get_ct2_model_dir(model_name)
    return (
        os.path.isdir(model_dir)
        and os.path.isfile(os.path.join(model_dir, "model.bin"))
        and os.path.isfile(os.path.join(model_dir, "config.json"))
    )


def get_huggingface_snapshot_path(model_name: str) -> Optional[str]:
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    model_dir_name = model_name.replace("/", "--")
    model_cache = os.path.join(cache_dir, f"models--{model_dir_name}")
    snapshots_dir = os.path.join(model_cache, "snapshots")

    if not os.path.isdir(snapshots_dir):
        return None

    ref_path = os.path.join(model_cache, "refs", "main")
    if os.path.isfile(ref_path):
        with open(ref_path, "r", encoding="utf-8") as file:
            revision = file.read().strip()
        snapshot_path = os.path.join(snapshots_dir, revision)
        if os.path.isdir(snapshot_path):
            return snapshot_path

    snapshots = [
        os.path.join(snapshots_dir, item)
        for item in os.listdir(snapshots_dir)
        if os.path.isdir(os.path.join(snapshots_dir, item))
    ]
    if not snapshots:
        return None

    return max(snapshots, key=os.path.getmtime)
