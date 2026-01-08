"""CSV file extractor for DataWarp v2.1."""

import pandas as pd
from typing import Optional
from datawarp.core.extractor import FileExtractor, TableStructure


class CSVExtractor:
    """Simple CSV extractor that delegates to FileExtractor for consistency."""

    def __init__(self, filepath: str, sheet_name: Optional[str] = None):
        """Initialize CSV extractor."""
        self.filepath = filepath
        self.sheet_name = sheet_name

        # CSV files don't have sheets, so convert to Excel for FileExtractor
        # Read CSV and save as temporary Excel file
        import tempfile
        import os

        df = pd.read_csv(filepath)

        # Create temp Excel file
        fd, temp_xlsx = tempfile.mkstemp(suffix='.xlsx')
        os.close(fd)

        df.to_excel(temp_xlsx, index=False, sheet_name='Sheet1')

        # Use FileExtractor on the Excel file
        self._extractor = FileExtractor(temp_xlsx, 'Sheet1')
        self._temp_file = temp_xlsx

    def infer_structure(self) -> TableStructure:
        """Infer structure from CSV file."""
        return self._extractor.infer_structure()

    def to_dataframe(self):
        """Convert CSV to pandas DataFrame."""
        return pd.read_csv(self.filepath)

    def __del__(self):
        """Clean up temporary file."""
        import os
        if hasattr(self, '_temp_file') and os.path.exists(self._temp_file):
            try:
                os.unlink(self._temp_file)
            except:
                pass
