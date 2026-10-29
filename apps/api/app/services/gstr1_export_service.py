"""
Official GSTN GSTR-1 Offline Tool JSON Exporter.
Delegates to core GSTR1Service for prefix-aware Table 13 and UQC Table 12 compilation.
"""

from app.services.gstr1_service import (
    GSTR1Service,
    compile_gstr1_table_13,
    parse_doc_series,
    round_flt,
    DOC_NATURE_MAP
)

# Backward-compatibility alias
GSTR1ExportService = GSTR1Service
