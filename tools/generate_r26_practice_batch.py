#!/usr/bin/env python3
import json, runpy
from pathlib import Path
from collections import defaultdict
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

BASE=Path(r"D:\EKCRPA\test-report-automation")
R26=BASE/"output"/"Selective_R26"
REPORTS=BASE/"output"/"parsed_reports_v2.json"
BASE_SCRIPT=BASE/"tools"/"generate_personalized_practice.py"
NS={}
exec(BASE_SCRIPT.read_text(encoding="utf-8").split("# Add five original Reading items")[0], NS)
MATH=NS["MATH_POOL"]
READING=NS["READING_POOL"]

NAMES={
"10_questions_basic_review_set":"10 Questions — Basic Review Set",
"20_questions_subject_weakness_focus_set":"20 Questions — Subject Weakness Focus Set",
"30_questions_15_to_20_minute_mock_practice_set":"30 Questions — 15 to 20 Minute Mock Practice Set"}
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleX",parent=styles["Title"],alignment=TA_CENTER,textColor=colors.HexColor("#1a365d"),fontSize=17,spaceAfter=9))
styles.add(ParagraphStyle(name="QuestionX",parent=styles["Normal"],fontSize=9.5,leading=12.5,spaceAfter=3))
styles.add(ParagraphStyle(name="SmallX",parent=styles["Normal"],fontSize=8,leading=10.5))

def make_pdf(path,title,student,questions,answer_key=False):
    doc=SimpleDocTemplate(str(path),pagesize=A4,leftMargin=15*mm,rightMargin=15*mm,topMargin=12*mm,bottomMargin=12*mm,title=title)
    story=[Paragraph(title,styles["TitleX"]),Paragraph(f"<b>Student:</b> {student} &nbsp;&nbsp; <b>Source:</b> Selective Trial Test Round 26",styles["SmallX"]),Spacer(1,4*mm)]
    for i,q in enumerate(questions,1):
        if i>1 and i%10==1: story.append(PageBreak())
        if q.get("passage"): story.append(Paragraph(str(q["passage"]).replace("\n","<br/>"),styles["SmallX"])); story.append(Spacer(1,2*mm))
        story.append(Paragraph(f"<b>{i}. {q['stem']}</b> <font color='#718096'>[{q['subject']} · {q['topic']} · {q['difficulty']}]</font>",styles["QuestionX"]))
        opts=q["options"] if isinstance(q["options"],list) else q["options"].split("|")
        for letter,opt in zip("ABCDE",opts): story.append(Paragraph(f"{letter}) {opt}",styles["QuestionX"]))
        if answer_key: story.append(Paragraph(f"<font color='#276749'><b>Answer {q['answer']}:</b> {q['explanation']}</font>",styles["SmallX"]))
        story.append(Spacer(1,2*mm))
    doc.build(story)


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
        subject_name=subject.get("name_raw","Unknown")
        for topic,wrong,total,rate in items[:5]: result.append({"subject":subject_name,"topic":topic,"wrong":wrong,"total":total,"error_rate":rate})
    return result

def pool():
    mp={}; rp={}
    for q in MATH: mp.setdefault(q["topic"],[]).append(dict(q,subject="Mathematical Reasoning"))
    for q in READING: rp.setdefault(q["topic"],[]).append(dict(q,subject="Reading"))
    return mp,rp

def select(areas,count):
    mp,rp=pool(); selected=[]
    for a in areas:
        source=mp if "Mathematical" in a["subject"] else rp
        for q in source.get(a["topic"],[]):
            if q not in selected: selected.append(q)
    fallback=[dict(q,subject="Mathematical Reasoning") for q in MATH]+[dict(q,subject="Reading") for q in READING]
    while len(selected)<count: selected.append(dict(fallback[len(selected)%len(fallback)]))
    return selected[:count]

rows=json.loads(REPORTS.read_text(encoding="utf-8"))
round26=[r for r in rows if r.get("test_type")=="Selective" and r.get("test_round")==26]
manifest={"round":26,"generated_at":"2026-10-26","students":{},"note":"Weak-area practice generated from R26 reports. Original sample questions; teacher review required."}

for report in sorted(round26,key=lambda r:r.get("student_name","")):
    student=str(report.get("student_name","")).strip()
    if not student or student=="Aanya Surve": continue
    out=R26/("personalised_practice_"+student.replace(" ","_"))
    out.mkdir(parents=True,exist_ok=True)
    areas=weak_areas(report)
    sets={"10_questions_basic_review_set":select(areas,10),"20_questions_subject_weakness_focus_set":select(areas,20),"30_questions_15_to_20_minute_mock_practice_set":select(areas,30)}
    sm={"student":student,"student_id":report.get("student_id"),"source":"Selective_R26","key_areas":areas,"sets":{}}
    for name,questions in sets.items():
        folder=out/name; folder.mkdir(parents=True,exist_ok=True)
        payload={"student":student,"student_id":report.get("student_id"),"key_areas":areas,"questions":[dict(q,number=i) for i,q in enumerate(questions,1)]}
        (folder/"questions.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        title=f"{student} — {NAMES[name]}"
        make_pdf(folder/"student_practice.pdf",title,student,questions,False)
        make_pdf(folder/"teacher_answer_key.pdf",title+" — Teacher Answer Key",student,questions,True)
        sm["sets"][name]={"question_count":len(questions),"student_pdf":"student_practice.pdf","teacher_pdf":"teacher_answer_key.pdf","json_file":"questions.json"}
    (out/"manifest.json").write_text(json.dumps(sm,ensure_ascii=False,indent=2),encoding="utf-8")
    manifest["students"][student]=sm

(R26/"personalised_practice_manifest_R26.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"students_generated":len(manifest["students"]),"student_names":sorted(manifest["students"])},ensure_ascii=False,indent=2))
