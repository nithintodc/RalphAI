"""Configuration constants and paths"""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Master files for date range filtering
DD_DATA_MASTER = ROOT_DIR / "dd-data.csv"
UE_DATA_MASTER = ROOT_DIR / "ue-data.csv"

# File paths - Marketing (New Customers)
DD_MKT_PRE_24 = ROOT_DIR / "dd-mkt-pre-24.csv"
DD_MKT_POST_24 = ROOT_DIR / "dd-mkt-post-24.csv"
DD_MKT_PRE_25 = ROOT_DIR / "dd-mkt-pre-25.csv"
DD_MKT_POST_25 = ROOT_DIR / "dd-mkt-post-25.csv"
UE_MKT_PRE_24 = ROOT_DIR / "ue-mkt-pre-24.csv"
UE_MKT_POST_24 = ROOT_DIR / "ue-mkt-post-24.csv"
UE_MKT_PRE_25 = ROOT_DIR / "ue-mkt-pre-25.csv"
UE_MKT_POST_25 = ROOT_DIR / "ue-mkt-post-25.csv"
