#!/usr/bin/env python3
"""
Script to find hardcoded Russian strings in Python files.
Generates a detailed report for i18n refactoring.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
import json


# Russian words to search for (common patterns)
RUSSIAN_PATTERNS = [
    "Ошибка",  # Error
    "Сервис",  # Service
    "Проект",  # Project
    "Контекст",  # Context
    "Пользователь",  # User
    "Настройки",  # Settings
    "Создать",  # Create
    "Удалить",  # Delete
    "Отмена",  # Cancel
    "Готово",  # Done
    "Загрузка",  # Loading
    "Сохранить",  # Save
]


def is_code_line(line: str) -> bool:
    """Check if line contains actual code (not comment or docstring)."""
    stripped = line.strip()
    
    # Skip empty lines
    if not stripped:
        return False
    
    # Skip comments
    if stripped.startswith("#"):
        return False
    
    # Skip docstrings (simple check)
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return False
    
    return True


def find_russian_in_file(filepath: Path) -> List[Dict]:
    """Find all Russian strings in a Python file."""
    results = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for line_num, line in enumerate(lines, 1):
            # Skip non-code lines
            if not is_code_line(line):
                continue
            
            # Check for Russian patterns
            for pattern in RUSSIAN_PATTERNS:
                if pattern in line:
                    # Extract the string context
                    context = line.strip()
                    
                    results.append({
                        'file': str(filepath),
                        'line': line_num,
                        'pattern': pattern,
                        'context': context
                    })
    
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    
    return results


def scan_directory(root_dir: Path, exclude_dirs: List[str] = None) -> Dict[str, List[Dict]]:
    """Scan directory for Russian strings."""
    if exclude_dirs is None:
        exclude_dirs = ['venv', '.git', '__pycache__', 'tests', '.ralph-loop', 'telegram-mcp']
    
    results = {}
    
    for py_file in root_dir.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue
        
        findings = find_russian_in_file(py_file)
        if findings:
            relative_path = py_file.relative_to(root_dir)
            results[str(relative_path)] = findings
    
    return results


def generate_report(results: Dict[str, List[Dict]], output_file: Path):
    """Generate a detailed markdown report."""
    
    # Count statistics
    total_files = len(results)
    total_occurrences = sum(len(findings) for findings in results.values())
    
    # Group by pattern
    pattern_counts = {}
    for findings in results.values():
        for finding in findings:
            pattern = finding['pattern']
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    
    # Generate report
    report = []
    report.append("# Hardcoded Russian Strings Report\n")
    report.append(f"**Generated**: {Path.cwd()}\n")
    report.append(f"**Total Files**: {total_files}")
    report.append(f"**Total Occurrences**: {total_occurrences}\n")
    
    report.append("## Summary by Pattern\n")
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        report.append(f"- **{pattern}**: {count} occurrences")
    
    report.append("\n## Detailed Findings\n")
    
    # Sort files by number of occurrences
    sorted_files = sorted(results.items(), key=lambda x: len(x[1]), reverse=True)
    
    for filepath, findings in sorted_files:
        report.append(f"\n### {filepath} ({len(findings)} occurrences)\n")
        
        for finding in findings:
            report.append(f"**Line {finding['line']}** - Pattern: `{finding['pattern']}`")
            report.append(f"```python")
            report.append(finding['context'])
            report.append(f"```\n")
    
    # Write report
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"✅ Report generated: {output_file}")
    print(f"📊 Found {total_occurrences} occurrences in {total_files} files")


def generate_translation_keys(results: Dict[str, List[Dict]], output_file: Path):
    """Generate suggested translation keys based on findings."""
    
    suggestions = {
        "error.generic": "❌ ข้อผิดพลาด: {error}",
        "error.download": "❌ ข้อผิดพลาดการดาวน์โหลด: {error}",
        "error.processing": "❌ ข้อผิดพลาดการประมวลผล: {error}",
        "error.proxy_setup": "❌ ข้อผิดพลาดการตั้งค่าพร็อกซี: {error}",
        "error.folder_creation": "❌ ข้อผิดพลาดการสร้างโฟลเดอร์: {error}",
        "error.docker": "❌ ข้อผิดพลาด Docker: {error}",
        
        "service.not_initialized": "⚠️ บริการยังไม่ได้เริ่มต้น",
        "service.project_not_initialized": "⚠️ บริการโปรเจกต์ยังไม่ได้เริ่มต้น",
        "service.account_not_initialized": "❌ บริการบัญชียังไม่ได้เริ่มต้น",
        "service.unavailable": "⚠️ บริการไม่พร้อมใช้งาน",
        "service.project_unavailable": "⚠️ บริการโปรเจกต์ไม่พร้อมใช้งาน",
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(suggestions, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Translation suggestions generated: {output_file}")


def main():
    """Main function."""
    root_dir = Path(__file__).parent
    
    print("🔍 Scanning for hardcoded Russian strings...")
    results = scan_directory(root_dir)
    
    if not results:
        print("✅ No hardcoded Russian strings found!")
        return
    
    # Generate reports
    report_file = root_dir / "hardcoded_strings_report.md"
    generate_report(results, report_file)
    
    suggestions_file = root_dir / "translation_suggestions.json"
    generate_translation_keys(results, suggestions_file)
    
    print("\n📋 Next steps:")
    print("1. Review the report: hardcoded_strings_report.md")
    print("2. Add suggested keys to translation files (th.json, en.json, ru.json, zh.json)")
    print("3. Replace hardcoded strings with translator calls")


if __name__ == "__main__":
    main()
