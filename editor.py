#!/usr/bin/env python3
"""Motor de edicao automatizada com FFmpeg."""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from engine_core import ROOT, SIZES, run, probe, resolve, segments_from_config
from engine_render import render_section

def add_music(source, music, output, volume, duration):
    if not music.is_file():
        raise FileNotFoundError(f"Trilha nao encontrada: {music}")
    vol = min(1.0, max(0.0, float(volume)))
    fade_st = max(0, duration - 1.0)
    graph = (f"[0:a:0]volume=1.0[a0];"
             f"[1:a:0]volume={vol},afade=t=out:st={fade_st:.2f}:d={min(1, duration):.2f}[a1];"
             "[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[a]")
    run(["ffmpeg", "-hide_banner", "-y", "-i", source, "-stream_loop", "-1", "-i", music,
         "-filter_complex", graph, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-t", duration, "-movflags", "+faststart", output])

def burn_subtitles(source, srt, output, font_size, crf):
    if not srt.is_file():
        raise FileNotFoundError(f"Legenda nao encontrada: {srt}")
    escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'").replace(",", "\\,")
    style = f"FontName=DejaVu Sans,FontSize={int(font_size)},Outline=2,Shadow=1,Alignment=2,MarginV=65"
    vf = f"subtitles=filename='{escaped}':force_style='{style}'"
    run(["ffmpeg", "-hide_banner", "-y", "-i", source, "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
         "-c:a", "copy", "-movflags", "+faststart", output])

def write_auto_subtitles(video, srt, cfg):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("Para legendas automaticas, instale: pip install faster-whisper") from exc
    model_name = cfg.get("whisper_model", "base")
    language = cfg.get("language", "pt")
    print(f"Transcrevendo com faster-whisper ({model_name}, idioma {language})...")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(video), language=language, vad_filter=True)
    def fmt(t):
        millis = int(round(t * 1000))
        hours, remain = divmod(millis, 3600000)
        mins, remain = divmod(remain, 60000)
        secs, ms = divmod(remain, 1000)
        return f"{hours:02}:{mins:02}:{secs:02},{ms:03}"
    with srt.open("w", encoding="utf-8") as out:
        for i, segment in enumerate(segments, 1):
            out.write(f"{i}\n{fmt(segment.start)} --> {fmt(segment.end)}\n{segment.text.strip()}\n\n")
    return srt.stat().st_size > 0

def edit(config):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg/ffprobe nao instalado. Rode: bash scripts/setup.sh")
    cfg_path = Path(config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = cfg_path.parent
    fmt = cfg.get("format", "reels")
    if fmt not in SIZES:
        raise ValueError(f"Formato invalido: {fmt}; opcoes: {list(SIZES)}")
    w, h = SIZES[fmt]
    output = resolve(base, cfg.get("output", "outputs/final.mp4"))
    output.parent.mkdir(parents=True, exist_ok=True)
    pieces = segments_from_config(cfg, base)
    print(f"Preparando {len(pieces)} cortes, formato {w}x{h}, look {cfg.get('color', 'natural')}")
    with tempfile.TemporaryDirectory(prefix="editor_") as td:
        temp = Path(td)
        rendered = []
        for idx, (file, start, end, has_audio) in enumerate(pieces):
            video = temp / f"take_{idx:04}.mp4"
            render_section(file, start, end, has_audio, video, w, h, cfg, idx, len(pieces))
            rendered.append(video)
        merged = temp / "merged.mp4"
        if len(rendered) == 1:
            shutil.copyfile(rendered[0], merged)
        else:
            manifest = temp / "concat.txt"
            manifest.write_text("".join(f"file '{str(v)}'\n" for v in rendered), encoding="utf-8")
            run(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0", "-i", manifest,
                 "-c", "copy", "-movflags", "+faststart", merged])
        current = merged
        if cfg.get("music"):
            song = resolve(base, cfg["music"])
            mixed = temp / "mixed.mp4"
            duration, _ = probe(current)
            add_music(current, song, mixed, cfg.get("music_volume", 0.16), duration)
            current = mixed
        subtitles = cfg.get("subtitles")
        if subtitles:
            if subtitles == "auto":
                srt = temp / "auto.srt"
                if not write_auto_subtitles(current, srt, cfg):
                    srt = None
            else:
                srt = resolve(base, subtitles)
            if srt:
                captioned = temp / "captioned.mp4"
                burn_subtitles(current, srt, captioned, cfg.get("font_size", 20), cfg.get("crf", 20))
                current = captioned
        shutil.copyfile(current, output)
    length, _ = probe(output)
    print(f"✅ Pronto: {output} ({length:.1f}s)")
    return output

def main():
    parser = argparse.ArgumentParser(description="Editor automatizado de videos com FFmpeg")
    parser.add_argument("config", nargs="?", default=str(ROOT / "edit.json"), help="Arquivo JSON de configuracao")
    args = parser.parse_args()
    try:
        edit(args.config)
    except (ValueError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as err:
        print(f"ERRO: {err}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
