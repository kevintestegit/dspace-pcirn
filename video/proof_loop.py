#!/usr/bin/env python3
"""
Prove the two claims the piece rests on.

1. The loop is exact in state, not just in pixels: every channel holds the same
   value AND the same velocity at t=0 and t=DUR, so the seam has no jump in
   either position or rate of change.
2. seek(t) is a pure function of t: the same t reached from a different direction
   renders a byte-identical frame.

  .venv/bin/python proof_loop.py
"""
import hashlib, io, os, sys
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "index.html")
DUR, SIZE = 30.0, 1440
ATOL, VTOL = 1e-6, 1e-4


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--force-device-scale-factor=1"])
        page = browser.new_context(viewport={"width": SIZE, "height": SIZE},
                                   device_scale_factor=1).new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto("file://" + PAGE)
        page.wait_for_function("window.__READY === true", timeout=30000)

        a = page.evaluate("t => window.__probe(t)", 0.0)
        b = page.evaluate("t => window.__probe(t)", DUR)

        # q1/q2 are the typed strings, not channels
        chans = {k: v for k, v in a.items() if isinstance(v, (int, float))}
        bad_v = [k for k in chans if not k.endswith("#") and abs(chans[k] - b[k]) > ATOL]
        bad_vv = [k for k in chans if k.endswith("#") and abs(chans[k] - b[k]) > VTOL]

        # purity: the same t, reached from three different directions
        hashes = []
        for order in ([0.0, 12.5, DUR, 0.0, DUR], [DUR, 0.0, DUR], [0.0, DUR, 0.0]):
            page.evaluate("ts => { for (const t of ts) window.seek(t); }", order)
            page.evaluate("t => window.seek(t)", 12.5)
            png = page.screenshot(type="png", animations="disabled")
            hashes.append(hashlib.sha256(png).hexdigest())

        # the seam itself: the first and last source frames
        def frame(t):
            page.evaluate("t => window.seek(t)", t)
            with Image.open(io.BytesIO(page.screenshot(type="png", animations="disabled"))) as im:
                return np.asarray(im.convert("RGB"), dtype=np.uint8)

        f0, f30 = frame(0.0), frame(DUR)
        diff = int(np.abs(f0.astype(np.int32) - f30.astype(np.int32)).max())
        changed = int((f0 != f30).any(axis=2).sum())
        browser.close()

    print(f"channels checked      : {len(chans) - len([k for k in chans if k.endswith('#')])}")
    print(f"value mismatch  t0/t30: {len(bad_v)}  {bad_v[:8]}")
    print(f"velocity mismatch     : {len(bad_vv)} {bad_vv[:8]}")
    print(f"seek(12.5) hashes     : {len(set(hashes))} distinct of {len(hashes)}")
    print(f"frame t0 vs t30       : max channel diff {diff}/255, {changed} differing pixels")
    print(f"page errors           : {errors or 'none'}")

    ok = not bad_v and not bad_vv and len(set(hashes)) == 1 and diff == 0 and not errors
    print("LOOP EXACT" if ok else "LOOP BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())