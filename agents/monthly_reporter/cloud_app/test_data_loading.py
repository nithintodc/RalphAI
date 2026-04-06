#!/usr/bin/env python3
"""Test script to verify data loading works correctly"""

import pandas as pd
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent

def test_load_file(file_path):
    """Test loading a single file"""
    print(f"\nTesting {file_path.name}...")
    try:
        df = pd.read_csv(file_path, skiprows=[0], header=0)
        df.columns = df.columns.str.strip()
        
        print(f"  Columns: {list(df.columns)[:5]}...")
        print(f"  Rows: {len(df)}")
        
        if 'Store ID' in df.columns:
            print(f"  Store ID column found")
            print(f"  Unique stores: {df['Store ID'].nunique()}")
        else:
            print(f"  ERROR: Store ID column not found!")
        
        if 'Sales (excl. tax)' in df.columns:
            print(f"  Sales (excl. tax) column found")
            df['Sales (excl. tax)'] = pd.to_numeric(df['Sales (excl. tax)'], errors='coerce')
            print(f"  Total sales: ${df['Sales (excl. tax)'].sum():,.2f}")
        else:
            print(f"  ERROR: Sales (excl. tax) column not found!")
            
    except Exception as e:
        print(f"  ERROR: {str(e)}")

# Test all files
files = [
    ROOT_DIR / "ue-pre-24.csv",
    ROOT_DIR / "ue-post-24.csv",
    ROOT_DIR / "ue-pre-25.csv",
    ROOT_DIR / "ue-post-25.csv",
]

for file_path in files:
    if file_path.exists():
        test_load_file(file_path)
    else:
        print(f"\nWARNING: {file_path.name} not found!")

print("\n" + "="*50)
print("Test complete!")

