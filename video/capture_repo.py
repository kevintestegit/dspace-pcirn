import json, os, sys, time
from playwright.sync_api import sync_playwright

BASE = "http://localhost:4000"
OUT = "out/repo"
os.makedirs(OUT, exist_ok=True)

def settle(pg, ms=3500):
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(ms)

def shot(pg, name):
    p = os.path.join(OUT, name + ".png")
    pg.screenshot(path=p)
    print(f"  {name:<24} {pg.url}")

def measure(pg, spec):
    return pg.evaluate("""(spec) => {
      const out = {};
      for (const [k, sel] of Object.entries(spec)) {
        const e = document.querySelector(sel);
        if (!e) { out[k] = null; continue; }
        const c = getComputedStyle(e), r = e.getBoundingClientRect();
        out[k] = { text: (e.innerText||'').trim().slice(0,80),
          font: c.fontWeight+' '+c.fontSize+'/'+c.lineHeight+' '+c.fontFamily.split(',')[0],
          size: c.fontSize, weight: c.fontWeight, ls: c.letterSpacing, tt: c.textTransform,
          color: c.color, bg: c.backgroundColor, border: c.borderTopWidth+' '+c.borderTopStyle+' '+c.borderTopColor,
          radius: c.borderRadius, pad: c.padding, box: [Math.round(r.width), Math.round(r.height)] };
      }
      return out;
    }""", spec)

R = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1440}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_default_timeout(40000)

    def kill_notice():
        for s in ("button.orejime-Notice-saveButton", "button.orejime-Notice-declineButton"):
            try:
                pg.click(s, timeout=2000); pg.wait_for_timeout(600); return
            except Exception:
                pass

    # ---- search results, waited until the cards actually arrive
    pg.goto(BASE + "/home", wait_until="networkidle"); pg.wait_for_timeout(2500); kill_notice()
    shot(pg, "01-home")
    QIN = "ds-search-form input[name=query]"
    pg.fill(QIN, "dados"); shot(pg, "02-search-typing")
    pg.press(QIN, "Enter"); settle(pg, 5000)
    shot(pg, "03-results")
    R["results"] = measure(pg, {
        "page title": "h2, .search-results h2",
        "section heading": "#search-content h2, .card-element h2",
        "result card": ".card-element",
        "card title": ".card-title",
        "card text": ".card-text",
        "scope button": ".scope-button",
        "search button": ".search-button",
        "sidebar h3": "ds-themed-search-filters h3, .sidebar-content h3",
        "facet button": "ds-themed-search-filters .btn",
        "clear filters": ".btn-primary",
    })
    R["result cards"] = pg.evaluate("""() => Array.from(document.querySelectorAll('.card-element')).slice(0,4).map(e => ({
        title: (e.querySelector('.card-title')||{}).innerText,
        text: (e.querySelector('.card-text')||{}).innerText }))""")

    # ---- the facet sidebar, the real filter control
    pg.evaluate("() => { const f=document.querySelector('ds-themed-search-filters'); if(f) f.scrollIntoView({block:'center'}); }")
    pg.wait_for_timeout(800); shot(pg, "04-filters")
    R["facets"] = measure(pg, {
        "facet heading": "ds-themed-search-filters h3",
        "facet button": "ds-themed-search-filters button",
    })
    pg.evaluate("() => window.scrollTo(0,0)")

    # ---- communities
    pg.goto(BASE + "/communities", wait_until="networkidle"); pg.wait_for_timeout(2000); kill_notice()
    shot(pg, "05-communities")
    R["communities"] = measure(pg, {"h1": "h1", "card title": ".card-title",
                                    "handle": ".ds-comcol-page-handle"})
    com = pg.query_selector(".card-title a, .card-text a")
    if com:
        com.click(); settle(pg, 3500); shot(pg, "06-community")
        R["community"] = measure(pg, {"h1": "h1", "handle": ".ds-comcol-page-handle",
                                      "search heading": "ds-comcol-search-section h2, h2"})
        col = pg.query_selector(".card-title a, .card-text a")
        if col:
            col.click(); settle(pg, 3500); shot(pg, "07-collection")
            R["collection"] = measure(pg, {"h1": "h1", "card title": ".card-title",
                                           "thumbnail": "ds-thumbnail"})
            it = pg.query_selector(".card-title a, .card-text a")
            if it:
                it.click(); settle(pg, 5000); shot(pg, "08-item")
                R["item"] = measure(pg, {
                    "h1": "h1",
                    "metadata label": "table.metadata td:first-child, .metadata-label",
                    "metadata value": "table.metadata td:nth-child(2), .metadata-value",
                    "metadata row": "table.metadata tr, .metadata-row",
                    "bitstream link": "a[href*='/bitstreams/']",
                    "btn": ".btn-primary, .btn",
                })
                R["item texts"] = pg.evaluate("""() => {
                  const rows = Array.from(document.querySelectorAll('table.metadata tr')).slice(0,8)
                    .map(tr => Array.from(tr.children).map(td => td.innerText.trim()));
                  const bs = Array.from(document.querySelectorAll("a[href*='/bitstreams/']")).slice(0,5)
                    .map(a => a.innerText.trim());
                  return { h1: (document.querySelector('h1')||{}).innerText, rows, bitstreams: bs };
                }""")
                pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight*0.40)")
                pg.wait_for_timeout(900); shot(pg, "09-item-metadata")
                bs = pg.query_selector("a[href*='/bitstreams/']")
                if bs:
                    bs.click(); pg.wait_for_timeout(6000); shot(pg, "10-preview")
                    print("   preview url:", pg.url)
    R["tokens"] = pg.evaluate("""() => {
      const root = getComputedStyle(document.documentElement), t = {};
      for (const p of ['--pcirn-fs-page-title','--pcirn-fs-section','--pcirn-fs-label',
                       '--pcirn-fs-card-title','--pcirn-fs-meta']) t[p] = root.getPropertyValue(p).trim();
      const hdr = document.querySelector('ds-header');
      if (hdr) { const c = getComputedStyle(hdr.querySelector('.navbar, header, div') || hdr);
        t['header-bg'] = c.backgroundColor; }
      const b = getComputedStyle(document.body);
      t['body-bg'] = b.backgroundColor; t['body-color'] = b.color;
      t['body-font'] = b.fontFamily; t['body-size'] = b.fontSize;
      const btn = document.querySelector('.search-button');
      if (btn) { const c = getComputedStyle(btn);
        t['search-button-bg'] = c.backgroundColor; t['search-button-color'] = c.color;
        t['search-button-radius'] = c.borderRadius; t['search-button-pad'] = c.padding; }
      return t;
    }""")
    b.close()

json.dump(R, open(os.path.join(OUT, "repo-styles.json"), "w"), indent=1, ensure_ascii=False)
print("\nok -> out/repo/")
