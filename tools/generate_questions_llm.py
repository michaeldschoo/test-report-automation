#!/usr/bin/env python3
"""
LLM 기반 신규 문제 생성 파이프라인

목적
- 기출 시험지에서 추출한 문항(`exam_papers_raw.json`)과 지문(`reading_complete_db.json`)을
  **스타일 참조(exemplar)** 로 사용해 새로운 문항을 생성한다.
- 생성 결과는 반드시 **구조 검증 게이트**를 통과해야 DB에 들어간다.

모드
1) `--mode passage` (기본): 기존 긴 지문을 그대로 사용하고 **새 문항만** 생성
2) `--mode new`: 시험 스타일에 맞는 **새 지문 + 다문항**을 생성

사용 예
    python tools/generate_questions_llm.py --mode passage --limit 1 --dry-run
    python tools/generate_questions_llm.py --mock --limit 2
    set GEMINI_API_KEY=...   &&  python tools/generate_questions_llm.py --limit 5
    python tools/generate_questions_llm.py --provider openai --model gpt-4o-mini --limit 5

출력
    data/questions/generated_db.json      (생성 문항, structure_ok / verified 플래그)
    data/questions/generated_review.json  (검증 탈락 사유 목록)
"""
import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
EXAM_RAW = BASE / "data" / "questions" / "exam_papers_raw.json"
READING_DB = BASE / "data" / "questions" / "reading_complete_db.json"
GENERATED_DB = Path(os.environ.get("PRACTICE_GENERATED_DB", BASE / "data" / "questions" / "generated_db.json"))
REVIEW = BASE / "data" / "questions" / "generated_review.json"

LONG_PASSAGE_MIN = 300
MAX_OPTIONS = 5
MIN_OPTIONS = 4
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

SCHEMA_HINT = """[
  {
    "stem": "문제 본문 (영어, 15자 이상)",
    "options": ["보기1", "보기2", "보기3", "보기4"],
    "answer": "B",
    "explanation": "정답 근거를 지문에 기반해 1~2문장으로 설명",
    "topic": "Inference | Main Idea | Vocabulary in Context | Detail | Tone | Author's Purpose",
    "difficulty": "Medium"
  }
]"""


def log(msg):
    print(msg, flush=True)


def norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def load_exemplars():
    """기출에서 스타일 참조용 (지문, 문항) 목록을 만든다."""
    exemplars = []
    if READING_DB.exists():
        for section in json.loads(READING_DB.read_text(encoding="utf-8")):
            passage = str(section.get("passage", "")).strip()
            good = [q for q in section.get("questions", [])
                    if q.get("answer") and len([o for o in str(q.get("options", "")).split("|") if o.strip()]) >= 4]
            if len(passage) >= LONG_PASSAGE_MIN and good:
                exemplars.append({
                    "title": section.get("title", ""),
                    "passage": passage,
                    "questions": good,
                    "source": section.get("source", ""),
                })
    return exemplars


