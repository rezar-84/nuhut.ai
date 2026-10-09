"""Monthly reports stored as text files under reports/."""
import os

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def list_reports():
    return sorted(name for name in os.listdir(REPORT_DIR) if name.endswith(".txt"))
