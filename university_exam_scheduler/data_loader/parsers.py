"""CSV/TXT parse yardımcıları.

Hedef:
- CSV veya TXT formatındaki dosyaları mümkün olduğunca esnek şekilde okuyabilmek
- Farklı ayraçları (`,`, `;`, `\t`, `|`) tolere etmek
- Header varsa Dict olarak, yoksa sütun listesi olarak satırları döndürmek
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence


DEFAULT_DELIMITERS = [",", ";", "\t", "|"]


def _sniff_delimiter(sample: str) -> str:
    """Metin örneğinden ayraç tahmini yapar; bulunamazsa virgül döner."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(DEFAULT_DELIMITERS))
        return dialect.delimiter
    except csv.Error:
        return ","


def _has_header(sample: str) -> bool:
    """CSV Sniffer ile header tahmini."""
    try:
        return csv.Sniffer().has_header(sample)
    except csv.Error:
        return False


@dataclass(frozen=True, slots=True)
class ParsedTable:
    """Bir dosyanın parse edilmiş içeriği."""

    # Header varsa keys bunlar olur; yoksa boş olabilir.
    headers: Sequence[str]
    # Satırlar: header varsa dict-like, yoksa list[str]
    rows: Sequence[Mapping[str, str] | Sequence[str]]


def read_delimited_file(path: Path, *, encoding: str = "utf-8") -> ParsedTable:
    """CSV/TXT dosyasını okuyup satırlara ayırır.

    - Dosyada header varsa `DictReader` ile parse eder.
    - Header yoksa `reader` ile parse eder.
    """
    text = path.read_text(encoding=encoding, errors="replace")
    sample = text[:4096]
    delimiter = _sniff_delimiter(sample)
    header = _has_header(sample)

    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return ParsedTable(headers=(), rows=())

    if header:
        reader = csv.DictReader(lines, delimiter=delimiter)
        headers = tuple(h.strip() for h in (reader.fieldnames or []) if h is not None)
        rows: list[Mapping[str, str]] = []
        for row in reader:
            # DictReader bazı durumlarda None key üretebilir; filtreleyelim.
            cleaned = {str(k).strip(): (v.strip() if isinstance(v, str) else "") for k, v in row.items() if k}
            rows.append(cleaned)
        return ParsedTable(headers=headers, rows=tuple(rows))

    reader2 = csv.reader(lines, delimiter=delimiter)
    parsed_rows: list[Sequence[str]] = []
    max_cols = 0
    for row in reader2:
        parsed = [cell.strip() for cell in row]
        max_cols = max(max_cols, len(parsed))
        parsed_rows.append(parsed)
    # Header olmadığında headers boş bırakılır; üst katman kolon map'i ile çözer.
    return ParsedTable(headers=(), rows=tuple(parsed_rows))


def iter_paths(paths: Iterable[str | Path]) -> Iterator[Path]:
    """String/Path karışık girişleri Path iterator'a çevirir."""
    for p in paths:
        yield p if isinstance(p, Path) else Path(p)

