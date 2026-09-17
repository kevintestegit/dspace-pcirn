# Piloto 20 itens — Resumo executivo

Período coberto: 1975–2026. Tipos: 16 PORTARIA/Portaria, 2 DECRETO, 1 LEI, 1 POP (MVP teste).

## Distribuição

- 2011: 2 (ADTS lote 100/101)
- 2023: 14 (fiscais 195/202/208/209, teletrabalho 201, NEA 002, posse 021, comissão PAD 022, enquadramento 224, concurso 190, RI 196 x2)
- Históricos: 6873/1976, 4526/1975
- Recente: 33.717/2024
- Teste: MVP 2026

## Qualidade PDF

- Texto extraível direto (pdftotext): 14/20 (70%)
- Scan com OCR validado: 4/20 (100, 101, 1004, 1011)
- Scan pendente OCR total: 2/20 (2233 capa, 2255 parcial)
- Padrão: DOE 2023 tem texto; EPSON Scan 2011 e boletins 2023 são imagem; anos 70 ruidosos.

## Melhores resumos

1. 123456789/29 — catalogação NUGECID exemplar (9 assuntos, sumário por artigo, link DOE).
2. 123456789/1000 — gestão de 276 vagas TAC/concurso, maior texto (10,6k chars).
3. 123456789/24 — prova MVP workflow completo.

## Padrões detectados

- Fiscalizações concentradas em Larisse Hellen (018, 022/2023).
- Pares duplicados: 100/101 (ADTS), 1009/1010 (posse/exercício), 1002/29 (RI).
- 224/2023 tornada sem efeito pela 226/2023 (ver inventário).
- LC 122/1994 domina base legal de pessoal; LC 571/2016 base de designações.

## Recomendação escala

- Aprovado padrão ficha. Escalar em lotes de 200 com pdftotext + tesseract fallback por (por), checkpoint a cada 50, coluna observações para 2233-like.
- Priorizar OCR total de decretos/leis antigos após lotes 2023-2026.
