import json
from pathlib import Path

POOL_FILE = Path("data/questions/pool.json")

def expand_thinking():
    with open(POOL_FILE, "r", encoding="utf-8") as f:
        pool = json.load(f)
    
    thinking_additions = [
        {"subject":"Thinking Skills","topic":"Logical Reasoning","difficulty":"Hard","stem":"If all A are B, and some B are C, which is definitely true?","options":"All A are C|Some A are C|Some A are not C|Cannot be determined","answer":"D","explanation":"A might not overlap with C at all."},
        {"subject":"Thinking Skills","topic":"Sequence","difficulty":"Medium","stem":"What follows: A, C, F, J, __?","options":"M|N|O|P|Q","answer":"C","explanation":"+2, +3, +4, +5 (J+5 = O)."},
        {"subject":"Thinking Skills","topic":"Deduction","difficulty":"Hard","stem":"Only one of three suspects is lying. Suspect 1: 'I'm innocent.' Suspect 2: 'Suspect 1 is lying.' Suspect 3: 'I'm innocent.' Who is the liar?","options":"Suspect 1|Suspect 2|Suspect 3|Cannot determine","answer":"A","explanation":"If 1 is lying, 2 is truthful, 3 is truthful. All consistent."},
        {"subject":"Thinking Skills","topic":"Arrangement","difficulty":"Hard","stem":"Five people sit in a row. A is next to B. C is not next to D. E is at the end. Who is next to A?","options":"B|C|D|E|Cannot determine","answer":"D","explanation":"Constraint analysis needed."},
        {"subject":"Thinking Skills","topic":"Word Logic","difficulty":"Medium","stem":"If 'cat' is 'dog', and 'dog' is 'bird', what is 'cat'?","options":"cat|dog|bird|fish","answer":"C","explanation":"Direct mapping."},
        {"subject":"Thinking Skills","topic":"Pattern","difficulty":"Medium","stem":"What is the missing number in the sequence: 2, 4, 8, 16, __?","options":"24|28|32|36|40","answer":"C","explanation":"Powers of 2."},
        {"subject":"Thinking Skills","topic":"Deduction","difficulty":"Hard","stem":"All doctors are smart. Some smart people are musicians. Are all musicians smart?","options":"Yes|No|Sometimes|Cannot be determined","answer":"B","explanation":"Logical fallacy."},
        {"subject":"Thinking Skills","topic":"Coding","difficulty":"Hard","stem":"If 'PLAN' is 'QMBO', what is 'WORK'?","options":"XPSL|YPSL|XPLK|WORK","answer":"A","explanation":"Each letter +1."},
        {"subject":"Thinking Skills","topic":"Conclusion","difficulty":"Medium","stem":"Traffic is bad because of roadworks. People are late. What is the best conclusion?","options":"Roadworks cause lateness|Traffic is always bad|People should walk|None","answer":"A","explanation":"Causal link in text."},
        {"subject":"Thinking Skills","topic":"Sequence","difficulty":"Medium","stem":"Day, Week, Month, __?","options":"Year|Century|Hour|Decade","answer":"A","explanation":"Chronological order of time periods."}
    ]
    pool["thinking"].extend(thinking_additions)
    with open(POOL_FILE, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    print(f"✅ Thinking 확장 완료: {len(pool['thinking'])}개")

if __name__ == "__main__":
    expand_thinking()
