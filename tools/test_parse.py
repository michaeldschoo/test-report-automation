from parse_reading_complete import parse_reading_paper

text = open('stt26_eng_ocr.txt', encoding='utf-8').read()
sections = parse_reading_paper(text)

print(f'✓ Total sections: {len(sections)}')
for i, s in enumerate(sections, 1):
    print(f'{i}. {s["title"]}')
    print(f'   Passage: {len(s["passage"])} chars')
    print(f'   Questions: {len(s["questions"])}')
