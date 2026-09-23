#!/usr/bin/env python3
"""Gera narracao por cena com edge-tts, concatena, mede duracoes e escreve SRT."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
AUDIO = OUT / "audio"


def find_edge_tts() -> str:
    exe = shutil.which("edge-tts") or str(Path.home() / ".local/bin/edge-tts")
    if not Path(exe).exists():
        sys.exit("edge-tts nao encontrado. Instale: pipx install edge-tts")
    return exe


def duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return float(out)


def srt_ts(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def wrap(text: str, width: int = 46) -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:2])


def main() -> None:
    cfg = json.loads((HERE / "script.json").read_text())
    AUDIO.mkdir(parents=True, exist_ok=True)
    exe = find_edge_tts()

    durations, files = [], []
    for i, scene in enumerate(cfg["scenes"], 1):
        mp3 = AUDIO / f"{i:02d}-{scene['id']}.mp3"
        subprocess.run(
            [
                exe,
                "--voice",
                cfg["voice"],
                "--rate",
                cfg.get("rate", "+0%"),
                "--text",
                scene["narration"],
                "--write-media",
                str(mp3),
            ],
            check=True,
        )
        durations.append(duration(mp3))
        files.append(mp3)
        print(f"  {scene['id']}: {durations[-1]:.2f}s")

    concat = OUT / "concat.txt"
    concat.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c",
            "copy",
            str(OUT / "voice.mp3"),
        ],
        check=True,
    )

    (OUT / "durations.json").write_text(json.dumps(durations, indent=2))

    srt, t = [], 0.0
    for i, (scene, d) in enumerate(zip(cfg["scenes"], durations), 1):
        srt.append(
            f"{i}\n{srt_ts(t)} --> {srt_ts(t + d)}\n{wrap(scene['narration'])}\n"
        )
        t += d
    (OUT / "subs.srt").write_text("\n".join(srt))

    print(
        f"total narracao: {t:.2f}s -> out/voice.mp3, out/subs.srt, out/durations.json"
    )


if __name__ == "__main__":
    main()
