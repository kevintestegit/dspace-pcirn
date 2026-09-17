#!/usr/bin/env python3
"""Gera abstracts melhorados (ementa completa + Art.1º/Resolve) a partir do texto do PDF.

Entradas:
  --meta  CSV com colunas handle,uuid,t,d,ty,s,a,au,id2 (bulk-meta.csv)
  --text  diretório com <uuid>.txt extraídos via pdftotext do assetstore
Saída: CSV uuid,handle,new_abstract (apenas itens com extração limpa aprovada no gate).

Regras (validadas em 2026-09-17, 1067 aprovados, ruído zero):
  - remove spans de boilerplate DOE/SDOE (carimbos, protocolo de assinaturas, links)
  - prefere cláusula operativa (Resolve:/Determinar que), depois ementa (Dispõe...),
    depois Art. 1º; rejeita cabeçalhos, preâmbulos Considerando e cortes no meio de número
  - scans sem camada de texto e rejeitados mantêm o abstract atual (pendente OCR)
"""

import argparse, csv, os, re


def clean(t):
    return re.sub(r"\s+", " ", t).strip()


def norm(t):
    t = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", t)
    t = re.sub(r"(\d)-\s+(\d)", r"\1-\2", t)
    t = re.sub(r"Art\.?\s*(\d+)\s*°", r"Art. \1º", t)
    return t


def deoil(t):
    t = re.sub(
        r"CERTIFICADO DIGITALMENTE\s+Ano XC[^.]{0,150}?\d{4}", " ", t, flags=re.I
    )
    i = t.rfind("PROTOCOLO DE ASSINATURAS")
    if i > 0:
        j = re.search(r"Código de verificação:\s*\S+", t[i : i + 2000], re.I)
        t = t[:i] + " " + t[i + (j.end() + 120 if j else 1500) :]
    t = re.sub(r"Para visualizar o documento original[^.]*\.", " ", t, flags=re.I)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(
        r"Poder Executivo\s+Ano XC\s*•\s*Nº\s*\d+\s+Natal,[^.]*?\d{4}\.?",
        " ",
        t,
        flags=re.I,
    )
    t = re.sub(r"CERTIFICADO DIGITALMENTE|PROTOCOLO DE ASSINATURAS", " ", t, flags=re.I)
    t = re.sub(r"(?<![A-Za-zÀ-ú])PUBLIQUE-SE E CUMPRA-SE\.?", " ", t, flags=re.I)
    t = re.sub(r"\*REPUBLICAR POR INCORREÇÃO", " ", t, flags=re.I)
    return clean(t)


HEADER = re.compile(
    r"(Portaria\s+Natal/RN[^.]{0,60}\.\s*n[ºo]?\s*\d+/\d+\s*[–-]\s*GDG/ITEP|LEI COMPLEMENTAR\s*N[ºo]?\s*\d+\s*,\s*DE[^.]{0,120}|DECRETO\s*N[ºo]?\s*\d+[^.]{0,100}?DE[^.]{0,100}?\d{4}|LEI(\s*COMPLEMENTAR)?\s*N[ºo]?\s*\.?\s*\d+[^.]{0,100}?DE[^.]{0,100}?\d{4})",
    re.I,
)
GEN = re.compile(
    r"((?:LEI COMPLEMENTAR|PORTARIA|DECRETO|LEI)\s*N[ºo]?\s*\d+[^.]{0,80}?(?:GDG/ITEP|ITEP)?[^.]{0,40})",
    re.I | re.S,
)


def strip_head(t):
    m = HEADER.search(t[:2000])
    if m and m.start() > 20:
        return t[m.start() :]
    for m in GEN.finditer(t[:1500]):
        if m.start() < 20:
            continue
        if re.search(
            r"(?i)(art|artigo|inciso|parágrafo|§)",
            t[max(0, m.start() - 80) : m.start()],
        ):
            continue
        return t[m.start() :]
    m2 = re.search(
        r"(O (?:DIRETOR-GERAL|CHEFE DE GABINETE)|A GOVERNADORA|FAÇO SABER|Resolve\s*:|Art\. 1º)",
        t,
    )
    if m2 and m2.start() > 50:
        return t[m2.start() :]
    return t


