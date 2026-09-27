import re
from pathlib import Path
from typing import Dict

def scan_constants(repo_root: Path) -> Dict[str, str]:
    """
    Pass 1: Scans TypeScript constants and types files to build a resolved
    symbol dictionary for table names and API route constants.
    """
    symbols = {}
    search_dirs = [
        repo_root / "src" / "constants",
        repo_root / "src" / "lib" / "constants",
        repo_root / "src" / "types",
        repo_root / "src" / "lib"
    ]

    # Regex for object dictionary exports, e.g.:
    # export const TABLES = { EXAMS: 'campus_exam_results', ... }
    # or const API_ROUTES = { PAYROLL: '/api/hr/run-payroll' }
    dict_pattern = re.compile(r'(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*\{([^}]+)\}', re.MULTILINE)
    entry_pattern = re.compile(r'([A-Za-z0-9_]+)\s*:\s*[\'"`]([^\'"`]+)[\'"`]')
    
    # Simple constant strings: export const BASE_API = '/api/v1';
    simple_pattern = re.compile(r'(?:export\s+)?const\s+([A-Za-z0-9_]+)\s*=\s*[\'"`]([^\'"`]+)[\'"`]')

    for d in search_dirs:
        if not d.exists():
            continue
        for ts_file in d.glob("**/*.ts*"):
            try:
                content = ts_file.read_text(encoding="utf-8", errors="ignore")
                
                # Match simple constants
                for m in simple_pattern.finditer(content):
                    var_name, val = m.group(1), m.group(2)
                    symbols[var_name] = val

                # Match dictionary constants
                for m in dict_pattern.finditer(content):
                    dict_name, body = m.group(1), m.group(2)
                    for entry in entry_pattern.finditer(body):
                        prop_name, prop_val = entry.group(1), entry.group(2)
                        symbols[f"{dict_name}.{prop_name}"] = prop_val
            except Exception:
                pass

    return symbols

if __name__ == "__main__":
    repo = Path(r"C:\Users\Admin\Desktop\projects\Present-Career-os")
    res = scan_constants(repo)
    print(f"[OK] Pass 1 Constant Scanner found {len(res)} resolved constants.")
    for k in list(res.keys())[:8]:
        print(f"  • {k} -> {res[k]}")
