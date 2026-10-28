#!/usr/bin/env python3
"""중복 문제 체크 스크립트"""
import json
import os
from pathlib import Path
from collections import defaultdict

DEFAULT_WINDOWS_BASE = Path(r"D:\EKCRPA\test-report-automation\output")
SCRIPT_DIR = Path(__file__).resolve().parent.parent / "output"
BASE = DEFAULT_WINDOWS_BASE if DEFAULT_WINDOWS_BASE.exists() else SCRIPT_DIR
cases = [
    ('OC_R11', 'personalised_practice_manifest_R11.json'),
    ('Selective_R26', 'personalised_practice_manifest_R26.json')
]

results = {
    'total_students': 0,
    'total_sets': 0,
    'total_questions': 0,
    'duplicates_found': 0,
    'issues': []
}

for folder, manifest_name in cases:
    folder_path = BASE / folder
    manifest_path = folder_path / manifest_name
    
    if not manifest_path.exists():
        print(f"[SKIP] {manifest_name} not found")
        continue
    
    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)
    
    print(f"\n{'='*60}")
    print(f"Checking: {folder}")
    print(f"{'='*60}")
    
    results['total_students'] += len(manifest['students'])
    
    for student_name, student_data in manifest['students'].items():
        student_folder = folder_path / f"personalised_practice_{student_name.replace(' ', '_')}"
        
        for set_name, set_info in student_data['sets'].items():
            results['total_sets'] += 1
            json_path = student_folder / set_name / 'questions.json'
            
            if not json_path.exists():
                results['issues'].append(f"{student_name} - {set_name}: JSON missing")
                continue
            
            with open(json_path, encoding='utf-8') as f:
                data = json.load(f)
            
            questions = data.get('questions', [])
            results['total_questions'] += len(questions)
            
            # 중복 체크
            stems = [q.get('stem', '') for q in questions]
            unique_stems = set(stems)
            
            if len(stems) != len(unique_stems):
                duplicates = len(stems) - len(unique_stems)
                results['duplicates_found'] += duplicates
                results['issues'].append(
                    f"{student_name} - {set_name}: {duplicates} duplicate(s) - {len(questions)} total, {len(unique_stems)} unique"
                )
                print(f"  [DUPLICATE] {student_name} - {set_name}: {duplicates} duplicate(s)")
            else:
                print(f"  [OK] {student_name} - {set_name}: {len(questions)} questions, all unique")

print(f"\n{'='*60}")
print("Summary")
print(f"{'='*60}")
print(json.dumps(results, ensure_ascii=False, indent=2))

if results['duplicates_found'] == 0:
    print("\n✅ No duplicates found! All questions are unique.")
else:
    print(f"\n❌ Found {results['duplicates_found']} duplicates across {len(results['issues'])} sets.")
