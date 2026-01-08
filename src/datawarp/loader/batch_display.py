"""Simple batch loading display with tqdm progress bars.

tqdm shows progress (auto-positioned above table):
  - Download progress bar
  - Insert progress bar
  
Simple text table (clean, like original):
  - Period | Status | Rows | Cols | Duration | Details
"""

def create_two_area_display(manifest_name, target_table, sheet_display, num_files):
    """Print static header and table header."""
    print(f"Loading: {manifest_name} → {target_table}")
    print(f"Source: \"{sheet_display}\" | Files: {num_files}")
    print()
    print(f"{'Period':<12} {'Status':<10} {'Rows':<10} {'New Cols':<10} {'Duration':<10} {'Details'}")
    print("─" * 80)
    return None, None, None  # No Rich components needed

def update_progress(layout, period, status, filename=""):
    """tqdm handles progress - nothing to do here."""
    pass

def add_result(results_table, period, status, rows="", new_cols="", duration="", details="", style=""):
    """Print simple table row."""
    print(f"{period:<12} {status:<10} {rows:<10} {new_cols:<10} {duration:<10} {details}")

def complete_progress(layout):
    """tqdm bars auto-clear with leave=False - nothing needed."""
    pass
