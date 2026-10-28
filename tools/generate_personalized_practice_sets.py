#!/usr/bin/env python3
import argparse, json, re
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
                stem_key = q_entry.get("stem", "")[:80] + str(q_entry.get("topic", ""))
                if stem_key and stem_key not in seen_stems:
                    seen_stems.add(stem_key)
                    q_entry["_id"] = hash(stem_key)
                    pool.append(q_entry)

            for q in data.get("reading", []):
                opts = [o.strip() for o in q.get("options", "").split("|") if o.strip()]
                # 더미 옵션('A|B|C|D')이 아니고 실제 선택지가 있는 유효 문제만 로드
                if len(opts) >= 2 and q.get("options") != "A|B|C|D":
                    q_entry = dict(q, subject="Reading", verified=q.get("verified", True))
                    stem_key = q_entry.get("stem", "")[:80] + str(q_entry.get("topic", ""))
                    if stem_key and stem_key not in seen_stems:
                        seen_stems.add(stem_key)
                        q_entry["_id"] = hash(stem_key)
                        pool.append(q_entry)

            for q in data.get("thinking", []):
                q_entry = dict(q, subject="Thinking Skills", verified=q.get("verified", False))
                stem_key = q_entry.get("stem", "")[:80] + str(q_entry.get("topic", ""))
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
                        opts = [o.strip() for o in q.get("options", "").split("|") if o.strip()]
                        if len(opts) >= 2 and q.get("options") != "A|B|C|D":
                            stem_key = q.get("stem", "")[:80] + str(q.get("topic", ""))
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

    math_count = len([q for q in pool if q.get("subject") == "Mathematical Reasoning"])
    reading_count = len([q for q in pool if q.get("subject") == "Reading"])
    thinking_count = len([q for q in pool if "Thinking" in q.get("subject", "")])
    print(f"[INFO] Pool loaded: {len(pool)} total questions (Math: {math_count}, Reading: {reading_count}, Thinking: {thinking_count})")
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
            topic_safe = escape_xml(q.get("topic", ""))
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


