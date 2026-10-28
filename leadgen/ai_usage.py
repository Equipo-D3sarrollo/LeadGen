"""Registro local y mínimo del uso de IA."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

USAGE_LOG_PATH = Path("ai_usage.jsonl")


def registrar_uso(
    flujo: str,
    modelo: str,
    respuesta,
    ruta: str | Path | None = None,
    proveedor: str = "openai",
    estado: str = "success",
    duracion_ms: int | None = None,
    ejecucion_id: str | None = None,
    tipo_error: str | None = None,
) -> None:
    """Registra uso técnico sin guardar prompts, respuestas ni datos del negocio."""
    usage = getattr(respuesta, "usage", None)

    registro = {
        "fecha_hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "proveedor": proveedor,
        "flujo": flujo,
        "modelo": modelo,
        "estado": estado,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    if duracion_ms is not None:
        registro["duracion_ms"] = duracion_ms
    if ejecucion_id is not None:
        registro["ejecucion_id"] = ejecucion_id
    if tipo_error is not None:
        registro["tipo_error"] = tipo_error
    for campo in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        valor = getattr(usage, campo, None)
        if valor is not None:
            registro[campo] = valor
    detalles_entrada = getattr(usage, "input_token_details", None)
    cache_leida = getattr(detalles_entrada, "cached_tokens", None)
    if cache_leida is not None:
        registro["cached_input_tokens"] = cache_leida

    try:
        destino = Path(ruta) if ruta is not None else USAGE_LOG_PATH
        with destino.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError) as error:
        print(f"[ai_usage] No se pudo registrar uso de {flujo}: {type(error).__name__}")
