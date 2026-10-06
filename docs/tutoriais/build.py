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
NAVY, GOLD, INK, MUTED, PAPER = 0x07345F, 0xD79B00, 0x24364B, 0x52657B, 0xF6F8FB


def prop(name, value):
    item = PropertyValue()
    item.Name, item.Value = name, value
    return item


def box(doc, page, kind, x, y, w, h, fill=None, line=None):
    shape = doc.createInstance('com.sun.star.drawing.' + kind)
    shape.setPosition(Point(int(x * 100), int(y * 100)))
    shape.setSize(Size(int(w * 100), int(h * 100)))
    page.add(shape)
    shape.FillStyle = uno.Enum('com.sun.star.drawing.FillStyle', 'NONE' if fill is None else 'SOLID')
    if fill is not None:
        shape.FillColor = fill
    shape.LineStyle = uno.Enum('com.sun.star.drawing.LineStyle', 'NONE' if line is None else 'SOLID')
    if line is not None:
        shape.LineColor, shape.LineWidth = line, 70
    return shape


def text(doc, page, content, x, y, w, h, size=18, color=INK, bold=False):
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


def slide(doc, number, title, version, date):
    pages = doc.getDrawPages()
    page = pages.getByIndex(0) if number == 0 else pages.insertNewByIndex(number)
    while page.getCount():
        page.remove(page.getByIndex(0))
    page.Width, page.Height, page.Layout = 25400, 19050, 20
    box(doc, page, 'RectangleShape', 0, 0, 254, 190.5, PAPER)
    box(doc, page, 'RectangleShape', 0, 0, 254, 19, NAVY)
    text(doc, page, 'REPOSITÓRIO INSTITUCIONAL PCIRN', 11, 5, 230, 11, 16, 0xFFFFFF, True)
    text(doc, page, title, 11, 26, 232, 22, 25, NAVY, True)
    box(doc, page, 'RectangleShape', 11, 52, 232, 1, GOLD)
    text(doc, page, f'NUGECID · Versão {version} · {date}', 11, 179, 128, 7, 11, MUTED)
    contact = text(doc, page, '', 142, 179, 82, 7, 10, NAVY)
    link = doc.createInstance('com.sun.star.text.TextField.URL')
    link.URL = 'mailto:arquivogeral@pci.rn.gov.br'
    link.Representation = 'arquivogeral@pci.rn.gov.br'
    contact.Text.insertTextContent(contact.Text.createTextCursor(), link, False)
    text(doc, page, str(number + 1), 230, 179, 13, 7, 11, NAVY)
    return page


def flow(doc, page):
    stages = [('SERVIDOR', 'Preparar e submeter'), ('NUGECID', 'Conferir e revisar'), ('REPOSITÓRIO', 'Documento publicado')]
    for i, (owner, action) in enumerate(stages):
        x = 11 + i * 81
        box(doc, page, 'RectangleShape', x, 105, 70, 32, 0xFFFFFF, NAVY)
        text(doc, page, owner, x + 4, 111, 62, 9, 14, NAVY, True)
        text(doc, page, action, x + 4, 123, 62, 10, 13)
        if i < 2:
            text(doc, page, '→', x + 70, 115, 11, 15, 24, NAVY)
    text(doc, page, 'Pendência: devolver → corrigir → reenviar → revisar novamente.', 11, 149, 230, 15, 17, NAVY, True)


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
        page = slide(doc, 0, document['title'], spec['version'], spec['date'])
        text(doc, page, document['summary'], 11, 63, 222, 35, 23)
        text(doc, page, document['audience'], 11, 111, 210, 15, 18, NAVY, True)
        text(doc, page, 'Orientações ilustradas · Repositório Institucional da Polícia Científica do Rio Grande do Norte', 11, 136, 178, 27, 17)
        crest = ROOT / 'dspace-angular/source/src/assets/pcirn/images/brasao-policia-cientifica-rn.png'
        picture(doc, page, crest, 205, 130, 24, 28, 'Brasão da Polícia Científica do Rio Grande do Norte')
        for index, item in enumerate(document['slides'], 1):
            page = slide(doc, index, f'{index:02d}  {item["title"]}', spec['version'], spec['date'])
            text(doc, page, item['text'], 11, 58, 232, 33, 17)
            if item.get('flow'):
                flow(doc, page)
                continue
            path = HERE / 'capturas' / (item['shot'] + '.png')
            if not path.is_file():
                raise FileNotFoundError(path)
            metadata = spec['captures'][item['shot']]
            width, height = metadata['width'], metadata['height']
            scale = min(232 / width, 77 / height, .37)
            w, h = width * scale, height * scale
            x, y = 11 + (232 - w) / 2, 95 + (77 - h) / 2
            picture(doc, page, path, x, y, w, h, item['title'] + '. ' + metadata['caption'])
            for n, rect in enumerate(metadata.get('highlights', []), 1):
                rx, ry, rw, rh = rect
                box(doc, page, 'RectangleShape', x + rx * scale, y + ry * scale, rw * scale, rh * scale, line=GOLD)
            text(doc, page, metadata['caption'], 11, 172, 232, 6, 9, MUTED)
        odp = HERE / (document['id'] + '.odp')
        pdf = ASSETS / (document['id'] + '.pdf')
        doc.storeAsURL(odp.as_uri(), (prop('FilterName', 'impress8'), prop('Overwrite', True)))
        settings = (prop('UseTaggedPDF', True), prop('ExportBookmarks', True), prop('ExportNotesPages', False))
        doc.storeToURL(pdf.as_uri(), (prop('FilterName', 'impress_pdf_Export'), prop('FilterData', settings), prop('Overwrite', True)))
        details = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
        count = int(re.search(r'^Pages:\s+(\d+)', details, re.M).group(1))
        assert count == len(document['slides']) + 1, (pdf, count)
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
        process = subprocess.Popen(['libreoffice', '-env:UserInstallation=' + Path(profile).as_uri(), '--headless', '--norestore', '--nodefault', '--nofirststartwizard', f'--accept=pipe,name={pipe};urp;StarOffice.ComponentContext'], stdout=subprocess.DEVNULL)
        try:
            context = uno.getComponentContext()
            resolver = context.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', context)
            for _ in range(100):
                try:
                    remote = resolver.resolve(f'uno:pipe,name={pipe};urp;StarOffice.ComponentContext')
                    break
                except Exception:
                    if process.poll() is not None:
                        raise RuntimeError('LibreOffice failed to start')
                    time.sleep(.1)
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
