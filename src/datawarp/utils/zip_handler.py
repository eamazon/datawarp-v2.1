"""ZIP archive utilities for DataWarp v2.

Simple, focused utility for extracting files from ZIP archives.
Used by batch loader to handle ZIP files in manifests.
"""
import zipfile
import tempfile
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def extract_file_from_zip(zip_path: Path, filename: str) -> Path:
    """Extract single file from ZIP to temp location.
    
    Args:
        zip_path: Path to ZIP file
        filename: Name of file to extract (can include subdirectories)
        
    Returns:
        Path to extracted file
        
    Raises:
        FileNotFoundError: If file not found in ZIP
        ValueError: If ZIP is corrupted or invalid
        
    Example:
        >>> zip_path = Path('/tmp/data.zip')
        >>> extracted = extract_file_from_zip(zip_path, 'data.csv')
        >>> # extracted is now /tmp/datawarp_zip_xyz/data.csv
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            namelist = zf.namelist()
            
            # Check if file exists in ZIP
            if filename not in namelist:
                # Show helpful error with available files
                available = ', '.join(namelist[:5])
                if len(namelist) > 5:
                    available += f' ... ({len(namelist)} total)'
                    
                raise FileNotFoundError(
                    f"File '{filename}' not found in ZIP. "
                    f"Available: {available}"
                )
            
            # Extract to temp directory
            temp_dir = tempfile.mkdtemp(prefix='datawarp_zip_')
            extracted_path = zf.extract(filename, temp_dir)
            
            logger.info(f"Extracted '{filename}' from ZIP to {temp_dir}")
            return Path(extracted_path)
            
    except zipfile.BadZipFile as e:
        raise ValueError(
            f"{zip_path.name} is not a valid ZIP file. "
            f"Error: {str(e)}"
        ) from e


def list_zip_contents(zip_path: Path) -> List[str]:
    """List all files in ZIP archive.
    
    Args:
        zip_path: Path to ZIP file
        
    Returns:
        List of filenames in ZIP
        
    Raises:
        ValueError: If ZIP is corrupted or invalid
        
    Example:
        >>> contents = list_zip_contents(Path('/tmp/data.zip'))
        >>> # ['data.csv', 'metadata.txt', 'README.md']
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            return zf.namelist()
    except zipfile.BadZipFile as e:
        raise ValueError(
            f"{zip_path.name} is not a valid ZIP file. "
            f"Error: {str(e)}"
        ) from e
