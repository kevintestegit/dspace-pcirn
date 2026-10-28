#!/usr/bin/env python3
"""Export the editable PCIRN presentations and refresh PDF catalogue metadata."""
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.awt import Point, Size

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / 'dspace-angular/source/src/assets/pcirn/tutoriais'
CATALOG = ROOT / 'dspace-angular/source/src/app/info/tutoriais/tutorials.catalog.ts'
KIT = HERE / 'kit-visual'
FAIXA_PATH = KIT / 'PCIRN_Faixa_Cabecalho_2480x420.png'
CREST_PATH = KIT / 'brasao-policia-cientifica-rn.png'

# Paleta Institucional Refinada alinhada ao Kit Visual PCIRN
NAVY_PRIMARY = 0x0C3D67     # Azul PCIRN oficial da identidade
ACCENT_GOLD  = 0xD97706     # Âmbar/Dourado oficial para destaques e acentos
SLATE_TITLE  = 0x0F172A     # Ardósia escura para títulos de alta legibilidade
SLATE_TEXT   = 0x334155     # Texto instrucional limpo (WCAG AAA)
SLATE_MUTED  = 0x64748B     # Metadados e legendas
BORDER_LIGHT = 0xCBD5E1     # Bordas suaves de cartões e molduras
BG_CANVAS    = 0xF8FAFC     # Fundo suave dos slides
WHITE        = 0xFFFFFF


def prop(name, value):
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def box(doc, page, kind, x, y, w, h, fill=None, line=None, radius=0, line_w=70):
    shape = doc.createInstance('com.sun.star.drawing.' + kind)
    shape.setPosition(Point(int(x * 100), int(y * 100)))
    shape.setSize(Size(int(w * 100), int(h * 100)))
    page.add(shape)
    shape.FillStyle = uno.Enum('com.sun.star.drawing.FillStyle', 'NONE' if fill is None else 'SOLID')
    if fill is not None:
        shape.FillColor = fill
    shape.LineStyle = uno.Enum('com.sun.star.drawing.LineStyle', 'NONE' if line is None else 'SOLID')
    if line is not None:
        shape.LineColor, shape.LineWidth = line, line_w
    if radius > 0 and hasattr(shape, 'CornerRadius'):
        shape.CornerRadius = int(radius * 100)
    return shape


def text(doc, page, content, x, y, w, h, size=14, color=SLATE_TEXT, bold=False):
    shape = box(doc, page, 'TextShape', x, y, w, h)
    shape.Text.String = content
    shape.TextLeftDistance = shape.TextRightDistance = 0
    shape.TextUpperDistance = shape.TextLowerDistance = 0
    cursor = shape.Text.createTextCursor()
    cursor.gotoEnd(True)
    cursor.CharFontName, cursor.CharHeight = 'Liberation Sans', size
    cursor.CharColor, cursor.CharWeight = color, 150.0 if bold else 100.0
    cursor.CharLocale = uno.createUnoStruct('com.sun.star.lang.Locale')
    locale = cursor.CharLocale
    locale.Language, locale.Country = 'pt', 'BR'
    cursor.CharLocale = locale
    return shape


def picture(doc, page, path, x, y, w, h, caption):
    shape = box(doc, page, 'GraphicObjectShape', x, y, w, h)
    shape.GraphicURL = path.as_uri()
    shape.Title, shape.Description = caption, caption
    return shape


def add_footer(doc, page, spec, subtext, current_page, total_pages):
    box(doc, page, 'RectangleShape', 16, 174, 222, 0.5, fill=BORDER_LIGHT)
    text(doc, page, f'NUGECID · Versão {spec["version"]} · {subtext}', 16, 178, 140, 6, size=8, color=SLATE_MUTED)
    contact = text(doc, page, '', 160, 178, 70, 6, size=8, color=NAVY_PRIMARY)
    link = doc.createInstance('com.sun.star.text.TextField.URL')
    link.URL = 'mailto:arquivogeral@pci.rn.gov.br'
    link.Representation = 'arquivogeral@pci.rn.gov.br'
    contact.Text.insertTextContent(contact.Text.createTextCursor(), link, False)
    text(doc, page, f'{current_page} / {total_pages}', 234, 178, 10, 6, size=8, color=NAVY_PRIMARY, bold=True)