def load_generated():
    if GENERATED_DB.exists():
        try:
            return json.loads(GENERATED_DB.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


# ---------------------------------------------------------------- 프롬프트
def build_passage_prompt(exemplar, count):
    example_text = "\n".join(
        f"- {q['stem']} | 보기: {q['options']} | 정답: {q['answer']}"
        for q in exemplar["questions"][:3]
    )
    return f"""You are an experienced Australian selective-school exam writer.

TASK: Write {count} NEW multiple-choice reading comprehension questions for the passage below.
The passage is fixed — do NOT rewrite or summarise it.

PASSAGE
\"\"\"
{exemplar['passage'][:6000]}
\"\"\"

STYLE REFERENCE (existing questions on this passage — match their register and difficulty, but do NOT copy them)
{example_text}

RULES
1. Exactly {MIN_OPTIONS} or {MAX_OPTIONS} options per question.
2. One correct answer only; answer must be the option LETTER (A/B/C/D/E).
3. Every question must be answerable ONLY from the passage above.
4. Mix question types: main idea, detail, inference, vocabulary in context, author's purpose, tone.
5. Do NOT reuse the wording of the style reference questions.
6. Difficulty: "Medium" or "Hard".
7. Output STRICT JSON array only (no markdown, no commentary).

JSON SCHEMA
{SCHEMA_HINT}
"""


def build_new_prompt(topic_hint, count_questions):
    return f"""You are an experienced Australian selective-school exam writer.

TASK: Create a NEW {topic_hint} reading passage (350-700 words) and {count_questions} multiple-choice
questions on it, in the style of the NSW Selective / OC trial tests.

RULES
1. Passage: single coherent text, or two short linked extracts labelled "Extract A:" and "Extract B:".
2. Questions: exactly {MIN_OPTIONS} or {MAX_OPTIONS} options each, one correct answer.
3. Answer must be the option LETTER (A/B/C/D/E).
4. Mix question types: main idea, detail, inference, vocabulary in context, author's purpose, tone.
5. Original content only — do not reproduce any existing published text.
6. Output STRICT JSON object only (no markdown, no commentary):

{{
  "title": "short title",
  "passage": "the passage text",
  "questions": {SCHEMA_HINT}
}}
"""


# ---------------------------------------------------------------- LLM 호출
def request_with_retry(method, url, *, params=None, headers=None, json_body=None, timeout=180, attempts=3):
    """429/503/타임아웃에 대해 지수 백오프로 재시도한다."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.request(method, url, params=params, headers=headers, json=json_body, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if attempt < attempts:
                    wait = 5 * attempt
                    log(f"  [retry {attempt}/{attempts - 1}] HTTP {resp.status_code} → {wait}초 후 재시도")
                    time.sleep(wait)
                    continue
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
            return resp
        except requests.exceptions.Timeout as exc:
            last_error = exc
            if attempt < attempts:
                log(f"  [retry {attempt}/{attempts - 1}] 타임아웃 → 재시도")
                time.sleep(5 * attempt)
                continue
            raise
    raise last_error if last_error else RuntimeError("요청 실패")


def call_gemini(prompt, model, api_key, timeout=180):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 8192,
                             "responseMimeType": "application/json"},
    }
    resp = request_with_retry("POST", url, params={"key": api_key}, json_body=payload, timeout=timeout)
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"응답에 candidates 없음: {json.dumps(data)[:200]}")
    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise RuntimeError(f"빈 응답 (finishReason={candidates[0].get('finishReason')})")
    return text


def call_openai(prompt, model, api_key, timeout=180):
    url = "https://api.openai.com/v1/chat/completions"
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.7}
    resp = request_with_retry("POST", url, headers={"Authorization": f"Bearer {api_key}"},
                              json_body=payload, timeout=timeout)
    return resp.json()["choices"][0]["message"]["content"]


def extract_json(text):
    """LLM 응답에서 JSON 블록만 안전하게 추출한다."""
    text = str(text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("JSON 파싱 실패")


# ---------------------------------------------------------------- 검증 게이트
ALLOWED_TOPICS = {
    "main idea", "detail", "inference", "vocabulary in context", "tone",
    "author's purpose", "authors purpose", "structure", "comparison",
}


def clean_text(value):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value


def validate_question(raw, existing_stems):
    """생성 문항 1개를 검증한다. (사유 목록, 정규화된 문항) 반환"""
    reasons = []
    stem = clean_text(raw.get("stem"))
    options = [clean_text(o) for o in raw.get("options", []) if clean_text(o)]
    answer = str(raw.get("answer", "")).strip().upper()[:1]
    explanation = clean_text(raw.get("explanation"))
    topic = clean_text(raw.get("topic")) or "Inference"
    difficulty = clean_text(raw.get("difficulty")) or "Hard"

    if len(stem) < 15:
        reasons.append("stem_too_short")
    if not (MIN_OPTIONS <= len(options) <= MAX_OPTIONS):
        reasons.append(f"bad_option_count({len(options)})")
    if len(set(options)) != len(options):
        reasons.append("duplicate_options")
    if answer not in "ABCDE"[: len(options)]:
        reasons.append(f"bad_answer({answer or 'none'})")
    if len(explanation) < 10:
        reasons.append("no_explanation")
    if norm(stem) in existing_stems:
        reasons.append("duplicate_stem")
    if difficulty.lower() not in ("medium", "hard", "easy"):
        difficulty = "Hard"

    cleaned = {
        "stem": stem,
        "options": "|".join(options),
        "answer": answer,
        "explanation": explanation,
        "topic": topic,
        "difficulty": difficulty,
    }
    return reasons, cleaned


def mock_questions(passage, count):
    """API 키 없이 파이프라인을 검증하기 위한 결정적 샘플 (구조 검증용)"""
    head = clean_text(passage)[:80]
    items = []
    for i in range(count):
        items.append({
            "stem": f"[MOCK] According to the passage ({head}...), which statement is supported by the text? (sample {i + 1})",
            "options": [f"Option A for sample {i + 1}", f"Option B for sample {i + 1}",
                        f"Option C for sample {i + 1}", f"Option D for sample {i + 1}"],
            "answer": "ABCD"[i % 4],
            "explanation": f"[MOCK] 정답 {('ABCD'[i % 4])} 는 지문의 해당 부분에서 직접 확인된다.",
            "topic": "Inference",
            "difficulty": "Hard",
            "_mock": True,
        })
    return {"title": "MOCK SAMPLE", "passage": passage, "questions": items}


def collect_existing_stems():
    stems = set()
    pool_file = BASE / "data" / "questions" / "pool.json"
    if pool_file.exists():
        data = json.loads(pool_file.read_text(encoding="utf-8"))
        for key in ("math", "reading", "thinking"):
            for q in data.get(key, []):
                stems.add(norm(q.get("stem")))
    if READING_DB.exists():
        for section in json.loads(READING_DB.read_text(encoding="utf-8")):
            for q in section.get("questions", []):
                stems.add(norm(q.get("stem")))
    for section in load_generated():
        for q in section.get("questions", []):
            stems.add(norm(q.get("stem")))
    return stems


def resolve_api_key(provider):
    load_dotenv(BASE / ".env")
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API")
    return os.environ.get("OPENAI_API_KEY")


def generate_one(exemplar, args, api_key):
    """예시 1개에 대해 문항을 생성하고 검증하여 섹션을 반환한다."""
    count = args.questions
    if args.mode == "new":
        prompt = build_new_prompt(args.topic_hint, count)
    else:
        prompt = build_passage_prompt(exemplar, count)

    if args.dry_run:
        log("\n" + "=" * 70)
        log(prompt[:1500] + ("\n...[생략]..." if len(prompt) > 1500 else ""))
        return None, []

    if args.mock:
        payload = mock_questions(exemplar["passage"], count)
    else:
        if args.provider == "gemini":
            text = call_gemini(prompt, args.model, api_key)
        else:
            text = call_openai(prompt, args.model, api_key)
        payload = extract_json(text)

    if isinstance(payload, dict):
        passage = clean_text(payload.get("passage")) or exemplar["passage"]
        title = clean_text(payload.get("title")) or "Generated Passage"
        raw_questions = payload.get("questions", [])
        section_type = "Passage"
    else:
        passage = exemplar["passage"]
        title = exemplar.get("title") or "Generated Questions"
        raw_questions = payload
        section_type = "Linked Extracts" if re.search(r"(Extract|Text)\s+[A-D]\b", passage, re.I) else "Passage"

    existing = collect_existing_stems()
    accepted, rejects = [], []
    for raw in raw_questions:
        reasons, cleaned = validate_question(raw, existing)
        if reasons:
            rejects.append({"title": title, "stem": raw.get("stem", "")[:160], "reasons": reasons})
            continue
        existing.add(norm(cleaned["stem"]))
        accepted.append(cleaned)

    if len(accepted) < args.min_accept:
        return None, rejects

    section = {
        "type": section_type,
        "title": f"[LLM] {title}"[:120],
        "source": f"llm:{args.provider}:{args.model}",
        "passage": passage,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "structure_ok": True,
        "verified": False,
        "questions": accepted,
    }
    return section, rejects


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description="LLM 기반 신규 문제 생성 (Reading)")
    parser.add_argument("--mode", choices=["passage", "new"], default="passage",
                        help="passage=기존 지문 재사용, new=새 지문 생성")
    parser.add_argument("--provider", choices=["gemini", "openai"], default="gemini")
    parser.add_argument("--model", default=None, help="모델명 (기본: gemini-2.0-flash / gpt-4o-mini)")
    parser.add_argument("--limit", type=int, default=3, help="처리할 예시(지문) 수")
    parser.add_argument("--questions", type=int, default=5, help="지문당 생성 문항 수")
    parser.add_argument("--min-accept", type=int, default=3, help="섹션 채택 최소 문항 수")
    parser.add_argument("--topic-hint", default="narrative or persuasive", help="--mode new 일 때 지문 유형 힌트")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 프롬프트만 출력")
    parser.add_argument("--mock", action="store_true", help="API 없이 파이프라인 동작 검증")
    parser.add_argument("--out", default=None, help=f"출력 경로 (기본: {GENERATED_DB})")
    parser.add_argument("--review", default=None, help=f"검증 탈락 목록 경로 (기본: {REVIEW})")
    args = parser.parse_args()

    if not args.model:
        args.model = DEFAULT_GEMINI_MODEL if args.provider == "gemini" else DEFAULT_OPENAI_MODEL

    out_path = Path(args.out) if args.out else GENERATED_DB
    review_path = Path(args.review) if args.review else REVIEW

    api_key = None
    if not args.dry_run and not args.mock:
        api_key = resolve_api_key(args.provider)
        if not api_key:
            log(f"[ERR] {args.provider.upper()} API 키가 없습니다.")
            log("      .env 또는 환경변수에 아래 중 하나를 설정하세요:")
            log("        GEMINI_API_KEY=...   (또는 GOOGLE_API_KEY)")
            log("        OPENAI_API_KEY=...")
            log("      먼저 흐름을 확인하려면:  --dry-run  또는  --mock")
            return 1

    exemplars = load_exemplars()
    if args.mode == "new" and not exemplars:
        exemplars = [{"title": args.topic_hint, "passage": "", "questions": [], "source": "n/a"}]
    if not exemplars:
        log("[ERR] 스타일 참조로 쓸 예시가 없습니다. reading_complete_db.json 을 먼저 채우세요.")
        return 1

    if args.mode == "passage":
        exemplars = [e for e in exemplars if len(e.get("passage", "")) >= LONG_PASSAGE_MIN]
    exemplars = exemplars[: args.limit]
    log(f"[INFO] mode={args.mode} provider={args.provider} model={args.model} exemplars={len(exemplars)} "
        f"questions/exemplar={args.questions}")

    new_sections, all_rejects = [], []
    for idx, exemplar in enumerate(exemplars, 1):
        log(f"\n[{idx}/{len(exemplars)}] {str(exemplar.get('title'))[:60]}")
        try:
            section, rejects = generate_one(exemplar, args, api_key)
        except Exception as exc:
            log(f"  [ERR] {exc}")
            continue
        all_rejects.extend(rejects)
        if section:
            log(f"  ✓ 문항 {len(section['questions'])}개 생성 (탈락 {len(rejects)}건)")
            new_sections.append(section)
        else:
            log(f"  - 채택 기준 미달 (탈락 {len(rejects)}건)")

    if args.dry_run:
        log("\n[DRY-RUN] API를 호출하지 않았습니다. 파일도 쓰지 않습니다.")
        return 0

    existing = load_generated()
    existing_passages = {norm(s.get("passage"))[:300] for s in existing}
    added = 0
    for section in new_sections:
        key = norm(section["passage"])[:300]
        if key in existing_passages:
            log(f"  [중복] 이미 있는 지문: {section['title'][:50]}")
            continue
        existing_passages.add(key)
        existing.append(section)
        added += 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path.write_text(json.dumps(all_rejects, ensure_ascii=False, indent=2), encoding="utf-8")

    total_q = sum(len(s.get("questions", [])) for s in existing)
    log("\n" + "=" * 60)
    log(f"완료: 신규 섹션 {added}개 / 누적 섹션 {len(existing)}개 / 누적 문항 {total_q}개")
    log(f"  저장: {out_path}")
    log(f"  검증 탈락 {len(all_rejects)}건 -> {review_path}")
    log("  ※ verified=false 상태입니다. 검수 후 true 로 바꾸면 생성기가 사용합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



