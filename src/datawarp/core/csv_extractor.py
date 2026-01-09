"""CSV file extractor for DataWarp v2.1 - Optimized (no Excel conversion)."""

import re
import pandas as pd
from typing import Optional, Dict
from datawarp.core.extractor import TableStructure, ColumnInfo, SheetType, DataOrientation, FirstColumnType


class CSVExtractor:
    """Fast CSV extractor - directly infers structure without Excel conversion."""

    def __init__(self, filepath: str, sheet_name: Optional[str] = None):
        """Initialize CSV extractor."""
        self.filepath = filepath
        # sheet_name ignored for CSV (no sheets)

    def _to_db_identifier(self, name: str) -> str:
        """Convert column name to valid PostgreSQL identifier."""
        clean = name.lower()
        clean = re.sub(r'[£$€%]', '', clean)
        clean = re.sub(r'[^a-z0-9]+', '_', clean)
        clean = re.sub(r'_+', '_', clean).strip('_')
        if not clean:
            return 'col_unnamed'
        reserved = {'month', 'year', 'group', 'order', 'table', 'index', 'key',
                   'value', 'date', 'time', 'user', 'name', 'type', 'level'}
        if clean in reserved:
            clean = f"{clean}_val"
        if clean and clean[0].isdigit():
            clean = f"col_{clean}"
        return clean[:63]

    def _infer_type(self, series: pd.Series) -> str:
        """Infer SQL type from pandas Series."""
        # Drop nulls for inference
        non_null = series.dropna()
        if len(non_null) == 0:
            return 'VARCHAR(255)'

        # Check pandas dtype first
        if pd.api.types.is_integer_dtype(series):
            return 'INTEGER'
        if pd.api.types.is_float_dtype(series):
            return 'NUMERIC(18,6)'
        if pd.api.types.is_bool_dtype(series):
            return 'BOOLEAN'
        if pd.api.types.is_datetime64_any_dtype(series):
            return 'DATE'

        # For object dtype, sample values
        sample = non_null.head(25).astype(str)

        # Check if all values look like integers
        try:
            sample.apply(lambda x: int(x.replace(',', '')))
            return 'INTEGER'
        except (ValueError, AttributeError):
            pass

        # Check if all values look like floats
        try:
            sample.apply(lambda x: float(x.replace(',', '').replace('%', '')))
            return 'NUMERIC(18,6)'
        except (ValueError, AttributeError):
            pass

        return 'VARCHAR(255)'

    def infer_structure(self) -> TableStructure:
        """Infer structure directly from CSV (fast, no Excel conversion)."""
        # Read just enough for structure inference
        df = pd.read_csv(self.filepath, nrows=100)

        columns: Dict[int, ColumnInfo] = {}
        used_names = {}

        for idx, col_name in enumerate(df.columns):
            pg_name = self._to_db_identifier(str(col_name))

            # Handle duplicates
            if pg_name in used_names:
                used_names[pg_name] += 1
                pg_name = f"{pg_name}_{used_names[pg_name]}"
            else:
                used_names[pg_name] = 0

            # Infer type
            inferred_type = self._infer_type(df[col_name])

            columns[idx] = ColumnInfo(
                excel_col=str(idx),
                col_index=idx,
                pg_name=pg_name,
                original_headers=[str(col_name)],
                inferred_type=inferred_type
            )

        return TableStructure(
            sheet_name='CSV',
            sheet_type=SheetType.TABULAR,
            header_rows=[0],
            data_start_row=1,
            data_end_row=999999,  # Large default for CSV
            data_start_col=0,
            data_end_col=len(df.columns) - 1,
            columns=columns,
            spacer_columns=[],
            orientation=DataOrientation.VERTICAL,
            first_col_type=FirstColumnType.FISCAL_YEAR,
            id_columns=[]
        )

    def to_dataframe(self) -> pd.DataFrame:
        """Read CSV to DataFrame with lowercased column names."""
        df = pd.read_csv(self.filepath)
        # Lowercase column names to match CREATE TABLE
        df.columns = [self._to_db_identifier(str(col)) for col in df.columns]
        return df