def init_page(doc, number):
    pages = doc.getDrawPages()
    page = pages.getByIndex(0) if number == 0 else pages.insertNewByIndex(number)
    while page.getCount():
        page.remove(page.getByIndex(0))
    page.Width, page.Height, page.Layout = 25400, 19050, 20
    box(doc, page, 'RectangleShape', 0, 0, 254, 190.5, fill=BG_CANVAS)
    return page


def render_cover(doc, spec, document, total_pages):
    page = init_page(doc, 0)
    picture(doc, page, FAIXA_PATH, 0, 0, 254, 12, 'Faixa Institucional PCIRN')
    box(doc, page, 'RectangleShape', 0, 12, 254, 1.2, fill=ACCENT_GOLD)
    text(doc, page, 'POLÍCIA CIENTÍFICA DO RIO GRANDE DO NORTE  ·  REPOSITÓRIO INSTITUCIONAL', 16, 3, 222, 6, size=9, color=WHITE, bold=True)
    box(doc, page, 'RectangleShape', 16, 22, 222, 146, fill=WHITE, line=BORDER_LIGHT, radius=3, line_w=30)
    picture(doc, page, CREST_PATH, 26, 32, 28, 28, 'Brasão da Polícia Científica do Rio Grande do Norte')
    text(doc, page, 'GOVERNO DO ESTADO DO RIO GRANDE DO NORTE  ·  NUGECID', 60, 34, 168, 7, size=10, color=SLATE_MUTED, bold=True)
    text(doc, page, 'MANUAL OFICIAL DE ORIENTAÇÃO AO USUÁRIO', 60, 44, 168, 7, size=11, color=ACCENT_GOLD, bold=True)
    box(doc, page, 'RectangleShape', 26, 66, 202, 0.6, fill=BORDER_LIGHT)
    text(doc, page, document['title'], 26, 74, 202, 20, size=26, color=NAVY_PRIMARY, bold=True)
    text(doc, page, document['summary'], 26, 98, 202, 22, size=15, color=SLATE_TEXT)
    box(doc, page, 'RectangleShape', 26, 128, 86, 9, fill=BG_CANVAS, line=BORDER_LIGHT, radius=2, line_w=20)
    text(doc, page, f'PÚBLICO-ALVO:  {document["audience"]}', 30, 130, 78, 6, size=9, color=NAVY_PRIMARY, bold=True)
    access_label = 'Público (sem login)' if document['group'] == 'consulta' else 'Servidores autorizados'
    box(doc, page, 'RectangleShape', 118, 128, 80, 9, fill=BG_CANVAS, line=BORDER_LIGHT, radius=2, line_w=20)
    text(doc, page, f'ACESSO:  {access_label}', 122, 130, 72, 6, size=9, color=SLATE_MUTED, bold=True)
    add_footer(doc, page, spec, f'Publicação oficial · {spec["date"]}', 1, total_pages)
    return page