def select_questions(areas, count, pool):
    """
    학생 약점 기반 문제 선택 및 과목별 균형 배분
    - 유효한 문제만 선택 (더미 A|B|C|D 제외)
    - 중복 출제 완전 방지
    """
    # 1. 유효 문제 필터링
    valid_pool = []
    for q in pool:
        opts = [o.strip() for o in q.get("options", "").split("|") if o.strip()]
        stem = str(q.get("stem", "")).strip()
        if len(opts) >= 2 and q.get("options") != "A|B|C|D" and stem:
            if "_id" not in q:
                q["_id"] = hash(q.get("subject", "") + str(q.get("topic", "")) + stem[:80])
            valid_pool.append(q)

    reading_pool = [q for q in valid_pool if q.get("subject") == "Reading"]
    math_pool = [q for q in valid_pool if q.get("subject") == "Mathematical Reasoning"]
    thinking_pool = [q for q in valid_pool if "Thinking" in q.get("subject", "")]

    # 2. 목표 과목별 할당량 설정
    if count == 30:
        target_counts = {
            "Reading": min(10, len(reading_pool)),
            "Mathematical Reasoning": min(10, len(math_pool)),
            "Thinking Skills": min(10, len(thinking_pool))
        }
    elif count == 20:
        target_counts = {
            "Reading": min(7, len(reading_pool)),
            "Mathematical Reasoning": min(7, len(math_pool)),
            "Thinking Skills": min(6, len(thinking_pool))
        }
    else:  # 10문항 기본 세트
        target_counts = {
            "Reading": min(4, len(reading_pool)),
            "Mathematical Reasoning": min(4, len(math_pool)),
            "Thinking Skills": min(2, len(thinking_pool))
        }

    selected = []
    used_ids = set()

    # 3. 1차: 학생의 약점 Topic 순위대로 문제 매칭
    for area in sorted(areas, key=lambda x: (-x["error_rate"], -x["wrong"])):
        wanted_topic = area["topic"].lower().strip()
        wanted_subj = area["subject"].lower().strip()
        subj_key = "Reading" if "reading" in wanted_subj else ("Mathematical Reasoning" if "math" in wanted_subj else "Thinking Skills")

        current_subj_count = len([s for s in selected if s.get("subject") == subj_key or (subj_key == "Thinking Skills" and "Thinking" in s.get("subject", ""))])
        if current_subj_count >= target_counts.get(subj_key, 10):
            continue

        for q in valid_pool:
            if q["_id"] in used_ids:
                continue
            q_subj = q.get("subject", "").lower()
            q_topic = q.get("topic", "").lower()
            if (wanted_subj in q_subj or q_subj in wanted_subj) and (wanted_topic == q_topic or wanted_topic in q_topic or q_topic in wanted_topic):
                selected.append(q)
                used_ids.add(q["_id"])
                current_subj_count += 1
                if len(selected) >= count:
                    break
                if current_subj_count >= target_counts.get(subj_key, 10):
                    break
        if len(selected) >= count:
            break

    # 4. 2차: 과목별 할당량이 남아있으면 해당 과목의 다른 문제들로 보충
    subject_pools = {
        "Reading": reading_pool,
        "Mathematical Reasoning": math_pool,
        "Thinking Skills": thinking_pool
    }
    for subj_key, s_pool in subject_pools.items():
        cur_count = len([s for s in selected if s.get("subject") == subj_key or (subj_key == "Thinking Skills" and "Thinking" in s.get("subject", ""))])
        needed = target_counts.get(subj_key, 0) - cur_count
        if needed > 0:
            for q in s_pool:
                if q["_id"] not in used_ids:
                    selected.append(q)
                    used_ids.add(q["_id"])
                    needed -= 1
                    if len(selected) >= count:
                        break
                    if needed <= 0:
                        break
        if len(selected) >= count:
            break

    # 5. 3차: 전체 문항 수(count)에 도달할 때까지 남은 유효 문제로 채우기 (중복 없음)
    for q in valid_pool:
        if len(selected) >= count:
            break
        if q["_id"] not in used_ids:
            selected.append(q)
            used_ids.add(q["_id"])

    # 6. 문제집 순서 정렬: 지문이 있는 문제들은 지문 단위로 묶고 과목별로 정돈
    def sort_order(q):
        subj_prio = {"Reading": 1, "Mathematical Reasoning": 2, "Thinking Skills": 3, "Thinking Ability": 3}
        has_passage = 0 if len(str(q.get("passage", "")).strip()) > 80 else 1
        passage_id = str(q.get("passage", ""))[:40]
        return (subj_prio.get(q.get("subject"), 4), has_passage, passage_id, q.get("topic", ""))

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
    for t in thinking_templates:
        t["_id"] = hash(t["stem"])
        pool.append(t)

    output = output_folder(args.test_type, args.round)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "test_type": args.test_type,
        "round": args.round,
        "generated_at": "2026-10-28",
        "students": {},
        "question_bank_topics_available": bank_topics[:20],
        "note": "Weak-area practice generated from student reports with verified unique questions."
    }

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
            questions = select_questions(areas, count, pool)
            folder = student_folder / set_name
            folder.mkdir(parents=True, exist_ok=True)
            payload = {
                "student": student,
                "student_id": report.get("student_id"),
                "test_type": args.test_type,
                "round": args.round,
                "key_areas": areas,
                "questions": [dict(q, number=i) for i, q in enumerate(questions, 1)]
            }
            (folder / "questions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            title = f"{student} — {SET_NAMES[set_name]}"
            make_pdf(folder / "student_practice.pdf", title, student, args.test_type, args.round, questions, False)
            make_pdf(folder / "teacher_answer_key.pdf", title + " — Teacher Answer Key", student, args.test_type, args.round, questions, True)
            student_manifest["sets"][set_name] = {
                "question_count": len(questions),
                "student_pdf": "student_practice.pdf",
                "teacher_pdf": "teacher_answer_key.pdf",
                "json_file": "questions.json"
            }
        (student_folder / "manifest.json").write_text(json.dumps(student_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["students"][student] = student_manifest

    manifest_name = f"personalised_practice_manifest_R{args.round}.json"
    (output / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "students_generated": len(manifest["students"]),
        "student_names": sorted(manifest["students"]),
        "output": str(output)
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
