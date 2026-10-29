#!/usr/bin/env python3
"""
시험지 PDF → 문항 DB 추출기 (OCR 기반)

배경
- J: 드라이브의 시험지는 **텍스트 레이어가 없는 스캔 PDF** 이므로 OCR 이 필수다.
- 기본 tesseract psm 3 은 보기 라벨(A/B/C/D)을 잃어버린다. psm 4 를 사용해야
  `A ...`, `B ...`, `Cc ...`, `D___ ...` 형태로 안정적으로 추출된다.
- 정답은 `... ANS.pdf` 에 **굵은 글씨(볼드)** 로 표시되어 있다.
  두 PDF 의 동일 좌표에서 잉크(어두운 픽셀) 밀도를 비교해 정답을 판정한다.
  (실측: 정답 보기 1.17~1.22 vs 오답 0.99~1.05)

사용 예
    python tools/extract_exam_papers.py --limit 3
    python tools/extract_exam_papers.py --subject ENG --out data/questions/exam_papers_raw.json
    python tools/extract_exam_papers.py --roots "J:\\...\\TEST" --limit 10

출력
    data/questions/exam_papers_raw.json  (논문/섹션/문항/정답 + 신뢰도)
    data/questions/exam_papers_review.json (정답 신뢰도가 낮아 검수가 필요한 문항)
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
from pdf2image import convert_from_path
import pytesseract

DEFAULT_POPPLER = os.environ.get("POPPLER_PATH", r"F:\poppler-26.09.0\Library\bin")
DEFAULT_ROOTS = [
    r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2027\TEST",
    r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2027\TEST",
]

# 2022~2025 연도별 아카이브 (--archive 로 추가)
ARCHIVE_ROOTS = [
    r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2022\OC Test",
    r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2023\OC Test",
    r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2024\Test",
    r"J:\My Drive\EKC  OFFICE\OC - NEW\OC 2025\TEST",
    r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2022\STT test",
    r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2023\STT test",
    r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2024\TEST",
    r"J:\My Drive\EKC  OFFICE\STT - NEW\STT2025\TEST",
]
DPI = 300
TESS_CFG = "--oem 3 --psm 4"

# 페이지 머리글/바닥글 등 문항이 아닌 줄
NOISE_RE = re.compile(
    r"^(?:"
    r"===\s*Page\s*\d+\s*===?"
    r"|.*Edu-Kingdom College.*"
    r"|.*EDU-KINGDOM.*"
    r"|.*Tutorial Coaching Specialist.*"
    r"|.*Fulfil your dream.*"
    r"|.*Copyright.*"
    r"|Reading Skills\s*\d*"
    r"|Mathematical Reasoning\s*\d*"
    r"|Thinking Skills?\s*\d*"
    r"|Test\s*\d+\s*"
    r"|Time Allowed.*"
    r"|Student Name.*"
    r"|SELECTIVE HIGH SCHOOL.*"
    r"|\d+\s*$"
    r"|[0-9OQUVW>\[\]|]{4,}\s*"          # OCR 잡음 토큰 (예: "00NWU>")
    r")$",
    re.IGNORECASE,
)

QUESTION_RE = re.compile(r"^\s*(\d{1,2})\s*[\.\)]\s*(.+?)\s*$")
OPTION_RE = re.compile(r"^\s*([A-E])\s*(?:[\)\.\:]|[_=]{1,}|-{2,}|\s)\s*(.+?)\s*$")
RANGE_RE = re.compile(r"Questions?\s+(\d{1,2})\s*(?:to|fo|ffo|—|-|~)\s*(\d{1,2})", re.IGNORECASE)
PASSAGE_RE = re.compile(r"^\s*(Extract|Text|Passage)\s+([A-D])?\s*[:\-]?\s*(.*)$", re.IGNORECASE)

# 정답 판정 임계값 (실측 기반)
ANSWER_MIN_RATIO = 1.08      # 정답 보기의 최소 잉크 비율
ANSWER_MIN_MARGIN = 0.05     # 2위 보기와의 최소 격차
LONG_PASSAGE_MIN = 300


def log(msg):
    print(msg, flush=True)


def ocr_lines(image):
    """OCR 결과를 줄 단위(text, top, bottom)로 묶어 반환한다."""
    data = pytesseract.image_to_data(image, lang="eng", config=TESS_CFG, output_type=pytesseract.Output.DICT)
    groups = {}
    for i, raw in enumerate(data["text"]):
        text = (raw or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = 0.0
        if conf < 0:             # tesseract 가 텍스트가 아니라고 판단한 토큰만 배제
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        top = data["top"][i]
        height = data["height"][i]
        left = data["left"][i]
        entry = groups.setdefault(key, {"top": top, "bottom": top + height, "left": left, "words": []})
        entry["top"] = min(entry["top"], top)
        entry["bottom"] = max(entry["bottom"], top + height)
        entry["left"] = min(entry["left"], left)
        entry["words"].append(text)
    lines = [{"text": " ".join(v["words"]), "top": v["top"], "bottom": v["bottom"], "left": v["left"]}
             for v in groups.values()]
    lines.sort(key=lambda x: x["top"])
    return lines


def normalize_option_body(body):
    """'Cc Frustration ...', 'A device found ...' 처럼 남아 있는 라벨 조각을 제거한다."""
    body = re.sub(r"^[A-E](?:[a-e])?[\.\)\:]?\s+", "", body)
    return body.strip()


def clean_label(text):
    """'Cc' 'D___' 'A __' 같은 OCR 변형에서 보기 라벨과 본문을 분리한다."""
    m = OPTION_RE.match(text)
    if not m:
        return None
    letter = m.group(1).upper()
    body = m.group(2).strip()
    body = re.sub(r"^[_=\-\s]+", "", body).strip()
    body = normalize_option_body(body)
    body = re.sub(r"\s+", " ", body)
    if len(body) < 1:
        return None
    return letter, body


def parse_questions(lines, allowed=None):
    """
    줄 목록에서 문항(번호/본문/보기)을 추출한다.
    allowed: 허용할 문항 번호 집합 ('Questions N to M' 범위 밖의 숫자 오인 방지)
    """
    questions = []
    current = None
    option_indent = None
    for line in lines:
        text = line["text"].strip()
        if not text or NOISE_RE.match(text):
            continue

        label = clean_label(text)
        q = QUESTION_RE.match(text)

        # 새 문항 시작 (보기 라벨 패턴이 아닌 경우만)
        if q and not label:
            num = int(q.group(1))
            if allowed is not None and num not in allowed:
                continue
            current = {"no": num, "stem": q.group(2).strip(), "options": [],
                       "lines": {"stem": [line], "options": []}}
            questions.append(current)
            option_indent = None
            continue

        if current is None:
            continue

        if label:
            _, body = label
            if option_indent is None:
                option_indent = line["left"]
            current["options"].append(body)
            current["lines"]["options"].append(line)
            continue

        # 라벨이 유실된 보기: 문제 블록 안의 짧은 줄은 새 보기로 간주 (보기는 보통 한 줄)
        if current["options"] and len(current["options"]) < 5 and len(text) <= 140:
            body = normalize_option_body(text)
            if body:
                current["options"].append(body)
                current["lines"]["options"].append(line)
            continue

        if current["options"]:
            current["options"][-1] = (current["options"][-1] + " " + text).strip()
            if current["lines"]["options"]:
                current["lines"]["options"][-1] = line
        else:
            # 보기가 아직 없을 때: 줄 간격이 촘촘하면 stem 의 줄바꿈으로 본다
            stem_lines = current["lines"]["stem"]
            gap = line["top"] - stem_lines[-1]["bottom"] if stem_lines else 999
            if len(current["stem"]) < 40 or gap < 30:
                current["stem"] = (current["stem"] + " " + text).strip()
                stem_lines.append(line)
            else:
                body = normalize_option_body(text)
                if body:
                    current["options"].append(body)
                    current["lines"]["options"].append(line)
    return questions


def ink_count(gray, top, bottom, pad=3):
    """지정한 y 구간의 어두운 픽셀 수(잉크량)"""
    h = gray.shape[0]
    t = max(0, int(top) - pad)
    b = min(h, int(bottom) + pad)
    if b <= t:
        return 0
    return int((gray[t:b, :] < 128).sum())


def detect_answers(questions, paper_pages, ans_pages):
    """
    정답지의 굵은 글씨(볼드)를 이용해 정답을 판정한다.
    정답 보기는 잉크 비율(ANS/paper)이 1.08 이상, 2위 대비 0.05 이상 높다.
    판정이 어려우면 answer=None 으로 남겨 검수 대상으로 보낸다.
    """
    for q in questions:
        option_lines = q["lines"].get("options", [])
        q["_ratios"] = []
        if not option_lines:
            continue
        page_idx = option_lines[0].get("page")
        if page_idx is None or page_idx >= len(ans_pages) or page_idx >= len(paper_pages):
            continue
        paper = np.array(paper_pages[page_idx])
        ans = np.array(ans_pages[page_idx])
        h = min(paper.shape[0], ans.shape[0])
        w = min(paper.shape[1], ans.shape[1])
        paper, ans = paper[:h, :w], ans[:h, :w]
        ratios = []
        for line in option_lines:
            p_ink = ink_count(paper, line["top"], line["bottom"])
            a_ink = ink_count(ans, line["top"], line["bottom"])
            ratios.append(a_ink / p_ink if p_ink else 0.0)
        q["_ratios"] = [round(r, 2) for r in ratios]


def resolve_answers(questions, letters="ABCDE"):
    """잉크 비율 목록에서 정답 라벨을 결정한다."""
    for q in questions:
        ratios = q.get("_ratios") or []
        q["answer"] = None
        q["answer_confidence"] = 0.0
        if len(ratios) < 2:
            continue
        order = sorted(range(len(ratios)), key=lambda i: -ratios[i])
        best = order[0]
        if best >= len(letters):
            continue
        margin = ratios[best] - ratios[order[1]] if len(order) > 1 else ratios[best]
        if ratios[best] >= ANSWER_MIN_RATIO and margin >= ANSWER_MIN_MARGIN:
            q["answer"] = letters[best]
            q["answer_confidence"] = round(margin, 3)


def build_sections_from_lines(all_lines):
    """
    'Questions N to M.' 마커를 기준으로 섹션을 나눈다.
    각 섹션 = [마커 다음 줄 ~ 다음 마커 전] 이며,
    첫 문항 이전까지의 텍스트를 지문(passage)으로 사용한다.
    """
    markers = []
    for idx, line in enumerate(all_lines):
        m = RANGE_RE.search(line["text"])
        if m:
            markers.append((idx, int(m.group(1)), int(m.group(2))))

    if not markers:
        return [{"type": "Standalone", "title": "Unlabelled", "passage": "",
                 "questions": parse_questions(all_lines)}]

    sections = []
    for i, (start_idx, q_start, q_end) in enumerate(markers):
        end_idx = markers[i + 1][0] if i + 1 < len(markers) else len(all_lines)
        block = all_lines[start_idx + 1:end_idx]

        first_q = None
        for j, line in enumerate(block):
            qm = QUESTION_RE.match(line["text"].strip())
            if qm and int(qm.group(1)) == q_start and not clean_label(line["text"]):
                first_q = j
                break

        if first_q is None:
            passage_lines, question_lines = block, []
        else:
            passage_lines, question_lines = block[:first_q], block[first_q:]

        kept = [l["text"].strip() for l in passage_lines
                if l["text"].strip() and not NOISE_RE.match(l["text"].strip())]
        passage = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
        allowed = set(range(q_start, q_end + 1))
        questions = parse_questions(question_lines, allowed)

        sections.append({
            "type": "Linked Extracts" if re.search(r"(Extract|Text)\s+[A-D]\b", passage, re.IGNORECASE) else "Passage",
            "title": f"Questions {q_start}-{q_end}",
            "passage": passage,
            "questions": questions,
        })
    return sections


def find_ans_file(paper_path):
    """`... ENG.pdf` → `... ENG ANS.pdf` 짝을 찾는다."""
    candidate = paper_path.with_name(paper_path.stem + " ANS.pdf")
    if candidate.exists():
        return candidate
    for p in paper_path.parent.glob("*.pdf"):
        if p.name.upper().endswith("ANS.PDF") and paper_path.stem.upper() in p.name.upper():
            return p
    return None


def detect_subject(name):
    upper = name.upper()
    for subject in ("ENG", "MATH", "TS"):
        if re.search(rf"\b{subject}\b", upper):
            return subject
    if "WRITING" in upper:
        return "WRITING"
    return "UNKNOWN"


def render(pdf_path, poppler):
    return convert_from_path(str(pdf_path), DPI, poppler_path=poppler, grayscale=True)


def process_paper(paper_path, poppler):
    """시험지 1개를 OCR·파싱해 구조화된 dict 로 만든다."""
    ans_path = find_ans_file(paper_path)
    paper_pages = render(paper_path, poppler)
    ans_pages = render(ans_path, poppler) if ans_path else []

    all_lines = []
    for page_idx, page in enumerate(paper_pages):
        for line in ocr_lines(page):
            line["page"] = page_idx
            all_lines.append(line)

    sections = build_sections_from_lines(all_lines)
    all_questions = [q for s in sections for q in s["questions"]]
    detect_answers(all_questions, paper_pages, ans_pages)
    resolve_answers(all_questions)

    for section in sections:
        for q in section["questions"]:
            for key in ("_ratios", "lines"):
                q.pop(key, None)

    valid_sections = []
    for section in sections:
        good = []
        for q in section["questions"]:
            opts = q.get("options", [])
            if len(opts) < 4 or not q.get("stem") or len(q["stem"]) < 10:
                continue
            answer = q.get("answer")
            q["answer"] = answer if answer and answer in "ABCDE"[: len(opts)] else None
            good.append(q)
        if good:
            section["questions"] = good
            section["long_passage"] = len(section.get("passage", "")) >= LONG_PASSAGE_MIN
            valid_sections.append(section)

    return {
        "paper_id": normalize_paper_id(paper_path.name, path_context(paper_path)),
        "file": paper_path.name,
        "ans_file": ans_path.name if ans_path else None,
        "subject": detect_subject(paper_path.name),
        "sections": valid_sections,
    }


def collect_papers(roots, subject_filter, include_ans=False, match=None):
    """루트 목록에서 시험지 PDF(정답지 제외)를 수집한다. (동일 파일명 중복 제거)"""
    papers = []
    seen_ids = set()
    seen_roots = set()
    for root in roots:
        base = Path(root)
        if not base.exists():
            log(f"[SKIP] 경로 없음: {root}")
            continue
        try:
            resolved = str(base.resolve()).lower()
        except OSError:
            resolved = str(base).lower()
        if resolved in seen_roots:          # 대소문자만 다른 동일 폴더 중복 방지
            continue
        seen_roots.add(resolved)

        for pdf in sorted(base.rglob("*.pdf")):
            name = pdf.name.upper()
            if not include_ans and "ANS" in name:
                continue
            if "WRITING" in name:
                continue
            if "RESULT" in str(pdf.parent).upper():    # 결과지 폴더 제외
                continue
            if match and match.upper() not in name:
                continue
            subject = detect_subject(pdf.name)
            if subject_filter and subject not in subject_filter:
                continue
            pid = normalize_paper_id(pdf.name, path_context(pdf))
            if pid in seen_ids:             # "OC06 ENG (2).pdf" 같은 사본 제외
                continue
            seen_ids.add(pid)
            papers.append(pdf)
    return papers


def path_context(pdf_path):
    """상위 폴더에서 연도 컨텍스트를 뽑는다. (예: 'OC 2023' → OC2023, 'STT2024' → STT2024)"""
    for part in reversed(Path(pdf_path).parts[:-1]):
        m = re.search(r"(OC|STT)\s*[-_]?\s*(\d{4})", part, re.IGNORECASE)
        if m:
            return f"{m.group(1).upper()}{m.group(2)}"
    return ""


def normalize_paper_id(filename, context=""):
    """파일명 → 안정적인 paper_id ('OC06 ENG (2).pdf' → 'OC2023|OC06 ENG')"""
    stem = Path(filename).stem
    stem = re.sub(r"\s*\(\d+\)\s*$", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip().upper()
    return f"{context}|{stem}" if context else stem


def worker(task):
    """병렬 처리용 워커 (프로세스에서 실행)"""
    path_str, poppler = task
    try:
        return process_paper(Path(path_str), poppler)
    except Exception as exc:
        p = Path(path_str)
        return {"paper_id": normalize_paper_id(p.name, path_context(p)), "file": p.name,
                "error": str(exc), "sections": []}


def main():
    parser = argparse.ArgumentParser(description="시험지 PDF → 문항 DB 추출기 (OCR)")
    parser.add_argument("--roots", nargs="*", default=DEFAULT_ROOTS, help="시험지 PDF 루트 폴더들")
    parser.add_argument("--subjects", nargs="*", default=["ENG"], help="추출 대상 과목 (ENG MATH TS)")
    parser.add_argument("--limit", type=int, default=0, help="처리할 시험지 수 제한 (테스트용)")
    parser.add_argument("--match", default=None, help="파일명에 포함될 문자열 필터 (예: STT26)")
    parser.add_argument("--out", default="data/questions/exam_papers_raw.json")
    parser.add_argument("--review", default="data/questions/exam_papers_review.json")
    parser.add_argument("--poppler", default=DEFAULT_POPPLER)
    parser.add_argument("--workers", type=int, default=1, help="병렬 프로세스 수 (권장 4~8)")
    parser.add_argument("--append", action="store_true", help="기존 결과 파일에 이어붙이기")
    parser.add_argument("--skip-existing", action="store_true", help="이미 처리한 paper_id 는 건너뛰기")
    parser.add_argument("--archive", action="store_true", help="2022~2025 연도별 아카이브 루트도 포함")
    args = parser.parse_args()

    roots = list(args.roots)
    if args.archive:
        roots.extend(ARCHIVE_ROOTS)

    if not Path(args.poppler).exists():
        log(f"[WARN] poppler 경로를 찾을 수 없습니다: {args.poppler} (POPPLER_PATH 환경변수로 지정 가능)")

    papers = collect_papers(roots, set(args.subjects), match=args.match)
    log(f"[INFO] 대상 시험지: {len(papers)}개 | 과목: {sorted(args.subjects)}")

    previous = []
    out_path = Path(args.out)
    if (args.append or args.skip_existing) and out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = []
    done_ids = {p.get("paper_id") for p in previous if p.get("paper_id")}
    if args.skip_existing and done_ids:
        before = len(papers)
        papers = [p for p in papers if normalize_paper_id(p.name, path_context(p)) not in done_ids]
        log(f"[INFO] 이미 처리된 {before - len(papers)}개 제외 → 남은 {len(papers)}개")

    if args.limit:
        papers = papers[: args.limit]
    if not papers:
        log("[INFO] 처리할 시험지가 없습니다.")
        return 0

    results = []
    review = []
    started = time.time()
    tasks = [(str(p), args.poppler) for p in papers]

    def handle(parsed, idx):
        if not parsed:
            return
        if parsed.get("error"):
            log(f"[{idx}/{len(papers)}] {parsed['file']}  [ERR] {parsed['error'][:80]}")
            return
        results.append(parsed)
        q_total = sum(len(s["questions"]) for s in parsed["sections"])
        q_answered = sum(1 for s in parsed["sections"] for q in s["questions"] if q.get("answer"))
        long_sections = [s for s in parsed["sections"] if s.get("long_passage")]
        log(f"[{idx}/{len(papers)}] {parsed['file']}  sections={len(parsed['sections'])} "
            f"questions={q_total} answered={q_answered} long={len(long_sections)}")
        for s in parsed["sections"]:
            for q in s["questions"]:
                if not q.get("answer"):
                    review.append({
                        "file": parsed["file"], "section": s["title"], "question_no": q["no"],
                        "stem": q["stem"], "options": q["options"],
                    })

    if args.workers and args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        log(f"[INFO] 병렬 처리: workers={args.workers}")
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(worker, t): i for i, t in enumerate(tasks, 1)}
            for fut in as_completed(futures):
                handle(fut.result(), futures[fut])
    else:
        for idx, task in enumerate(tasks, 1):
            handle(worker(task), idx)

    merged = previous + results
    seen = set()
    deduped = []
    for item in merged:
        pid = item.get("paper_id")
        if pid and pid in seen:
            continue
        seen.add(pid)
        deduped.append(item)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    review_path = Path(args.review)
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed = time.time() - started
    total_q = sum(len(s["questions"]) for r in deduped for s in r["sections"])
    total_ans = sum(1 for r in deduped for s in r["sections"] for q in s["questions"] if q.get("answer"))
    total_long = sum(len([q for q in s["questions"] if q.get("answer")])
                     for r in deduped for s in r["sections"] if s.get("long_passage"))
    log("\n" + "=" * 60)
    log(f"완료: 이번 {len(results)}편 / 누적 {len(deduped)}편  ({elapsed / 60:.1f}분)")
    log(f"  문항 {total_q}개 (정답 판정 {total_ans}개, {total_ans / total_q * 100 if total_q else 0:.1f}%)")
    log(f"  긴 지문(>={LONG_PASSAGE_MIN}자) 섹션의 정답 확보 문항: {total_long}개")
    log(f"  저장: {out_path}")
    log(f"  이번 실행 검수 필요(정답 미판정): {len(review)}건 -> {review_path}")
    return 0


if __name__ == "__main__":
    main()
