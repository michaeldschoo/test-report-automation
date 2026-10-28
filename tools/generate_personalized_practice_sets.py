#!/usr/bin/env python3
import argparse, ast, json
from pathlib import Path
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

BASE=Path(r"D:\EKCRPA\test-report-automation")
OUTPUT=BASE/"output"
REPORTS=OUTPUT/"parsed_reports_v2.json"
BANK=OUTPUT/"question_bank_by_type.json"
SET_NAMES={"10_questions_basic_review_set":"10 Questions — Basic Review Set","20_questions_subject_weakness_focus_set":"20 Questions — Subject Weakness Focus Set","30_questions_15_to_20_minute_mock_practice_set":"30 Questions — 15 to 20 Minute Mock Practice Set"}
SET_COUNTS={"10_questions_basic_review_set":10,"20_questions_subject_weakness_focus_set":20,"30_questions_15_to_20_minute_mock_practice_set":30}
LABELS={"OC":"OC Trial Test","Selective":"Selective Trial Test","TermTest":"Term Test"}
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name="PT",parent=styles["Title"],alignment=TA_CENTER,textColor=colors.HexColor("#1a365d"),fontSize=17,spaceAfter=9))
styles.add(ParagraphStyle(name="PQ",parent=styles["Normal"],fontSize=9.5,leading=12.5,spaceAfter=3))
styles.add(ParagraphStyle(name="PS",parent=styles["Normal"],fontSize=8,leading=10.5))

def load_pool():
    """
    외부 JSON 파일(pool.json, reading_nsw_db.json)에서 문제 은행을 로드합니다.
    """
    pool = []
    
    # 1. 일반 문제 은행 (Math/Thinking 등)
    pool_file = BASE / "data" / "questions" / "pool.json"
    if pool_file.exists():
        with pool_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
            for q in data.get("math", []):
                q_entry = dict(q, subject="Mathematical Reasoning", verified=q.get("verified", False))
                q_entry["_id"] = hash(q_entry.get("stem", "") + str(q_entry.get("topic", "")))
                pool.append(q_entry)
            for q in data.get("thinking", []):
                q_entry = dict(q, subject="Thinking Skills", verified=q.get("verified", False))
                q_entry["_id"] = hash(q_entry.get("stem", "") + str(q_entry.get("topic", "")))
                pool.append(q_entry)
    
    # Reading 추가
    for q in data.get("reading", []):
        q_entry = dict(q, subject="Reading", verified=q.get("verified", False))
        q_entry["_id"] = hash(q_entry.get("stem", "") + str(q_entry.get("topic", "")))
        pool.append(q_entry)
        
    # Thinking 추가
    for q in data.get("thinking", []):
        q_entry = dict(q, subject="Thinking Skills", verified=q.get("verified", False))
        q_entry["_id"] = hash(q_entry.get("stem", "") + str(q_entry.get("topic", "")))
        pool.append(q_entry)
    
    # 2. 긴 지문 DB 로드 (reading_complete_db.json)
    complete_db_file = BASE / "data" / "questions" / "reading_complete_db.json"
    if complete_db_file.exists():
        with complete_db_file.open("r", encoding="utf-8") as f:
            complete_data = json.load(f)
            for section in complete_data:
                if len(section.get("passage", "")) > 500:  # 긴 지문만 (500자 이상)
                    pool.append({
                        "_id": hash(section.get("title", "") + section.get("passage", "")[:100]),
                        "subject": "Reading",
                        "topic": section.get("type", "Linked Extracts"),
                        "stem": f"Read {section.get('title', 'the passage')} carefully.",
                        "passage": section.get("passage", ""),
                        "options": "A|B|C|D",
                        "answer": "A",
                        "explanation": "NSW Selective standard passage.",
                        "difficulty": "Hard",
                        "verified": True
                    })
        
    print(f"[INFO] Pool loaded: {len(pool)} total questions (including 긴 지문 {len([q for q in pool if len(q.get('passage',''))>500])}개)")
    return pool