def render_flow(doc, page, cx, cy, cw, ch):
    stages = [
        ('ETAPA 01', 'SERVIDOR', 'Preparar e submeter', 'Submissão na coleção autorizada com metadados e arquivo conferidos.'),
        ('ETAPA 02', 'NUGECID', 'Conferir e revisar', 'Conferência de integridade, sigilo, PDF/A e validação documental.'),
        ('ETAPA 03', 'REPOSITÓRIO', 'Documento publicado', 'Disponibilização com URI permanente e acesso público irrestrito.')
    ]
    for i, (badge, actor, action, detail) in enumerate(stages):
        sx = cx + 8 + i * 71
        sy = cy + 14
        box(doc, page, 'RectangleShape', sx, sy, 64, 58, fill=0xF8FAFC, line=BORDER_LIGHT, radius=2, line_w=25)
        box(doc, page, 'RectangleShape', sx, sy, 64, 7, fill=NAVY_PRIMARY, radius=1.5)
        text(doc, page, badge, sx + 4, sy + 1.5, 56, 5, size=8, color=WHITE, bold=True)
        text(doc, page, actor, sx + 4, sy + 11, 56, 7, size=14, color=NAVY_PRIMARY, bold=True)
        text(doc, page, action, sx + 4, sy + 21, 56, 12, size=11, color=SLATE_TITLE, bold=True)
        text(doc, page, detail, sx + 4, sy + 35, 56, 18, size=9, color=SLATE_MUTED)
        if i < 2:
            text(doc, page, '➔', sx + 65, sy + 24, 6, 10, size=16, color=ACCENT_GOLD, bold=True)
    pend_y = cy + 80
    box(doc, page, 'RectangleShape', cx + 8, pend_y, 206, 32, fill=0xFFFBEB, line=0xFDE68A, radius=2, line_w=30)
    box(doc, page, 'RectangleShape', cx + 8, pend_y, 4, 32, fill=ACCENT_GOLD)
    box(doc, page, 'RectangleShape', cx + 16, pend_y + 5, 42, 6, fill=ACCENT_GOLD, radius=1)
    text(doc, page, 'CICLO DE PENDÊNCIA', cx + 18, pend_y + 6, 38, 4, size=7, color=WHITE, bold=True)
    text(doc, page, 'Devolução com justificativa ➔ Correção pelo servidor ➔ Reenvio ➔ Nova conferência pelo NUGECID', cx + 16, pend_y + 14, 192, 7, size=10, color=0x92400E, bold=True)
    text(doc, page, 'Em caso de inconformidade ou erro no arquivo, o NUGECID devolve o item com orientações claras. O documento não é publicado até aprovação final.', cx + 16, pend_y + 22, 192, 8, size=8, color=0x78350F)


