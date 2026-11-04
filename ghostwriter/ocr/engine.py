"""PaddleOCR-Engine (vereinfachte Übernahme aus digitizeMyBook)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ghostwriter.ocr.text_cleanup import cleanup_german_ocr

logger = logging.getLogger(__name__)

_pipeline: Any | None = None


def _device() -> str:
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu"
    except Exception:
        logger.debug("Paddle CUDA-Check fehlgeschlagen", exc_info=True)
    return "cpu"


def get_pipeline() -> Any:
    """Lädt (cached) PP-OCRv5 deutsch."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    from paddleocr import PaddleOCR

    device = _device()
    logger.info("OCR-Gerät: %s", device)
    _pipeline = PaddleOCR(
        device=device,
        lang="german",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=True,
        use_textline_orientation=False,
        text_det_limit_side_len=2400,
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        text_rec_score_thresh=0.45,
    )
    return _pipeline


def clear_pipeline() -> None:
    """Gibt die OCR-Pipeline und möglichst GPU-Speicher frei."""
    global _pipeline
    import gc

    if _pipeline is not None:
        close = getattr(_pipeline, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                logger.debug("Pipeline close fehlgeschlagen", exc_info=True)
        _pipeline = None
    gc.collect()
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            paddle.device.cuda.empty_cache()
    except Exception:
        pass


def ocr_image(image_path: Path) -> str:
    """OCR für eine Bilddatei; gibt bereinigten Text zurück."""
    pipeline = get_pipeline()
    raw = pipeline.predict(str(image_path))
    texts: list[str] = []
    for item in raw or []:
        texts.extend(_texts_from_result(item))
    joined = "\n".join(t for t in texts if t.strip())
    return cleanup_german_ocr(joined)


def _texts_from_result(result: Any) -> list[str]:
    if result is None:
        return []
    if isinstance(result, dict):
        for key in ("rec_texts", "texts", "text"):
            value = result.get(key)
            if isinstance(value, list):
                return [str(v) for v in value]
            if isinstance(value, str):
                return [value]
    # PaddleOCR result objects
    for attr in ("rec_texts", "texts"):
        value = getattr(result, attr, None)
        if isinstance(value, list):
            return [str(v) for v in value]
    if hasattr(result, "json"):
        try:
            data = result.json
            if callable(data):
                data = data()
            return _texts_from_result(data)
        except Exception:
            pass
    return []