ABBR = re.compile(
    r"(?i)\b(mat|art|n|sr|sra|dr|dra|ex|etc|vol|p|pp|v|srta|prof|anexo|inc|ref|tel)\.$"
)


def clause_end(t, start, minlen=20, maxlen=650):
    i = start
    while True:
        jd, js = t.find(".", i), t.find(";", i)
        js = [x for x in [jd, js] if x >= 0]
        if not js or min(js) - start > maxlen:
            return None
        j = min(js)
        if ABBR.search(t[start : j + 1].strip()):
            i = j + 1
            continue
        if t[j] == ";":
            if j - start >= minlen:
                return j + 1
        elif j - start >= minlen and not re.match(r"\d", t[j + 1 : j + 2]):
            return j + 1
        i = j + 1


def build(text, r):
    t = strip_head(deoil(norm(clean(text))))
    if len(t) < 200:
        return None
    cands = []
    for pat in [r"Resolve\s*:?", r"(Determinar que)"]:
        mo = re.search(pat, t)
        if mo:
            start = mo.end() if "Resolve" in pat else mo.start(1)
            e = clause_end(t, start, 40, 650)
            if e:
                s = t[start:e].strip(" :;-")
                if len(s) > 40:
                    cands.append(s)
                    break
    me = re.search(
        r"(?:^|\.\s+)((?:Dispõe|Institui|Designa|Constitui|Autoriza|Concede|Retifica|Torna sem efeito|Cria|Altera)\s)",
        t,
        re.I,
    )
    if me:
        e = clause_end(t, me.end(1), 30, 550)
        s = t[me.start(1) : e].strip() if e else ""
        if (
            s
            and not re.match(r"(?i)considerando", s)
            and all(s not in c and c not in s for c in cands)
        ):
            cands.append(s)
    m1 = t.find("Art. 1º")
    if m1 >= 0:
        e = clause_end(t, m1, 30, 550)
        if e:
            a = t[m1:e].strip()
            if all(a not in c and c not in a for c in cands):
                cands.append(a)
    if not cands:
        return None
    body = " ".join(cands[:2])
    if body and body[0].islower():
        body = body[0].upper() + body[1:]
    if re.match(
        r"(Nº|N\.º|Portaria Natal|O DIRETOR-GERAL|O CHEFE DE GABINETE|A GOVERNADORA)",
        body[:120],
    ):
        return None
    if "Considerando" in body[:120]:
        return None
    ident = (r["id2"] or "").split("|")[0].strip() if r.get("id2") else r["t"][:60]
    new = (body + f" ({ident}, {r.get('d') or 's/data'}.)").strip()
    if len(new) > 1100:
        cut = new[:1100]
        m = re.search(r"(\d[\d\.\-/\s]*)$", cut)
        if m:
            m2 = re.match(r"[\d\.\-/\s]+[A-Za-z0-9\-/]*", new[1100:1130])
            if m2 and m2.group(0).strip():
                cut = (cut + m2.group(0)).rstrip()[:1125]
        dot = cut.rfind(". ")
        new = cut[: dot + 1] if dot > 600 else cut.rstrip() + "…"
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    meta = {}
    with open(a.meta, newline="") as f:
        for r in csv.DictReader(f):
            meta[r["uuid"]] = r
    out, rej = [], 0
    for uuid, r in meta.items():
        p = os.path.join(a.text, uuid + ".txt")
        if os.path.exists(p):
            nb = build(open(p).read(), r)
            if nb:
                out.append((uuid, r["handle"], nb))
            else:
                rej += 1
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["uuid", "handle", "new_abstract"])
        w.writerows(out)
    print(f"aprovados {len(out)} rejeitados {rej}")


if __name__ == "__main__":
    main()