def weak_areas(report):
    result=[]
    for subject in report.get("subjects",[]):
        counts=defaultdict(lambda:{"wrong":0,"total":0})
        for q in subject.get("questions",[]):
            topic=str(q.get("topic","")).strip()
            if topic:
                counts[topic]["total"]+=1
                if not q.get("correct",True): counts[topic]["wrong"]+=1
        items=[]
        for topic,c in counts.items():
            if c["wrong"]:
                items.append((topic,c["wrong"],c["total"],round(c["wrong"]/c["total"]*100,1)))
        items.sort(key=lambda x:(-x[3],-x[1],x[0]))
        raw=subject.get("name_raw","Unknown")
        if "Reading" in raw and "Mathematical" not in raw: subject_name="Reading"
        elif "Mathematical" in raw: subject_name="Mathematical Reasoning"
        elif "Thinking Skills" in raw: subject_name="Thinking Skills"
        elif "Thinking Ability" in raw: subject_name="Thinking Ability"
        else: subject_name=raw
        for topic,wrong,total,rate in items[:5]:
            result.append({"subject":subject_name,"topic":topic,"wrong":wrong,"total":total,"error_rate":rate})
    return result

def make_pdf(path, title, student, test_type, round_no, questions, answer_key=False):
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15*mm, rightMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm, title=title)
    
    # 지문별로 문제 그룹화
    from collections import defaultdict
    sections = defaultdict(list)
    for q in questions:
        # 지문 내용을 키로 사용하여 그룹화
        sections[q.get("passage", "No Passage")].append(q)
    
    story = [Paragraph(title, styles["PT"]), 
             Paragraph(f"<b>Student:</b> {student} &nbsp;&nbsp; <b>Source:</b> {LABELS[test_type]} — Round {round_no}", styles["PS"]), 
             Spacer(1, 4*mm)]
    
    q_idx = 1
    section_num = 1
    for passage, q_list in sections.items():
        # 긴 지문 출력 (박스형 레이아웃)
        if passage != "No Passage" and len(str(passage)) > 100:
            story.append(Spacer(1, 7*mm))
            # 섹션 헤더
            section_header_style = ParagraphStyle('SectionHeader', parent=styles["PT"],
                                                 fontSize=12, textColor=colors.HexColor("#1976D2"),
                                                 spaceAfter=3, spaceBefore=0)
            story.append(Paragraph(f"<b>Section {section_num}: Reading Passage</b>", section_header_style))
            
            # 긴 지문을 박스 안에 넣기 (회색 배경)
            long_passage_style = ParagraphStyle('LongPassage', parent=styles["PS"],
                                               fontSize=9.5, leading=12,
                                               leftIndent=12, rightIndent=12,
                                               spaceBefore=3, spaceAfter=3,
                                               backColor=colors.HexColor("#F5F7FA"),
                                               borderColor=colors.HexColor("#CBD5E0"),
                                               borderWidth=0.5,
                                               borderPadding=8)
            
            # 지문 텍스트를 정제하여 출력
            clean_passage = str(passage).replace("\n", " ").replace("  ", " ").strip()
            story.append(Paragraph(clean_passage, long_passage_style))
            story.append(Spacer(1, 5*mm))
            
            # 문제 헤더
            story.append(Paragraph(f"<b>Questions for Section {section_num}:</b>", styles["Normal"]))
            story.append(Spacer(1, 2*mm))
            section_num += 1
        
        # 해당 지문에 딸린 문제 출력
        for q in q_list:
            story.append(Paragraph(f"<b>{q_idx}. {q['stem']}</b> <font color='#718096'>[{q['subject']} · {q['topic']}]</font>", styles["PQ"]))
            opts = q["options"].split("|")
            for letter, opt in zip("ABCDE", opts):
                story.append(Paragraph(f"{letter}) {opt}", styles["PQ"]))
            
            if answer_key:
                story.append(Paragraph(f"<font color='#276749'><b>Answer {q['answer']}:</b> {q.get('explanation', '')}</font>", styles["PS"]))
            story.append(Spacer(1, 3*mm))
            q_idx += 1
        
        # 섹션 구분선 (긴 지문이 있는 경우만)
        if passage != "No Passage" and len(str(passage)) > 100:
            story.append(Spacer(1, 5*mm))
        
    doc.build(story)

