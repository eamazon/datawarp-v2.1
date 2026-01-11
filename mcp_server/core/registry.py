"""Dataset Registry - Loads and manages dataset configuration.

The registry reads datasets.yaml and metadata/*.yaml to provide:
- Dataset discovery (list, filter, search)
- Metadata access (columns, descriptions, example questions)
- Backend configuration
"""

from pathlib import Path
from typing import Optional
import yaml

# Paths relative to mcp_server directory
MCP_SERVER_DIR = Path(__file__).parent.parent
CONFIG_PATH = MCP_SERVER_DIR / "config" / "datasets.yaml"
METADATA_DIR = MCP_SERVER_DIR / "metadata"


class DatasetRegistry:
    """Registry for dataset configuration and metadata."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        """Load dataset registry from YAML config.

        Args:
            config_path: Path to datasets.yaml
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.metadata_cache = {}  # Lazy-loaded metadata

    def _load_config(self) -> dict:
        """Load datasets.yaml configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {self.config_path}")

        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def list_datasets(
        self,
        domain: Optional[str] = None,
        tags: Optional[list[str]] = None,
        keyword: Optional[str] = None,
        limit: int = 50
    ) -> list[dict]:
        """List datasets with optional filtering.

        Args:
            domain: Filter by domain (mental_health, workforce, etc.)
            tags: Filter by tags (must match all)
            keyword: Search in dataset code and metadata
            limit: Max results to return

        Returns:
            List of dataset summaries
        """
        datasets = self.config.get('datasets', {})
        results = []

        for code, config in datasets.items():
            # Domain filter
            if domain and config.get('domain') != domain:
                continue

            # Tags filter (must match all)
            if tags:
                dataset_tags = set(config.get('tags', []))
                if not all(t in dataset_tags for t in tags):
                    continue

            # Keyword filter
            if keyword:
                keyword_lower = keyword.lower()
                if keyword_lower not in code.lower():
                    # Check metadata for keyword
                    metadata = self.get_metadata(code)
                    purpose = metadata.get('purpose', '').lower()
                    if keyword_lower not in purpose:
                        continue

            results.append({
                'code': code,
                'domain': config.get('domain', 'other'),
                'tags': config.get('tags', []),
                'backend': config.get('backend', 'duckdb_parquet'),
                'path': config.get('path', '')
            })

            if len(results) >= limit:
                break

        return results

    def get_dataset_config(self, code: str) -> dict:
        """Get configuration for a specific dataset.

        Args:
            code: Dataset code

        Returns:
            Dataset configuration dict

        Raises:
            KeyError: If dataset not found
        """
        datasets = self.config.get('datasets', {})
        if code not in datasets:
            raise KeyError(f"Dataset not found: {code}")
        return datasets[code]

    def get_metadata(self, code: str) -> dict:
        """Get rich metadata for a dataset.

        Loads from the domain-specific metadata file if not cached.

        Args:
            code: Dataset code

        Returns:
            Metadata dict with purpose, columns, example_questions
        """
        config = self.get_dataset_config(code)
        metadata_file = config.get('metadata_file', '')

        if not metadata_file:
            return {'purpose': '', 'columns': {}, 'example_questions': []}

        # Load metadata file if not cached
        metadata_path = MCP_SERVER_DIR / metadata_file
        if metadata_path not in self.metadata_cache:
            if metadata_path.exists():
                with open(metadata_path) as f:
                    self.metadata_cache[metadata_path] = yaml.safe_load(f)
            else:
                self.metadata_cache[metadata_path] = {'datasets': {}}

        domain_metadata = self.metadata_cache[metadata_path]
        return domain_metadata.get('datasets', {}).get(code, {
            'purpose': '',
            'columns': {},
            'example_questions': []
        })

    def get_backend_config(self, backend_name: str) -> dict:
        """Get backend configuration.

        Args:
            backend_name: Backend name (duckdb_parquet, postgres)

        Returns:
            Backend configuration dict
        """
        backends = self.config.get('backends', {})
        if backend_name not in backends:
            raise KeyError(f"Backend not found: {backend_name}")
        return backends[backend_name]

    def get_domains(self) -> list[str]:
        """Get list of unique domains."""
        domains = set()
        for config in self.config.get('datasets', {}).values():
            domains.add(config.get('domain', 'other'))
        return sorted(domains)

    def get_all_tags(self) -> list[str]:
        """Get list of unique tags across all datasets."""
        tags = set()
        for config in self.config.get('datasets', {}).values():
            tags.update(config.get('tags', []))
        return sorted(tags)

    def search_columns(
        self,
        keyword: str,
        role: Optional[str] = None,
        limit: int = 50
    ) -> list[dict]:
        """Search for columns across all datasets.

        Args:
            keyword: Search term for column names or descriptions
            role: Filter by role (dimension, measure, system)
            limit: Max results

        Returns:
            List of column matches with dataset context
        """
        keyword_lower = keyword.lower()
        results = []

        for code in self.config.get('datasets', {}).keys():
            metadata = self.get_metadata(code)
            columns = metadata.get('columns', {})

            for col_name, col_info in columns.items():
                # Skip if role doesn't match
                if role and col_info.get('role') != role:
                    continue

                # Search in column name, description, and keywords
                matches = (
                    keyword_lower in col_name.lower() or
                    keyword_lower in col_info.get('description', '').lower() or
                    any(keyword_lower in kw.lower()
                        for kw in col_info.get('query_keywords', []))
                )

                if matches:
                    results.append({
                        'dataset': code,
                        'column': col_name,
                        'description': col_info.get('description', ''),
                        'type': col_info.get('data_type', 'unknown'),
                        'role': col_info.get('role', 'dimension')
                    })

                    if len(results) >= limit:
                        return results

        return results
