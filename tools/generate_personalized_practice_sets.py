#!/usr/bin/env python3
import argparse, json, os, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# 프로젝트 루트 경로 동적 감지 (Windows D:\ 드라이브 및 로컬/클라우드 환경 호환)
DEFAULT_WINDOWS_BASE = Path(r"D:\EKCRPA\test-report-automation")
SCRIPT_DIR = Path(__file__).resolve().parent.parent
BASE = DEFAULT_WINDOWS_BASE if (DEFAULT_WINDOWS_BASE / "output").exists() else SCRIPT_DIR
OUTPUT = BASE / "output"
REPORTS = OUTPUT / "parsed_reports_v2.json"
BANK = OUTPUT / "question_bank_by_type.json"

SET_NAMES = {
    "10_questions_basic_review_set": "10 Questions — Basic Review Set",
    "20_questions_subject_weakness_focus_set": "20 Questions — Subject Weakness Focus Set",
    "30_questions_15_to_20_minute_mock_practice_set": "30 Questions — 15 to 20 Minute Mock Practice Set"
}
SET_COUNTS = {
    "10_questions_basic_review_set": 10,
    "20_questions_subject_weakness_focus_set": 20,
    "30_questions_15_to_20_minute_mock_practice_set": 30
}
LABELS = {"OC": "OC Trial Test", "Selective": "Selective Trial Test", "TermTest": "Term Test"}

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="PT", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#1a365d"), fontSize=17, spaceAfter=9))
styles.add(ParagraphStyle(name="PQ", parent=styles["Normal"], fontSize=9.5, leading=12.5, spaceAfter=3))
styles.add(ParagraphStyle(name="PS", parent=styles["Normal"], fontSize=8, leading=10.5))

# --- 문제 선별 정책 -------------------------------------------------------
# Reading 은 긴 지문(long passage) 기반 다문항 세트를 우선 사용한다.
LONG_PASSAGE_MIN = 300     # 긴 지문 최소 길이(문자)
MIN_PER_SUBJECT = 2        # 학생 성취도와 무관하게 모든 과목에 보장하는 최소 문항 수
MAX_PER_PASSAGE = 8        # 한 지문에서 뽑을 최대 문항 수 (실제 시험지 구성과 동일하게)
SUBJECT_GROUPS = ("Reading", "Mathematical Reasoning", "Thinking")

# 지문만 있고 실제 문제가 없는 플레이스홀더 stem (예: "Read Extract A: ... carefully. - Q1")
_PLACEHOLDER_STEM = re.compile(r'^\s*Read\s+Extract\s+.*carefully\.?\s*-?\s*Q\d+\s*$', re.IGNORECASE)


# stem 중복 판정용 키 (공백/대소문자 정규화 + 전체 문장 사용)
def _stem_key(q):
    stem = re.sub(r"\s+", " ", str(q.get("stem", "")).strip()).lower()
    topic = str(q.get("topic", "")).strip().lower()
    return stem + "|" + topic


def is_usable_question(q):
    """더미 선택지('A|B|C|D'), 빈 본문, 플레이스홀더 stem, 잘못된 정답을 배제한다."""
    options_raw = str(q.get("options", ""))
    opts = [o.strip() for o in options_raw.split("|") if o.strip()]
    stem = str(q.get("stem", "")).strip()
    if len(opts) < 2 or options_raw.strip() == "A|B|C|D":
        return False
    if not stem or _PLACEHOLDER_STEM.match(stem):
        return False
    if str(q.get("answer", "")).strip().upper() not in list("ABCDE")[:len(opts)]:
        return False
    return True


def normalize_subject(name_raw):
    """'Selective Trial Test Reading Skills' 같은 원본 이름을 표준 과목명으로 정규화"""
    raw = str(name_raw or "")
    if "Reading" in raw and "Mathematical" not in raw:
        return "Reading"
    if "Mathematical" in raw:
        return "Mathematical Reasoning"
    if "Thinking" in raw:
        return "Thinking"
    return raw


def subject_accuracy(report):
    """Progress Report 의 과목별 정답률(0~1). 리포트가 없으면 빈 dict."""
    accuracy = {}
    for subject in (report or {}).get("subjects", []):
        questions = subject.get("questions", [])
        total = subject.get("total") or len(questions)
        if not total:
            continue
        correct = subject.get("correct_count")
        if correct is None:
            correct = sum(1 for q in questions if q.get("correct"))
        accuracy[normalize_subject(subject.get("name_raw"))] = correct / total
    return accuracy


