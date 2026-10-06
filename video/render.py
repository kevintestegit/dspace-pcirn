#!/usr/bin/env python3
"""
Render index.html to video with headless Chromium.

Every output frame is sampled at four temporal subframes and the samples are
blended, which is what gives motion its weight: a spring crossing its fastest
point smears, the way an object with mass does. Frames are piped straight into
ffmpeg as rawvideo, so nothing is written to disk but the result.

  .venv/bin/python render.py                 # render the full piece
  .venv/bin/python render.py --beats         # one diagnostic frame per beat
  .venv/bin/python render.py --frame 12.5    # a single frame, for inspection
  .venv/bin/python render.py --fast          # one sample per frame, for layout checks
"""
import argparse, io, os, shutil, subprocess, sys, time
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "index.html")
OUT = os.path.join(HERE, "out")
FPS = 60
SIZE = 1440
SUB = 4


def ffmpeg(args, **kw):
    return subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True, **kw)


def open_page(pw, quiet=True):
    browser = pw.chromium.launch(args=["--force-device-scale-factor=1",
                                       "--disable-background-timer-throttling"])
    ctx = browser.new_context(viewport={"width": SIZE, "height": SIZE},
                              device_scale_factor=1)
    page = ctx.new_page()
    if not quiet:
        page.on("pageerror", lambda e: print("PAGE ERROR:", e, file=sys.stderr))
    page.goto("file://" + PAGE)
    page.wait_for_function("window.__READY === true", timeout=30000)
    return browser, page


def grab(page, t):
    """Seek to t and return the frame as an HxWx3 uint8 array."""
    page.evaluate("t => window.seek(t)", t)
    png = page.screenshot(type="png", animations="disabled")
    with Image.open(io.BytesIO(png)) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def render_frames(page, n_frames, sub, sink=None, label="", t_of=None):
    """Sample each frame `sub` times across its exposure window and blend."""
    if t_of is None:
        t_of = lambda n, k: (n + k / sub) / FPS      # noqa: E731
    for n in range(n_frames):
        acc = None
        for k in range(sub):
            f = grab(page, t_of(n, k))
            # accumulate in a wide dtype: uint8 addition wraps around, which would
            # turn a bright frame into a very dark one
            acc = f.astype(np.int32) if acc is None else acc + f
        img = (np.clip(acc // sub, 0, 255)).astype(np.uint8)
        if sink is not None:
            sink(img, n)
        if label and (n % FPS == 0 or n == n_frames - 1):
            done = (n + 1) / FPS
            print(f"  {label} {done:5.1f}s / {n_frames/FPS:.1f}s", flush=True)
        if sink is None and n % 300 == 0:
            Image.fromarray(img).save(os.path.join(OUT, f"frame-{n:05d}.png"))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", action="store_true", help="one diagnostic frame per beat")
    ap.add_argument("--frame", type=float, help="export a single frame at t seconds")
    ap.add_argument("--fast", action="store_true", help="one sample per frame")
    ap.add_argument("--audio", default=os.path.join(OUT, "audio.wav"))
    ap.add_argument("--mp4", default=os.path.join(OUT, "dspace-motion.mp4"))
    ap.add_argument("--sub", type=int, default=SUB)
    args = ap.parse_args()
    total = int(round(30.0 * FPS))
    os.makedirs(OUT, exist_ok=True)

    with sync_playwright() as pw:
        browser, page = open_page(pw, quiet=False)
        t0 = time.time()

        if args.beats:
            n = 60
            render_frames(page, 60, 1,
                          sink=lambda img, n: Image.fromarray(img).save(
                              os.path.join(OUT, f"beat-{n+1:02d}.png")),
                          label="beat", t_of=lambda n, k: (n + 0.96) * 0.5)  # settled frame for each beat
            return
        if args.frame is not None:
            Image.fromarray(grab(page, args.frame)).save(
                os.path.join(OUT, "frame.png"))
            print(f"ok -> out/frame.png  (t={args.frame})")
            return

        proc = subprocess.Popen(
            ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{SIZE}x{SIZE}", "-r", str(FPS), "-i", "pipe:0",
             "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
             # the last frame is a keyframe like the first, so the loop seam is coded
             # from the same source by both ends and comes out identical
             "-force_key_frames", f"expr:eq(n,{total-1})",
             "-pix_fmt", "yuv420p", os.path.join(OUT, "_video.mp4")],
            stdin=subprocess.PIPE)
        print(f"rendering {total} frames at {SIZE}x{SIZE}, "
              f"{args.sub if not args.fast else 1} samples/frame", flush=True)

        def sink(img, n):
            assert proc.stdin is not None
            proc.stdin.write(img.tobytes())

        render_frames(page, total, 1 if args.fast else args.sub, sink=sink, label="render")
        assert proc.stdin is not None
        proc.stdin.close()
        if proc.wait() != 0:
            raise SystemExit("ffmpeg failed")
        browser.close()

    video = os.path.join(OUT, "_video.mp4")
    if os.path.exists(args.audio):
        ffmpeg(["-i", video, "-i", args.audio, "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", args.mp4])
        print(f"ok -> {args.mp4}  (video + audio)")
    else:
        shutil.copy(video, args.mp4)
        print(f"ok -> {args.mp4}  (silent: {args.audio} not found)")
    os.remove(video)
    print(f"done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()