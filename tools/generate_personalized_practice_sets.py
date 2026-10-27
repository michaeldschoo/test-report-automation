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
    문제 은행을 로드합니다.
    Reading은 Cloze Exercise만 사용 (긴 지문 문제는 품질 이슈로 임시 제외)
    """
    text=(BASE/"tools"/"generate_personalized_practice.py").read_text(encoding="utf-8")
    tree=ast.parse(text); pools={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in ("MATH_POOL","READING_POOL"):
                pools[node.targets[0].id]=ast.literal_eval(node.value)
    math=[dict(q,subject="Mathematical Reasoning",verified=False) for q in pools.get("MATH_POOL",[])]
    
    # Reading: Cloze Exercise만 필터링 (다른 유형은 지문이 너무 짧아 품질 문제)
    reading_all=pools.get("READING_POOL",[])
    reading=[dict(q,subject="Reading",verified=False) for q in reading_all 
             if "Cloze" in q.get("topic","")]
    
    print(f"[INFO] Question pool loaded: {len(math)} Math, {len(reading)} Reading (Cloze only)")
    if len(reading)<len(reading_all):
        print(f"       Note: {len(reading_all)-len(reading)} non-Cloze Reading questions excluded due to quality concerns.")
    
    return math+reading

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

def make_pdf(path,title,student,test_type,round_no,questions,answer_key=False):
    doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=12*mm,bottomMargin=12*mm,title=title)
    story=[Paragraph(title,styles["PT"]),Paragraph(f"<b>Student:</b> {student} &nbsp;&nbsp; <b>Source:</b> {LABELS[test_type]} — Round {round_no}",styles["PS"]),Spacer(1,4*mm)]
    for i,q in enumerate(questions,1):
        if i>1 and i%10==1: story.append(PageBreak())
        if q.get("passage"):
            story.append(Paragraph(str(q["passage"]).replace("\n","<br/>"),styles["PS"])); story.append(Spacer(1,2*mm))
        story.append(Paragraph(f"<b>{i}. {q['stem']}</b> <font color='#718096'>[{q['subject']} · {q['topic']} · {q['difficulty']}]</font>",styles["PQ"]))
        opts=q["options"] if isinstance(q["options"],list) else q["options"].split("|")
        for letter,opt in zip("ABCDE",opts): story.append(Paragraph(f"{letter}) {opt}",styles["PQ"]))
        if answer_key: story.append(Paragraph(f"<font color='#276749'><b>Answer {q['answer']}:</b> {q['explanation']}</font>",styles["PS"]))
        story.append(Spacer(1,2*mm))
    doc.build(story)

def select_questions(areas,count,pool):
    """
    학생 약점 기반으로 문제를 선택합니다.
    중복을 방지하고, pool이 부족하면 경고를 출력합니다.
    """
    selected=[]
    # 각 문제에 고유 ID 부여 (stem + topic 기반 해시)
    for q in pool:
        if "_id" not in q:
            q["_id"]=hash(q.get("stem","")[:100]+str(q.get("topic",""))+str(q.get("subject","")))
    used_ids=set()
    
    # 1단계: 학생 약점에 맞는 문제 우선 선택
    for area in sorted(areas,key=lambda x:(-x["error_rate"],-x["wrong"])):
        wanted=area["topic"].lower(); wanted_subject=area["subject"].lower()
        for q in pool:
            if q["_id"] in used_ids:
                continue  # 이미 사용한 문제 건너뛰기
            topic=q["topic"].lower(); subject=q["subject"].lower()
            if wanted_subject==subject and (wanted==topic or wanted in topic or topic in wanted):
                selected.append(q)
                used_ids.add(q["_id"])
                if len(selected)>=count: return selected[:count]
    
    # 2단계: 아직 사용하지 않은 문제로 채우기
    for q in pool:
        if len(selected)>=count:
            break
        if q["_id"] not in used_ids:
            selected.append(q)
            used_ids.add(q["_id"])
    
    # 3단계: 여전히 부족하면 경고
    if len(selected)<count:
        print(f"[WARNING] Question pool has only {len([q for q in pool if q['_id'] not in used_ids])+len(selected)} unique questions, but {count} requested.")
        print(f"          Generated {len(selected)} unique questions (no duplicates).")
    
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