def allocate_counts(count, report, stock):
    """
    학생 성취도 기반 유동 배분.
    - 정답률이 낮은 과목(약점)에 더 많은 문항 배정
    - 모든 과목 최소 MIN_PER_SUBJECT 문항 보장 (재고가 부족하면 축소)
    - 과목별 가용 재고(stock)를 넘지 않음
    """
    subjects = [s for s in SUBJECT_GROUPS if stock.get(s, 0) > 0]
    if not subjects or count <= 0:
        return {}

    accuracy = subject_accuracy(report)
    # 정답률이 낮을수록 큰 가중치 (1.0 ~ 3.0). 리포트에 과목이 없으면 중립(0.5)
    weights = {s: 1.0 + (1.0 - accuracy.get(s, 0.5)) * 2.0 for s in subjects}

    counts = {s: 0 for s in subjects}
    remaining = count

    # 1) 과목별 최소 보장
    for subj in subjects:
        base = min(MIN_PER_SUBJECT, stock[subj], remaining)
        counts[subj] = base
        remaining -= base

    # 2) 남은 문항을 약점 가중치 비례로 분배 (재고 한도)
    eligible = [s for s in subjects if stock[s] > counts[s]]
    total_weight = sum(weights[s] for s in eligible)
    if remaining > 0 and total_weight > 0:
        shares = {s: remaining * weights[s] / total_weight for s in eligible}
        for s in eligible:
            give = min(int(shares[s]), stock[s] - counts[s], remaining)
            counts[s] += give
            remaining -= give
        # 소수부가 큰 과목부터 1문항씩 추가 배정
        order = sorted(eligible, key=lambda s: -(shares[s] - int(shares[s])))
        while remaining > 0 and order:
            progressed = False
            for s in order:
                if remaining <= 0:
                    break
                if counts[s] < stock[s]:
                    counts[s] += 1
                    remaining -= 1
                    progressed = True
            if not progressed:
                break

    return counts


def group_reading_by_passage(questions):
    """Reading 문항을 지문 단위로 묶는다 (긴 지문에 여러 문항이 함께 출제되도록)"""
    groups = defaultdict(list)
    for q in questions:
        groups[str(q.get("passage", "")).strip()].append(q)
    return groups



