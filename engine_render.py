from engine_core import LOOKS, run

def render_section(file, start, end, has_audio, output, width, height, cfg, pos, total):
    duration = round(end - start, 4)
    fade = min(max(0, float(cfg.get("fade_duration", 0.18))), duration / 4)
    fit = cfg.get("fit", "fill")
    if fit == "fill":
        transform = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    elif fit == "pad":
        transform = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    else:
        raise ValueError("fit deve ser 'fill' ou 'pad'")
    look = cfg.get("color", "natural")
    if look not in LOOKS:
        raise ValueError(f"Cor invalida: {look}. Opcoes: {', '.join(LOOKS)}")
    video_filters = ["setpts=PTS-STARTPTS", transform, LOOKS[look],
                     f"fps={int(cfg.get('fps', 30))}", "format=yuv420p", "setsar=1"]
    audio_filters = ["aresample=48000", "asetpts=PTS-STARTPTS"]
    if fade > 0 and total > 1:
        if pos > 0:
            video_filters.append(f"fade=t=in:st=0:d={fade:.3f}")
            audio_filters.append(f"afade=t=in:st=0:d={fade:.3f}")
        if pos < total - 1:
            st = max(0, duration - fade)
            video_filters.append(f"fade=t=out:st={st:.3f}:d={fade:.3f}")
            audio_filters.append(f"afade=t=out:st={st:.3f}:d={fade:.3f}")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", file]
    if not has_audio:
        cmd += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    audio_stream = "[0:a:0]" if has_audio else "[1:a:0]"
    graph = f"[0:v:0]{','.join(video_filters)}[v];{audio_stream}{','.join(audio_filters)}[a]"
    cmd += ["-filter_complex", graph, "-map", "[v]", "-map", "[a]", "-t", duration,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(cfg.get("crf", 20)),
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", output]
    run(cmd)
