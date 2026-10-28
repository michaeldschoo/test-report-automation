import json

data = json.load(open(r'output\Selective_R26\personalised_practice_Adrio_Maheswaran\30_questions_15_to_20_minute_mock_practice_set\questions.json', encoding='utf-8'))

questions = data['questions']
reading_qs = [q for q in questions if q['subject'] == 'Reading']

print(f'총 Reading 문제: {len(reading_qs)}개')
print(f'\n지문 길이 확인:')
for i, q in enumerate(reading_qs, 1):
    passage_len = len(q.get('passage', ''))
    print(f'  문제 {i}: {passage_len} chars')
    if passage_len > 500:
        print(f'    ✅ 긴 지문! - {q.get("passage", "")[:100]}...')
