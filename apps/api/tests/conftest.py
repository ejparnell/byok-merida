from pathlib import Path
import os
import sys

os.environ.setdefault("USER_NAME", "Test User")

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
