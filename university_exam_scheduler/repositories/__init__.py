"""Repository katmanı (veri erişimi).

Importer ve servisler, doğrudan SQL yazmak yerine bu katmanı kullanır.
Bu sayede DB değişirse (SQLite -> başka DB) üst katmanlar minimum etkilenir.
"""

