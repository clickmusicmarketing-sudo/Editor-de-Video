# Editor de Vídeo para Codex

Editor automatizado com Python 3 + FFmpeg. Funcionalidades: cortar e juntar trechos, eliminar pausas silenciosas (opcional), tratamento básico de cores, fades, música e legendas SRT ou transcrição opcional via faster-whisper.

## Como usar no Codex Cloud

1. Selecione este repositório ao criar o ambiente Codex.
2. Em Setup script, use `sudo apt-get update && sudo apt-get install -y ffmpeg` quando necessário. FFmpeg e ffprobe precisam estar disponíveis.
3. Disponibilize `media/video1.mp4` no ambiente **por um canal privado**. O Codex Cloud NÃO acessa automaticamente arquivos do seu computador; como este repositório é público, não faça commit de vídeos de clientes.
4. Rode `python3 editor.py edit.json`.
5. Retire o vídeo gerado de `outputs/final.mp4` do ambiente do Codex.

Configurações: `format` = `reels` (1080×1920), `youtube` (1920×1080), `square` (1080×1080) ou `preview` (540×960); `color` = `natural`, `cinematic`, `vibrant`, `warm` ou `none`; `fit` = `fill` ou `pad`.

Cortes personalizados no `edit.json`:

```json
"segments": [{"file":"media/video1.mp4","start":1,"end":4},{"file":"media/video1.mp4","start":8,"end":12}]
```

Para trilha: `"music": "assets/trilha.mp3"` e `"music_volume": 0.16`. Para legenda SRT: `"subtitles": "assets/legenda.srt"`. Legenda automática: `pip install faster-whisper` e `"subtitles": "auto"` (requer download do modelo). Corte automático de pausas: `"silence": {"enabled": true}`.

O editor não escolhe sozinho as melhores cenas e os perfis de cor são filtros fixos, não correções inteligentes por cena. Peça ao Codex para analisar o material e definir os trechos. A renderização na nuvem depende de armazenamento, recursos e limites de execução.
