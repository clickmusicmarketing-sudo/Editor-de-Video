#!/usr/bin/env python3
"""Editor de videos reproduzivel com FFmpeg. Python 3.10+."""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIZES = {"reels": (1080, 1920), "youtube": (1920, 1080), "square": (1080, 1080), "preview": (540, 960)}
LOOKS = {
    "natural": "eq=contrast=1.045:brightness=0.008:saturation=1.07,unsharp=5:5:0.25",
    "cinematic": "eq=contrast=1.095:brightness=-0.008:saturation=0.94:gamma=1.02,colorbalance=rs=0.025:bs=-0.025,unsharp=5:5:0.25",
    "vibrant": "eq=contrast=1.075:brightness=0.012:saturation=1.24,unsharp=5:5:0.28",
    "warm": "eq=contrast=1.05:brightness=0.01:saturation=1.10,colorbalance=rs=0.045:bs=-0.035",
    "none": "null",
}


def run(cmd, capture=False):
    print("▶", " ".join(map(str, cmd)))
    result = subprocess.run([str(x) for x in cmd], text=True, capture_output=capture)
    if result.returncode:
        message = (result.stderr or "").strip()[-3500:] if capture else "Confira a mensagem do FFmpeg acima."
        raise RuntimeError(f"Comando falhou: {message}")
    return result


def probe(path):
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                  "-of", "json", path], capture=True)
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not any(x.get("codec_type") == "video" for x in streams):
        raise ValueError(f"Sem faixa de video: {path}")
    return float(data["format"]["duration"]), any(x.get("codec_type") == "audio" for x in streams)


def resolve(base, value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else base / path).resolve()


def keep_after_silence(path, duration, cfg):
    """Retorna trechos com voz/som, preservando pequena margem em cada ponta."""
    threshold = float(cfg.get("noise_db", -32))
    min_silence = float(cfg.get("min_duration", 0.55))
    padding = max(0, float(cfg.get("keep_padding", 0.13)))
    detected = run(["ffmpeg", "-hide_banner", "-i", path, "-af",
                    f"silencedetect=noise={threshold}dB:d={min_silence}", "-f", "null", "-"], capture=True).stderr
    silences = []
    start = None
    for line in detected.splitlines():
        a = re.search(r"silence_start:\s*([\d.]+)", line)
        b = re.search(r"silence_end:\s*([\d.]+)", line)
        if a:
            start = float(a.group(1))
        if b and start is not None:
            silences.append((start, float(b.group(1))))
            start = None
    if start is not None:
        silences.append((start, duration))
    sections, cursor = [], 0.0
    for a, b in silences:
        if a > cursor:
            sections.append((max(0, cursor - padding), min(duration, a + padding)))
        cursor = max(cursor, b)
    if cursor < duration:
        sections.append((max(0, cursor - padding), duration))
    return [(a, b) for a, b in sections if b - a >= 0.22]


def segments_from_config(cfg, base):
    if cfg.get("segments"):
        raw = cfg["segments"]
    else:
        raw = [{"file": p} for p in cfg.get("inputs", [])]
    if not raw:
        raise ValueError("Informe 'inputs' ou 'segments' no edit.json")
    result = []
    for entry in raw:
        if isinstance(entry, str):
            entry = {"file": entry}
        file = resolve(base, entry["file"])
        if not file.is_file():
            raise FileNotFoundError(f"Video nao encontrado: {file}")
        length, audio = probe(file)
        start = float(entry.get("start", 0))
        end = float(entry.get("end", length))
        if not 0 <= start < end <= length + 0.05:
            raise ValueError(f"Corte fora da duracao de {file.name}: {start}-{end} (total {length:.2f}s)")
        if cfg.get("silence", {}).get("enabled") and audio:
            for a, b in keep_after_silence(file, length, cfg["silence"]):
                lo, hi = max(a, start), min(b, end)
                if hi - lo >= 0.22:
                    result.append((file, lo, hi, audio))
        else:
            result.append((file, start, end, audio))
    if not result:
        raise ValueError("Nenhum trecho restante. Desative a remocao de silencio ou ajuste os parametros.")
    return result