def load_pool():
    """
    외부 JSON 파일(pool.json, reading_complete_db.json)에서 유효한 문제 은행을 로드합니다.
    - 더미 선택지('A|B|C|D')나 빈 본문이 있는 항목은 배제합니다.
    """
    pool = []
    seen_stems = set()

    # 1. pool.json 로드
    pool_file = BASE / "data" / "questions" / "pool.json"
    if pool_file.exists():
        with pool_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

            for q in data.get("math", []):
                q_entry = dict(q, subject="Mathematical Reasoning", verified=q.get("verified", False))
                stem_key = _stem_key(q_entry)
                if stem_key and stem_key not in seen_stems:
                    seen_stems.add(stem_key)
                    q_entry["_id"] = hash(stem_key)
                    pool.append(q_entry)

            for q in data.get("reading", []):
                # 더미 옵션('A|B|C|D')/플레이스홀더 문항은 제외하고 유효 문제만 로드
                if is_usable_question(q):
                    q_entry = dict(q, subject="Reading", verified=q.get("verified", True))
                    stem_key = _stem_key(q_entry)
                    if stem_key and stem_key not in seen_stems:
                        seen_stems.add(stem_key)
                        q_entry["_id"] = hash(stem_key)
                        pool.append(q_entry)

            for q in data.get("thinking", []):
                q_entry = dict(q, subject="Thinking Skills", verified=q.get("verified", False))
                stem_key = _stem_key(q_entry)
                if stem_key and stem_key not in seen_stems:
                    seen_stems.add(stem_key)
                    q_entry["_id"] = hash(stem_key)
                    pool.append(q_entry)

    # 2. reading_complete_db.json 로드 (유효한 세부 문항이 있는 경우 포함)
    complete_db_file = BASE / "data" / "questions" / "reading_complete_db.json"
    if complete_db_file.exists():
        try:
            with complete_db_file.open("r", encoding="utf-8") as f:
                complete_data = json.load(f)
                for section in complete_data:
                    passage = section.get("passage", "")
                    for q in section.get("questions", []):
                        if is_usable_question(q):
                            stem_key = _stem_key(q)
                            if stem_key and stem_key not in seen_stems:
                                seen_stems.add(stem_key)
                                pool.append({
                                    "_id": hash(stem_key),
                                    "subject": "Reading",
                                    "topic": q.get("topic", section.get("type", "Linked Extracts")),
                                    "stem": q.get("stem", ""),
                                    "passage": passage,
                                    "options": q.get("options", ""),
                                    "answer": q.get("answer", "A"),
                                    "explanation": q.get("explanation", "NSW standard reading question."),
                                    "difficulty": q.get("difficulty", "Hard"),
                                    "verified": True
                                })
        except Exception as e:
            print(f"[WARN] Error reading complete_db_file: {e}")

    # 3. LLM 생성 문항 로드 (구조 검증을 통과한 섹션만 사용)
    generated_file = Path(os.environ.get("PRACTICE_GENERATED_DB",
                                         BASE / "data" / "questions" / "generated_db.json"))
    generated_count = 0
    if generated_file.exists():
        try:
            for section in json.loads(generated_file.read_text(encoding="utf-8")):
                if not (section.get("structure_ok") or section.get("verified")):
                    continue
                passage = section.get("passage", "")
                for q in section.get("questions", []):
                    if not is_usable_question(q):
                        continue
                    stem_key = _stem_key(q)
                    if not stem_key or stem_key in seen_stems:
                        continue
                    seen_stems.add(stem_key)
                    pool.append({
                        "_id": hash(stem_key),
                        "subject": "Reading",
                        # 리포트 토픽(Linked Extracts 등)과 동일한 공간으로 맞춰 선택되도록 한다
                        "topic": section.get("type", "Linked Extracts"),
                        "skill": q.get("topic", "Inference"),
                        "stem": q.get("stem", ""),
                        "passage": passage,
                        "options": q.get("options", ""),
                        "answer": q.get("answer", ""),
                        "explanation": q.get("explanation", ""),
                        "difficulty": q.get("difficulty", "Hard"),
                        "verified": bool(section.get("verified", False)),
                        "source": section.get("source", "llm"),
                    })
                    generated_count += 1
        except Exception as e:
            print(f"[WARN] Error reading generated_db: {e}")

    math_count = len([q for q in pool if q.get("subject") == "Mathematical Reasoning"])
    reading_count = len([q for q in pool if q.get("subject") == "Reading"])
    thinking_count = len([q for q in pool if "Thinking" in q.get("subject", "")])
    print(f"[INFO] Pool loaded: {len(pool)} total questions (Math: {math_count}, Reading: {reading_count}, Thinking: {thinking_count})")
    if generated_count:
        print(f"       LLM 생성 문항 포함: {generated_count}개 ({generated_file.name})")

    reading_grouped = group_reading_by_passage([q for q in pool if q.get("subject") == "Reading"])
    long_groups = {p: qs for p, qs in reading_grouped.items() if len(p) >= LONG_PASSAGE_MIN}
    long_count = sum(len(qs) for qs in long_groups.values())
    print(f"       Reading: {len(reading_grouped)} passages / long passages(>={LONG_PASSAGE_MIN} chars): "
          f"{len(long_groups)} passages, {long_count} questions")

    if reading_count == 0:
        print("[WARN] Reading 문항이 0개입니다! data/questions/pool.json 의 reading 항목과 "
              "data/questions/reading_complete_db.json 을 확인하세요. (지문만 있고 문항이 없으면 생성되지 않습니다)")
    elif long_count == 0:
        print(f"[WARN] 긴 지문(>={LONG_PASSAGE_MIN}자) Reading 문항이 없어 단문 위주로 출제됩니다. "
              "reading_complete_db.json 에 긴 지문+다문항 세트를 추가하세요.")
    return pool