def render_slide(doc, index, total, spec, document, item):
    page = init_page(doc, index)
    picture(doc, page, FAIXA_PATH, 0, 0, 254, 11, 'Faixa Institucional PCIRN')
    box(doc, page, 'RectangleShape', 0, 11, 254, 1.2, fill=ACCENT_GOLD)
    text(doc, page, 'REPOSITÓRIO INSTITUCIONAL DA POLÍCIA CIENTÍFICA DO RN', 16, 2.8, 155, 6, size=9, color=WHITE, bold=True)
    sub_title = document['title'].upper()
    if len(sub_title) > 36:
        sub_title = sub_title[:33] + '...'
    text(doc, page, f'TUTORIAL: {sub_title}', 175, 2.8, 63, 6, size=8, color=BORDER_LIGHT, bold=True)
    box(doc, page, 'RectangleShape', 16, 17, 24, 7, fill=NAVY_PRIMARY, radius=1.5)
    badge_label = 'FLUXO' if item.get('flow') else f'PASSO {index:02d}'
    text(doc, page, badge_label, 17.5, 19, 21, 5, size=8, color=WHITE, bold=True)
    text(doc, page, item['title'], 43, 17, 195, 8, size=18, color=SLATE_TITLE, bold=True)
    text(doc, page, item['text'], 16, 27, 222, 12, size=12, color=SLATE_TEXT)
    cx, cy, cw, ch = 16, 43, 222, 125
    if item.get('flow'):
        box(doc, page, 'RectangleShape', cx, cy, cw, ch, fill=WHITE, line=BORDER_LIGHT, radius=2.5, line_w=25)
        render_flow(doc, page, cx, cy, cw, ch)
        add_footer(doc, page, spec, 'Governança e Fluxo Documental', index + 1, total)
        return page
    path = HERE / 'capturas' / (item['shot'] + '.png')
    if not path.is_file():
        raise FileNotFoundError(path)
    metadata = spec['captures'][item['shot']]
    width, height = metadata['width'], metadata['height']
    max_w, max_h = cw - 6, ch - 13
    scale = min(max_w / width, max_h / height)
    w, h = width * scale, height * scale

    if h < 65:
        card_w = min(cw, max(140, w + 12))
        card_h = h + 13
        card_x = cx + (cw - card_w) / 2
        card_y = cy
        box(doc, page, 'RectangleShape', card_x, card_y, card_w, card_h, fill=WHITE, line=BORDER_LIGHT, radius=2.5, line_w=25)
        box(doc, page, 'RectangleShape', card_x, card_y, card_w, 7, fill=0xF1F5F9, radius=0)
        box(doc, page, 'RectangleShape', card_x + 4, card_y + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        box(doc, page, 'RectangleShape', card_x + 8, card_y + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        box(doc, page, 'RectangleShape', card_x + 12, card_y + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        text(doc, page, f'Interface do Repositório — {item["title"]}', card_x + 20, card_y + 2, card_w - 24, 4, size=7, color=SLATE_MUTED)
        img_x = card_x + (card_w - w) / 2
        img_y = card_y + 8
        picture(doc, page, path, img_x, img_y, w, h, item['title'] + '. ' + metadata['caption'])
        for rect in metadata.get('highlights', []):
            rx, ry, rw, rh = rect
            box(doc, page, 'RectangleShape', img_x + rx * scale, img_y + ry * scale, rw * scale, rh * scale, line=ACCENT_GOLD, line_w=120)

        rem_y = card_y + card_h + 5
        rem_h = 172 - rem_y
        if rem_h >= 24:
            box(doc, page, 'RectangleShape', cx, rem_y, cw, rem_h, fill=WHITE, line=BORDER_LIGHT, radius=2.5, line_w=25)
            box(doc, page, 'RectangleShape', cx, rem_y, cw, 7, fill=0xF8FAFC, radius=0)
            text(doc, page, 'ORIENTAÇÕES OPERACIONAIS PARA ESTA ETAPA', cx + 8, rem_y + 1.8, 200, 4, size=8, color=NAVY_PRIMARY, bold=True)
            box(doc, page, 'RectangleShape', cx + 8, rem_y + 12, 3, 3, fill=ACCENT_GOLD, radius=1.5)
            text(doc, page, 'Confira os dados e seleções na interface antes de avançar para a próxima etapa.', cx + 15, rem_y + 11, 198, 6, size=9, color=SLATE_TEXT)
            box(doc, page, 'RectangleShape', cx + 8, rem_y + 20, 3, 3, fill=ACCENT_GOLD, radius=1.5)
            text(doc, page, 'A conformidade documental assegura a correta indexação no acervo permanente da PCIRN.', cx + 15, rem_y + 19, 198, 6, size=9, color=SLATE_TEXT)
            if rem_h > 40:
                box(doc, page, 'RectangleShape', cx + 8, rem_y + 28, 3, 3, fill=ACCENT_GOLD, radius=1.5)
                text(doc, page, 'Para orientações ou esclarecimento de dúvidas, contate o NUGECID pelo canal Fale Conosco.', cx + 15, rem_y + 27, 198, 6, size=9, color=SLATE_TEXT)
    else:
        box(doc, page, 'RectangleShape', cx, cy, cw, ch, fill=WHITE, line=BORDER_LIGHT, radius=2.5, line_w=25)
        box(doc, page, 'RectangleShape', cx, cy, cw, 7, fill=0xF1F5F9, radius=0)
        box(doc, page, 'RectangleShape', cx + 4, cy + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        box(doc, page, 'RectangleShape', cx + 8, cy + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        box(doc, page, 'RectangleShape', cx + 12, cy + 2.5, 2, 2, fill=0xE2E8F0, radius=1)
        text(doc, page, f'Interface do Repositório Institucional — {item["title"]}', cx + 20, cy + 2, 180, 4, size=7, color=SLATE_MUTED)
        img_x = cx + (cw - w) / 2
        img_y = cy + 8 + ((ch - 13) - h) / 2
        picture(doc, page, path, img_x, img_y, w, h, item['title'] + '. ' + metadata['caption'])
        for rect in metadata.get('highlights', []):
            rx, ry, rw, rh = rect
            box(doc, page, 'RectangleShape', img_x + rx * scale, img_y + ry * scale, rw * scale, rh * scale, line=ACCENT_GOLD, line_w=120)
    add_footer(doc, page, spec, metadata['caption'], index + 1, total)
    return page


def build(desktop, spec, document):
    doc = desktop.loadComponentFromURL('private:factory/simpress', '_blank', 0, (prop('Hidden', True),))
    try:
        info = doc.DocumentProperties
        info.Title, info.Author = document['title'], 'PCIRN — NUGECID'
        info.Subject = document['summary']
        info.Language = uno.createUnoStruct('com.sun.star.lang.Locale')
        locale = info.Language
        locale.Language, locale.Country = 'pt', 'BR'
        info.Language = locale
        total_pages = len(document['slides']) + 1
        render_cover(doc, spec, document, total_pages)
        for index, item in enumerate(document['slides'], 1):
            render_slide(doc, index, total_pages, spec, document, item)
        odp = HERE / (document['id'] + '.odp')
        pdf = ASSETS / (document['id'] + '.pdf')
        doc.storeAsURL(odp.as_uri(), (prop('FilterName', 'impress8'), prop('Overwrite', True)))
        settings = (prop('UseTaggedPDF', True), prop('ExportBookmarks', True), prop('ExportNotesPages', False))
        doc.storeToURL(pdf.as_uri(), (prop('FilterName', 'impress_pdf_Export'), prop('FilterData', settings), prop('Overwrite', True)))
        details = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
        count = int(re.search(r'^Pages:\s+(\d+)', details, re.M).group(1))
        assert count == total_pages, (pdf, count)
        assert re.search(r'^Tagged:\s+yes', details, re.M), pdf
        extracted = subprocess.check_output(['pdftotext', str(pdf), '-'], text=True)
        normalized = ' '.join(extracted.split())
        assert document['title'] in normalized, pdf
        for item in document['slides']:
            assert ' '.join(item['text'].split()) in normalized, (pdf, item['title'])
        return {'id': document['id'], 'version': spec['version'], 'date': spec['date'], 'pages': count, 'size': f'{round(pdf.stat().st_size / 1024)} KB'}
    finally:
        doc.close(True)


def main():
    spec = json.loads((HERE / 'conteudo.json').read_text())
    ASSETS.mkdir(parents=True, exist_ok=True)
    pipe = 'pcirn_' + uuid4().hex
    with tempfile.TemporaryDirectory(prefix='pcirn-impress-') as profile:
        cmd = ['libreoffice', f'-env:UserInstallation={Path(profile).as_uri()}', '--headless', '--norestore', '--nodefault', '--nofirststartwizard', f'--accept=pipe,name={pipe};urp;StarOffice.ComponentContext']
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            context = uno.getComponentContext()
            resolver = context.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', context)
            for _ in range(300):
                try:
                    remote = resolver.resolve(f'uno:pipe,name={pipe};urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    if process.poll() is not None:
                        _, err = process.communicate()
                        raise RuntimeError(f'LibreOffice process exited early: {err.decode()}')
                    time.sleep(0.1)
            else:
                raise TimeoutError('LibreOffice did not accept the UNO connection')
            desktop = remote.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', remote)
            groups = []
            for group in ['consulta', 'servidores', 'nugecid']:
                documents = [build(desktop, spec, d) for d in spec['documents'] if d['group'] == group]
                groups.append({'id': group, 'documents': documents})
            catalogue = json.dumps(groups, ensure_ascii=False, indent=2).replace(chr(34), chr(39))
            catalogue = re.sub(r'([^,\n])(?=\n\s*[}\]])', r'\1,', catalogue)
            CATALOG.write_text('// Generated by docs/tutoriais/build.py from the exported PDFs.\nexport const TUTORIAL_GROUPS = ' + catalogue + ';\n')
            for group in groups:
                for document in group['documents']:
                    print(document['id'], document['pages'], 'pages,', document['size'])
            desktop.terminate()
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == '__main__':
    main()