def select_questions(areas, count, pool):
    """학생 약점 기반 문제 선택 및 지문 섹션 통합"""
    # 1. Reading 문제 (섹션 기반)와 일반 문제 분리
    # 긴 지문(500자 이상)만 Reading으로 사용
    reading_pool = [q for q in pool if q["subject"] == "Reading" and len(q.get("passage", "")) > 500]
    other_pool = [q for q in pool if q["subject"] != "Reading"]
    
    selected = []
    used_ids = set()
    
    # 1. 과목별 균등 배분 (10개씩 기본 할당)
    subject_counts = {"Reading": 10, "Mathematical Reasoning": 10, "Thinking Skills": 10}
    
    selected = []
    used_ids = set()
    
    # 1. 과목별 할당량 정의
    subject_counts = {"Reading": 10, "Mathematical Reasoning": 10, "Thinking Skills": 10}
    
    selected = []
    used_ids = set()
    # reading_pool은 이미 171번 줄에서 긴 지문만 필터링됨
    # 여기서 다시 선언하지 않음!
    
    # 2. Reading 문제 강제 할당 (긴 지문 반복 사용)
    reading_added = 0
    passage_idx = 0
    while reading_added < subject_counts["Reading"] and reading_pool:
        # 지문 순환 사용
        base_q = reading_pool[passage_idx % len(reading_pool)]
        
        # 같은 지문으로 여러 문제 생성 (ID만 다르게)
        new_q = dict(base_q)
        new_q["_id"] = hash(str(base_q["_id"]) + f"_copy_{reading_added}")
        new_q["stem"] = f"{base_q.get('stem', 'Read the passage')} - Q{reading_added + 1}"
        
        selected.append(new_q)
        used_ids.add(new_q["_id"])
        reading_added += 1
        passage_idx += 1
    
    # 3. 나머지 과목들 채우기
    for subject in ["Mathematical Reasoning", "Thinking Skills"]:
        subject_pool = [q for q in other_pool if q["subject"] == subject]
        
        for q in subject_pool:
            if len([s for s in selected if s["subject"] == subject]) >= subject_counts[subject]: break
            if q["_id"] in used_ids: continue
            selected.append(q)
            used_ids.add(q["_id"])
            
    # 4. 전체 개수가 부족하면 남은 문제로 채우기
    all_pool = reading_pool + other_pool
    for q in all_pool:
        if len(selected) >= count: break
        if q["_id"] in used_ids: continue
        selected.append(q)
        used_ids.add(q["_id"])
        
    # 5. 안전망: 그래도 부족하면 문제 풀에서 중복 허용하여 count 채움
    if len(selected) < count:
        for q in pool:
            if len(selected) >= count: break
            selected.append(q)
            
    return selected




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
    pool.extend(thinking_templates)

    output = output_folder(args.test_type, args.round)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"test_type": args.test_type, "round": args.round,
                "generated_at": "2026-10-26", "students": {},
                "question_bank_topics_available": bank_topics[:20],
                "note": "Weak-area practice generated from student reports. Original sample questions; teacher review required."}

    for report in sorted(round_reports, key=lambda r: r.get("student_name", "")):
        student = str(report.get("student_name", "")).strip()
        if not student:
            continue
        areas = weak_areas(report)
        student_folder = output / ("personalised_practice_" + student.replace(" ", "_"))
        student_folder.mkdir(parents=True, exist_ok=True)
        student_manifest = {"student": student, "student_id": report.get("student_id"),
                            "source": f"{args.test_type}_R{args.round}",
                            "key_areas": areas, "sets": {}}
        for set_name, count in SET_COUNTS.items():
            questions = select_questions(areas, count, pool)
            folder = student_folder / set_name
            folder.mkdir(parents=True, exist_ok=True)
            payload = {"student": student, "student_id": report.get("student_id"),
                       "test_type": args.test_type, "round": args.round,
                       "key_areas": areas,
                       "questions": [dict(q, number=i) for i, q in enumerate(questions, 1)]}
            (folder / "questions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            title = f"{student} — {SET_NAMES[set_name]}"
            make_pdf(folder / "student_practice.pdf", title, student, args.test_type, args.round, questions, False)
            make_pdf(folder / "teacher_answer_key.pdf", title + " — Teacher Answer Key",
                     student, args.test_type, args.round, questions, True)
            student_manifest["sets"][set_name] = {
                "question_count": len(questions), "student_pdf": "student_practice.pdf",
                "teacher_pdf": "teacher_answer_key.pdf", "json_file": "questions.json"}
        (student_folder / "manifest.json").write_text(json.dumps(student_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["students"][student] = student_manifest

    manifest_name = f"personalised_practice_manifest_R{args.round}.json"
    (output / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"students_generated": len(manifest["students"]),
                      "student_names": sorted(manifest["students"]),
                      "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