def weak_areas(report):
    result = []
    for subject in report.get("subjects", []):
        counts = defaultdict(lambda: {"wrong": 0, "total": 0})
        for q in subject.get("questions", []):
            topic = str(q.get("topic", "")).strip()
            if topic:
                counts[topic]["total"] += 1
                if not q.get("correct", True):
                    counts[topic]["wrong"] += 1
        items = []
        for topic, c in counts.items():
            if c["wrong"]:
                items.append((topic, c["wrong"], c["total"], round(c["wrong"] / c["total"] * 100, 1)))
        items.sort(key=lambda x: (-x[3], -x[1], x[0]))
        raw = subject.get("name_raw", "Unknown")
        if "Reading" in raw and "Mathematical" not in raw:
            subject_name = "Reading"
        elif "Mathematical" in raw:
            subject_name = "Mathematical Reasoning"
        elif "Thinking Skills" in raw:
            subject_name = "Thinking Skills"
        elif "Thinking Ability" in raw:
            subject_name = "Thinking Ability"
        else:
            subject_name = raw
        for topic, wrong, total, rate in items[:5]:
            result.append({"subject": subject_name, "topic": topic, "wrong": wrong, "total": total, "error_rate": rate})
    return result


def escape_xml(text):
    """ReportLab Paragraph 내 XML 특수문자 안전 이스케이프"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_pdf(path, title, student, test_type, round_no, questions, answer_key=False):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=title)

    # 지문(Passage)별로 문제 그룹화
    sections = defaultdict(list)
    for q in questions:
        passage = q.get("passage", "")
        # 지문이 충분히 긴 경우(80자 이상) 지문 섹션으로 묶음
        key = passage if (passage and len(str(passage).strip()) > 80) else "No Passage"
        sections[key].append(q)

    story = [
        Paragraph(escape_xml(title), styles["PT"]),
        Paragraph(f"<b>Student:</b> {escape_xml(student)} &nbsp;&nbsp; <b>Source:</b> {LABELS.get(test_type, test_type)} — Round {round_no}", styles["PS"]),
        Spacer(1, 4 * mm)
    ]

    q_idx = 1
    section_num = 1
    for passage, q_list in sections.items():
        # 긴 지문이 있는 경우: 회색 배경 박스 레이아웃으로 지문 출력
        if passage != "No Passage":
            story.append(Spacer(1, 4 * mm))
            section_header_style = ParagraphStyle(
                'SectionHeader', parent=styles["PT"],
                fontSize=12, textColor=colors.HexColor("#1976D2"),
                spaceAfter=3, spaceBefore=0, alignment=0
            )
            story.append(Paragraph(f"<b>Section {section_num}: Reading Passage</b>", section_header_style))

            long_passage_style = ParagraphStyle(
                'LongPassage', parent=styles["PS"],
                fontSize=9, leading=12,
                leftIndent=10, rightIndent=10,
                spaceBefore=3, spaceAfter=3,
                backColor=colors.HexColor("#F5F7FA"),
                borderColor=colors.HexColor("#CBD5E0"),
                borderWidth=0.5,
                borderPadding=7
            )

            # 지문 단락 유지 (줄바꿈 <br/><br/> 변환)
            safe_passage = escape_xml(passage).strip()
            safe_passage = re.sub(r'\n\s*\n', '<br/><br/>', safe_passage)
            safe_passage = safe_passage.replace('\n', '<br/>')
            story.append(Paragraph(safe_passage, long_passage_style))
            story.append(Spacer(1, 4 * mm))

            story.append(Paragraph(f"<b>Questions for Section {section_num}:</b>", styles["Normal"]))
            story.append(Spacer(1, 2 * mm))
            section_num += 1

        # 해당 지문에 딸린 문제들 출력
        for q in q_list:
            stem_safe = escape_xml(q.get("stem", ""))
            subj_safe = escape_xml(q.get("subject", ""))
            topic_safe = escape_xml(q.get("skill") or q.get("topic", ""))
            story.append(Paragraph(f"<b>{q_idx}. {stem_safe}</b> <font color='#718096'>[{subj_safe} · {topic_safe}]</font>", styles["PQ"]))

            opts = q.get("options", "").split("|")
            for letter, opt in zip("ABCDE", opts):
                opt_safe = escape_xml(opt.strip())
                # 이미 'A)' 나 'A.' 접두어가 붙어있는 경우 중복 제거
                opt_safe = re.sub(r'^[A-Ea-e][\)\.]\s*', '', opt_safe)
                story.append(Paragraph(f"{letter}) {opt_safe}", styles["PQ"]))

            if answer_key:
                ans_safe = escape_xml(q.get("answer", ""))
                exp_safe = escape_xml(q.get("explanation", ""))
                story.append(Paragraph(f"<font color='#276749'><b>Answer {ans_safe}:</b> {exp_safe}</font>", styles["PS"]))

            story.append(Spacer(1, 2.5 * mm))
            q_idx += 1

        if passage != "No Passage":
            story.append(Spacer(1, 4 * mm))

    doc.build(story)


def select_questions(areas, count, pool, report=None):
    """
    학생 약점 + 성취도 기반 문제 선택
    - Reading: 긴 지문(>=LONG_PASSAGE_MIN) 그룹을 우선 사용하고, 한 지문에 여러 문항을 묶어 출제
    - 모든 과목 최소 MIN_PER_SUBJECT 문항 보장
    - 학생 리포트의 과목별 정답률에 따라 과목별 문항 수를 유동 배분
    - 세트 내 중복 출제 금지
    """
    # 1. 유효 문제 필터링 (더미/플레이스홀더/정답오류 배제) + 동일 stem 중복 제거
    valid_pool = []
    seen_stems = set()
    for q in pool:
        if not is_usable_question(q):
            continue
        norm_stem = re.sub(r'\s+', ' ', str(q.get("stem", "")).strip()).lower()
        if not norm_stem or norm_stem in seen_stems:
            continue
        seen_stems.add(norm_stem)
        if "_id" not in q:
            q["_id"] = hash(q.get("subject", "") + str(q.get("topic", "")) + norm_stem[:80])
        valid_pool.append(q)

    reading = [q for q in valid_pool if q.get("subject") == "Reading"]
    math_pool = [q for q in valid_pool if q.get("subject") == "Mathematical Reasoning"]
    thinking_pool = [q for q in valid_pool if "Thinking" in q.get("subject", "")]

    # 2. Reading 은 긴 지문 그룹만 후보로 사용 (긴 지문이 없을 때만 단문으로 폴백)
    reading_groups = group_reading_by_passage(reading)
    long_groups = {p: qs for p, qs in reading_groups.items() if len(p) >= LONG_PASSAGE_MIN}
    use_groups = long_groups or {p: qs for p, qs in reading_groups.items() if p}
    reading_candidates = [q for qs in use_groups.values() for q in qs]

    # 3. 과목별 재고를 반영한 유동 배분
    stock = {
        "Reading": len(reading_candidates),
        "Mathematical Reasoning": len(math_pool),
        "Thinking": len(thinking_pool),
    }
    target_counts = allocate_counts(count, report, stock)

    selected = []
    used_ids = set()

    def take(q):
        selected.append(q)
        used_ids.add(q["_id"])

    def subject_count(subj_group):
        if subj_group == "Thinking":
            return len([s for s in selected if "Thinking" in s.get("subject", "")])
        return len([s for s in selected if s.get("subject") == subj_group])

    def remaining_quota(subj_group):
        return target_counts.get(subj_group, 0) - subject_count(subj_group)

    def weak_topics(subj_group):
        return {a["topic"].lower().strip() for a in areas if normalize_subject(a["subject"]) == subj_group}

    def topic_matches(q, wanted):
        q_topic = str(q.get("topic", "")).lower().strip()
        return any(w == q_topic or (w and (w in q_topic or q_topic in w)) for w in wanted)

    # 4. Reading: 약점 주제를 담은 긴 지문 그룹을 우선 선택하고, 그룹 안에서 여러 문항을 연속 배정
    wanted_reading = weak_topics("Reading")
    group_order = sorted(
        use_groups.items(),
        key=lambda item: (
            0 if any(topic_matches(q, wanted_reading) for q in item[1]) else 1,  # 약점 지문 우선
            -len(item[0]),                                                        # 긴 지문 우선
            -len(item[1]),                                                        # 문항이 많은 지문 우선
        )
    )
    for passage, group_questions in group_order:
        if remaining_quota("Reading") <= 0:
            break
        ordered = sorted(group_questions, key=lambda q: 0 if topic_matches(q, wanted_reading) else 1)
        # 기출/LLM 생성 문항을 교대로 배치해 학생이 다양한 출처의 문항을 받도록 한다
        exam_qs = [q for q in ordered if not str(q.get("source", "")).startswith("llm")]
        llm_qs = [q for q in ordered if str(q.get("source", "")).startswith("llm")]
        mixed = []
        for i in range(max(len(exam_qs), len(llm_qs))):
            if i < len(exam_qs):
                mixed.append(exam_qs[i])
            if i < len(llm_qs):
                mixed.append(llm_qs[i])
        taken_here = 0
        for q in mixed:
            if remaining_quota("Reading") <= 0 or taken_here >= MAX_PER_PASSAGE:
                break
            if q["_id"] not in used_ids:
                take(q)
                taken_here += 1

    # 5. Math / Thinking: 약점 주제 우선 → 같은 과목의 다른 문항으로 보충
    for subj_group, subj_pool in (("Mathematical Reasoning", math_pool), ("Thinking", thinking_pool)):
        if remaining_quota(subj_group) <= 0:
            continue
        wanted = weak_topics(subj_group)
        ordered = sorted(subj_pool, key=lambda q: (0 if topic_matches(q, wanted) else 1, str(q.get("topic", ""))))
        for q in ordered:
            if remaining_quota(subj_group) <= 0:
                break
            if q["_id"] not in used_ids:
                take(q)

    # 6. 모든 과목 최소 보장 (재고 부족으로 배분이 비었을 때 대비)
    for subj_group, subj_pool in (("Reading", reading_candidates),
                                  ("Mathematical Reasoning", math_pool),
                                  ("Thinking", thinking_pool)):
        need = MIN_PER_SUBJECT - subject_count(subj_group)
        for q in subj_pool:
            if need <= 0 or len(selected) >= count:
                break
            if q["_id"] not in used_ids:
                take(q)
                need -= 1

    # 7. 남은 자리는 전체 재고에서 보충 (중복 없음)
    if len(selected) < count:
        for q in reading_candidates + math_pool + thinking_pool:
            if len(selected) >= count:
                break
            if q["_id"] not in used_ids:
                take(q)

    # 8. 문제집 순서 정렬: 과목 순 → 긴 지문 그룹 → 주제
    def sort_order(q):
        subj_prio = {"Reading": 1, "Mathematical Reasoning": 2, "Thinking Skills": 3, "Thinking Ability": 3}
        has_passage = 0 if len(str(q.get("passage", "")).strip()) >= LONG_PASSAGE_MIN else 1
        passage_id = str(q.get("passage", ""))[:40]
        return (subj_prio.get(q.get("subject"), 4), has_passage, passage_id, str(q.get("topic", "")))

    selected.sort(key=sort_order)
    return selected[:count]


def output_folder(test_type, round_no):
    if test_type == "OC":
        return OUTPUT / f"OC_R{int(round_no):02d}"
    if test_type == "Selective":
        return OUTPUT / f"Selective_R{int(round_no)}"
    return OUTPUT / f"{test_type}_R{int(round_no)}"


def main():
    parser = argparse.ArgumentParser(description="Generate personalised practice sets from student progress reports.")
    parser.add_argument("--test-type", required=True, choices=["OC", "Selective", "TermTest"])
    parser.add_argument("--round", required=True, type=int)
    parser.add_argument("--reports-json", default=str(REPORTS))
    parser.add_argument("--bank-json", default=str(BANK))
    args = parser.parse_args()

    reports = json.loads(Path(args.reports_json).read_text(encoding="utf-8"))
    round_reports = [r for r in reports
                     if r.get("test_type") == args.test_type
                     and r.get("test_round") == args.round]
    if not round_reports:
        parser.error(f"No reports found for {args.test_type} Round {args.round}")

    bank_payload = json.loads(Path(args.bank_json).read_text(encoding="utf-8")) if Path(args.bank_json).exists() else {}
    bank_topics = []
    bank_type = bank_payload.get("question_bank", {}).get(args.test_type, {})
    for question in bank_type.get("questions", []):
        topic = str(question.get("topic", "")).strip()
        if topic and topic not in bank_topics:
            bank_topics.append(topic)

    pool = load_pool()
    thinking_subject = "Thinking Skills" if args.test_type == "OC" else "Thinking Ability"
    thinking_templates = [
        {"subject": thinking_subject, "topic": "Coding", "difficulty": "Medium",
         "stem": "If APPLE is coded by changing each letter to the next letter, what is the code for APPLE?",
         "options": "BQQMF|BOQKF|BQPLF|BQQLE|BQQME", "answer": "A",
         "explanation": "Each letter advances one position."},
        {"subject": thinking_subject, "topic": "Missing number", "difficulty": "Medium",
         "stem": "What number comes next: 3, 6, 12, 24, __?",
         "options": "36|48|42|54|30", "answer": "B",
         "explanation": "Each number doubles, so 24 × 2 = 48."},
        {"subject": thinking_subject, "topic": "Drawing Conclusion", "difficulty": "Medium",
         "stem": "All blue shapes are circles. This shape is blue. Which conclusion must follow?",
         "options": "It is red.|It is a square.|It is a circle.|It is large.|It has four sides.",
         "answer": "C", "explanation": "The stated rule means a blue shape is a circle."},
    ]
    # 기본 사고력 템플릿은 문제은행에 동일 문항이 없을 때만 추가
    existing_stems = {re.sub(r'\s+', ' ', str(q.get("stem", "")).strip()).lower() for q in pool}
    for t in thinking_templates:
        norm_stem = re.sub(r'\s+', ' ', t["stem"].strip()).lower()
        if norm_stem in existing_stems:
            continue
        existing_stems.add(norm_stem)
        t["_id"] = hash(t["stem"])
        pool.append(t)

    output = output_folder(args.test_type, args.round)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "test_type": args.test_type,
        "round": args.round,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "students": {},
        "question_bank_topics_available": bank_topics[:20],
        "note": "Weak-area practice generated from student reports with verified unique questions."
    }
    allocation_log = defaultdict(lambda: defaultdict(int))

    for report in sorted(round_reports, key=lambda r: r.get("student_name", "")):
        student = str(report.get("student_name", "")).strip()
        if not student:
            continue
        areas = weak_areas(report)
        student_folder = output / ("personalised_practice_" + student.replace(" ", "_"))
        student_folder.mkdir(parents=True, exist_ok=True)
        student_manifest = {
            "student": student,
            "student_id": report.get("student_id"),
            "source": f"{args.test_type}_R{args.round}",
            "key_areas": areas,
            "sets": {}
        }
        for set_name, count in SET_COUNTS.items():
            questions = select_questions(areas, count, pool, report)
            folder = student_folder / set_name
            folder.mkdir(parents=True, exist_ok=True)
            payload = {
                "student": student,
                "student_id": report.get("student_id"),
                "test_type": args.test_type,
                "round": args.round,
                "key_areas": areas,
                "questions": [dict({k: v for k, v in q.items() if k != "_id"}, number=i)
                              for i, q in enumerate(questions, 1)]
            }
            (folder / "questions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            title = f"{student} — {SET_NAMES[set_name]}"
            make_pdf(folder / "student_practice.pdf", title, student, args.test_type, args.round, questions, False)
            make_pdf(folder / "teacher_answer_key.pdf", title + " — Teacher Answer Key", student, args.test_type, args.round, questions, True)
            subject_counts = defaultdict(int)
            for q in questions:
                subject_counts[normalize_subject(q.get("subject"))] += 1
            for key, val in subject_counts.items():
                allocation_log[set_name][key] += val
            student_manifest["sets"][set_name] = {
                "question_count": len(questions),
                "subject_counts": dict(subject_counts),
                "student_pdf": "student_practice.pdf",
                "teacher_pdf": "teacher_answer_key.pdf",
                "json_file": "questions.json"
            }
        (student_folder / "manifest.json").write_text(json.dumps(student_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["students"][student] = student_manifest

    manifest_name = f"personalised_practice_manifest_R{args.round}.json"
    (output / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n[INFO] 세트별 과목 배분 합계 (학생 전체 누적)")
    for set_name in SET_COUNTS:
        dist = dict(allocation_log[set_name])
        print(f"  {set_name}: {dist}")
    print(json.dumps({
        "students_generated": len(manifest["students"]),
        "student_names": sorted(manifest["students"]),
        "output": str(output)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
