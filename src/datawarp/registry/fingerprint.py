"""
Structural fingerprinting for cross-period source matching.
Pure deterministic - no LLM calls, no pattern matching.
"""
import hashlib
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Fingerprint:
    """Structural fingerprint for source matching."""
    column_names: Set[str]
    column_count: int
    signature_hash: str  # MD5 of sorted column names

def generate_fingerprint(columns: List[Dict]) -> Fingerprint:
    """
    Create structural fingerprint from column metadata.
    Used for matching sources across periods when column structures are identical.
    """
    # Extract and normalize column names
    col_names = set(c['original_name'].lower() for c in columns)

    # Generate signature hash
    sorted_names = sorted(col_names)
    signature = '|'.join(sorted_names)
    sig_hash = hashlib.md5(signature.encode()).hexdigest()

    return Fingerprint(
        column_names=col_names,
        column_count=len(col_names),
        signature_hash=sig_hash
    )

def jaccard_similarity(fp1: Fingerprint, fp2: Fingerprint) -> float:
    """
    Calculate Jaccard similarity between two fingerprints.
    Returns: 0.0 (no match) to 1.0 (perfect match)
    """
    if fp1.signature_hash == fp2.signature_hash:
        return 1.0  # Exact match

    intersection = len(fp1.column_names & fp2.column_names)
    union = len(fp1.column_names | fp2.column_names)

    return intersection / union if union > 0 else 0.0

def find_best_match(
    new_fp: Fingerprint,
    registry: Dict[str, Fingerprint],
    threshold: float = 0.80
) -> Tuple[Optional[str], float]:
    """
    Find best matching canonical code from registry.

    Returns:
        (canonical_code, confidence) or (None, 0.0) if no match
    """
    best_match = None
    best_score = 0.0

    for canonical_code, stored_fp in registry.items():
        score = jaccard_similarity(new_fp, stored_fp)
        if score > best_score:
            best_score = score
            best_match = canonical_code

    if best_score >= threshold:
        return (best_match, best_score)

    return (None, 0.0)
