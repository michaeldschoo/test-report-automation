#!/usr/bin/env python3
"""
exam_papers_raw.json → reading_complete_db.json 변환기

- `tools/extract_exam_papers.py` 가 만든 원본 추출 결과를
  맞춤 문제집 생성기(`generate_personalized_practice_sets.py`)가 읽는 형식으로 변환한다.
- 채택 조건: 긴 지문(>=300자) + 정답이 있는 문항 3개 이상
- 기존 DB(수작업 문항)는 보존하고, 지문/문항 중복만 제거하며 병합한다.

사용 예
    python tools/build_reading_db_from_papers.py
    python tools/build_reading_db_from_papers.py --min-questions 4 --dry-run
"""
import argparse
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "questions" / "exam_papers_raw.json"
DB = BASE / "data" / "questions" / "reading_complete_db.json"
LONG_PASSAGE_MIN = 300
DEFAULT_MIN_QUESTIONS = 3

# stem 이 잘린 것으로 보이는 어미 (줄바꿈 처리 실패 흔적)
TRUNCATED_ENDINGS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "at", "by", "for", "from",
    "with", "as", "that", "which", "who", "whose", "when", "if", "is", "are", "was",
    "were", "be", "been", "should", "would", "could", "can", "may", "might", "must",
    "because", "although", "while", "than", "then", "into", "about", "most", "more",
}


def is_truncated_stem(stem):
    words = re.findall(r"[A-Za-z]+", stem.lower())
    if not words:
        return True
    return words[-1] in TRUNCATED_ENDINGS


def clean_stem(stem):
    stem = re.sub(r"^[\s\.\|:\-–—]+", "", str(stem or ""))
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def clean_passage(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def convert_section(paper, section, min_questions):
    passage = clean_passage(section.get("passage", ""))
    if len(passage) < LONG_PASSAGE_MIN:
        return None

    questions = []
    for q in section.get("questions", []):
        opts = [str(o).strip() for o in q.get("options", []) if str(o).strip()]
        answer = q.get("answer")
        stem = clean_stem(q.get("stem", ""))
        if not answer or answer not in "ABCDE"[: len(opts)] or len(opts) < 4:
            continue
        if len(stem) < 12 or is_truncated_stem(stem):
            continue
        if any(len(o) < 1 for o in opts):
            continue
        questions.append({
            "stem": stem,
            "options": "|".join(opts),
            "answer": answer,
            "explanation": q.get("explanation", "") or f"정답은 {answer}번입니다.",
            "topic": section.get("type", "Linked Extracts"),
            "difficulty": q.get("difficulty", "Hard"),
        })
    if len(questions) < min_questions:
        return None

    return {
        "type": section.get("type", "Linked Extracts"),
        "title": f"{paper['paper_id']} — {section.get('title', '')}".strip(),
        "source": paper.get("file"),
        "passage": passage,
        "questions": questions,
    }


def main():
    parser = argparse.ArgumentParser(description="추출된 시험지 문항을 Reading DB로 병합")
    parser.add_argument("--raw", default=str(RAW))
    parser.add_argument("--db", default=str(DB))
    parser.add_argument("--min-questions", type=int, default=DEFAULT_MIN_QUESTIONS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    raw_path = Path(args.raw)
    if not raw_path.exists():
        raise SystemExit(f"[ERR] 추출 결과가 없습니다: {raw_path}\n"
                         f"      먼저 `python tools/extract_exam_papers.py` 를 실행하세요.")

    papers = json.loads(raw_path.read_text(encoding="utf-8"))
    db_path = Path(args.db)
    existing = json.loads(db_path.read_text(encoding="utf-8")) if db_path.exists() else []
    if isinstance(existing, dict):
        existing = [existing]

    seen_passages = {norm(s.get("passage", ""))[:400] for s in existing}
    seen_stems = set()
    for s in existing:
        for q in s.get("questions", []):
            seen_stems.add(norm(q.get("stem", "")))

    added = []
    skipped_short = 0
    skipped_dup = 0
    skipped_few = 0
    for paper in papers:
        for section in paper.get("sections", []):
            entry = convert_section(paper, section, args.min_questions)
            if not entry:
                passage_len = len(clean_passage(section.get("passage", "")))
                if passage_len < LONG_PASSAGE_MIN:
                    skipped_short += 1
                else:
                    skipped_few += 1
                continue
            key = norm(entry["passage"])[:400]
            if key in seen_passages:
                skipped_dup += 1
                continue
            unique_questions = []
            for q in entry["questions"]:
                stem_key = norm(q["stem"])
                if stem_key in seen_stems:
                    continue
                seen_stems.add(stem_key)
                unique_questions.append(q)
            if len(unique_questions) < args.min_questions:
                skipped_few += 1
                continue
            entry["questions"] = unique_questions
            seen_passages.add(key)
            added.append(entry)

    merged = existing + added
    total_q = sum(len(s.get("questions", [])) for s in merged)
    print(f"[INFO] papers={len(papers)}, 신규 섹션={len(added)}, 건너뜀(짧은지문={skipped_short}, 문항부족={skipped_few}, 중복={skipped_dup})")
    print(f"[INFO] DB 섹션 {len(existing)} → {len(merged)} / 문항 {sum(len(s.get('questions', [])) for s in existing)} → {total_q}")
    for e in added:
        print(f"  + {e['title'][:60]} | 문항 {len(e['questions'])} | 지문 {len(e['passage'])}자")

    if args.dry_run:
        print("[DRY-RUN] 파일을 쓰지 않았습니다.")
        return

    db_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 저장: {db_path}")


if __name__ == "__main__":
    main()
