import json
import sys
sys.path.insert(0, 'tools')

from parse_reading_complete import parse_reading_paper

text = open('stt26_eng_ocr.txt', encoding='utf-8').read()
sections = parse_reading_paper(text)

# 저장
with open('data/questions/reading_complete_db.json', 'w', encoding='utf-8') as f:
    json.dump(sections, f, ensure_ascii=False, indent=2)

print(f'✅ Saved {len(sections)} reading sections')
print(f'   Total passage chars: {sum(len(s["passage"]) for s in sections)}')
