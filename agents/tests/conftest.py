import os
import sys

# السماح باستيراد ملفات agents/ من داخل tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# بدون تأخير مصطنع في الـ Mock أثناء الاختبارات
os.environ["MOCK_LATENCY"] = "0"

# Set both DB paths before test modules import either application.
import tempfile
from pathlib import Path

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="thiqa-agent-tests-"))
os.environ["THIQA_DB_PATH"] = str(_TEST_DB_DIR / "thiqa.sqlite")
os.environ["INSURERS_DB_PATH"] = str(_TEST_DB_DIR / "insurers.sqlite")
