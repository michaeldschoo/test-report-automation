#!/usr/bin/env python3
"""Create Aanya Surve's personalised R26 practice samples."""
import json
from pathlib import Path
from datetime import date
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

BASE = Path(r"D:\EKCRPA\test-report-automation")
OUT = BASE / "output" / "Selective_R26" / "personalised_practice_Aanya_Surve"
OUT.mkdir(parents=True, exist_ok=True)
STUDENT, TEST = "Aanya Surve", "Selective Trial Test — Round 26"
BLUE, GREEN = colors.HexColor("#1a365d"), colors.HexColor("#276749")
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="PracticeTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=BLUE, fontSize=18, spaceAfter=10))
styles.add(ParagraphStyle(name="Question", parent=styles["Normal"], fontSize=10, leading=13, spaceAfter=4))
styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8.5, leading=11))

MATH_POOL = [
 {"topic":"Mass","difficulty":"Medium","stem":"A box has mass 2.4 kg. After 650 g is removed, what mass remains?","options":"1.75 kg|1.85 kg|1.95 kg|2.25 kg|2.15 kg","answer":"A","explanation":"650 g = 0.650 kg; 2.4 − 0.650 = 1.75 kg."},
 {"topic":"Mass","difficulty":"Medium","stem":"Three bags weigh 850 g, 1.2 kg and 950 g. What is their total mass in kilograms?","options":"2.0 kg|2.8 kg|3.0 kg|3.2 kg|3.5 kg","answer":"C","explanation":"850 g + 950 g = 1.8 kg; plus 1.2 kg = 3.0 kg."},
 {"topic":"Addition","difficulty":"Medium","stem":"Mia has 1,287 points. She gains 946, then 385 more. How many points does she have now?","options":"2,618|2,628|2,508|2,718|2,808","answer":"A","explanation":"1287 + 946 = 2233; 2233 + 385 = 2618."},
 {"topic":"Addition","difficulty":"Hard","stem":"Find the next number: 12, 24, 48, 96, ____.","options":"144|192|182|204|168","answer":"B","explanation":"Each number doubles; 96 × 2 = 192."},
 {"topic":"Speed and Time","difficulty":"Medium","stem":"A bus travels 180 km at 60 km/h, plus a 15-minute stop. How long is the whole trip?","options":"3 h 15 min|3 h 30 min|3 h 45 min|4 h|2 h 45 min","answer":"A","explanation":"180 ÷ 60 = 3 hours; plus 15 minutes."},
 {"topic":"Speed and Time","difficulty":"Hard","stem":"Leo begins at 08:35 and travels for 55 minutes. What time does he arrive?","options":"09:20|09:25|09:30|09:35|09:40","answer":"C","explanation":"08:35 + 55 minutes = 09:30."},
 {"topic":"Combination","difficulty":"Medium","stem":"A café offers 3 sandwiches and 4 drinks. How many different pairs are possible?","options":"7|8|12|14|16","answer":"C","explanation":"The multiplication principle gives 3 × 4 = 12."},
 {"topic":"Combination","difficulty":"Medium","stem":"A three-digit code uses 1, 2 or 3 once each. How many codes are possible?","options":"3|6|9|12|27","answer":"B","explanation":"3 × 2 × 1 = 6."},
 {"topic":"Combination","difficulty":"Hard","stem":"Four students form a team of two. How many different teams are possible?","options":"4|6|8|12|16","answer":"B","explanation":"AB, AC, AD, BC, BD, CD = 6 teams."},
 {"topic":"Mass","difficulty":"Hard","stem":"How many whole 750 g flour packets are needed for 3.2 kg?","options":"4|5|6|7|8","answer":"B","explanation":"3200 ÷ 750 leaves remainder 200 g, so 5 packets are needed."},
 {"topic":"Speed and Time","difficulty":"Medium","stem":"A train averages 75 km/h for 2 hours 20 minutes. How far does it travel?","options":"145 km|150 km|175 km|180 km|195 km","answer":"C","explanation":"2⅓ hours × 75 = 175 km."},
 {"topic":"Addition","difficulty":"Medium","stem":"A library borrowed 5,640 books this month and 4,275 last month. How many more were borrowed this month?","options":"1,365|1,375|1,465|1,475|1,355","answer":"A","explanation":"5640 − 4275 = 1365."},
 {"topic":"Combination","difficulty":"Hard","stem":"Five books are placed in a row. In how many orders could they be arranged?","options":"10|25|60|120|125","answer":"D","explanation":"5 × 4 × 3 × 2 × 1 = 120."},
 {"topic":"Mass","difficulty":"Medium","stem":"A recipe needs 375 g rice, 125 g peas and 50 g herbs. What is the total mass?","options":"450 g|500 g|550 g|600 g|625 g","answer":"C","explanation":"375 + 125 + 50 = 550 g."},
 {"topic":"Speed and Time","difficulty":"Hard","stem":"A cyclist rides 36 km in 1 hour 30 minutes. What is the average speed?","options":"18 km/h|24 km/h|27 km/h|30 km/h|36 km/h","answer":"B","explanation":"36 ÷ 1.5 = 24 km/h."}
]

READING_POOL = [
 {"topic":"Paired Comprehension","difficulty":"Medium","passage":"Text A: A community garden opened beside the library, where residents borrow tools and grow herbs. Text B: The garden changed the courtyard, but some visitors complain that watering creates muddy paths.","stem":"Which statement combines both texts?","options":"The garden has no benefits.|Residents gain shared gardening space, although the paths may become muddy.|The library only lends books.|Mud makes all visitors leave.|No tools are available.","answer":"B","explanation":"Text A gives the benefit; Text B adds a possible disadvantage."},
 {"topic":"Cloze Passage","difficulty":"Medium","passage":"The astronomer checked the telescope twice. Clouds had ______ the stars, but one bright planet appeared near the horizon.","stem":"Choose the best word for the blank.","options":"revealed|hidden|measured|followed|counted","answer":"B","explanation":"Clouds cover or hide stars."},
 {"topic":"Linked Extracts","difficulty":"Hard","passage":"First extract: The guide warned the hikers that the bridge was closed. Second extract: By noon, the group had reached the river and was debating whether to turn back.","stem":"Which conclusion is best supported?","options":"The hikers ignored all warnings.|The group was aware of a crossing problem.|It began raining at noon.|The bridge had reopened.|The guide joined the hike.","answer":"B","explanation":"The warning and later debate are linked by the closed bridge."},
 {"topic":"Paired Comprehension","difficulty":"Hard","passage":"Museum report: Attendance rose 12% after late-night opening. Survey: Many visitors said evening hours fitted difficult daytime schedules.","stem":"Why might attendance have risen?","options":"The museum moved.|Tickets became cheaper.|Evening opening suited more visitors.|School groups stopped visiting.|The museum closed earlier.","answer":"C","explanation":"Evening availability is the reason suggested by the survey."},
 {"topic":"Poetry","difficulty":"Medium","passage":"Soft rain taps the sleeping roof,\nA silver rhythm, note by note;\nThe garden drinks beneath the stars,\nWhile moonlight guides the night bird's flight.","stem":"What mood does the poem mainly create?","options":"Angry and noisy|Quiet and peaceful|Dangerous and fearful|Busy and excited|Cold and lonely","answer":"B","explanation":"Soft rain, silver rhythm and moonlight create a peaceful mood."},
 {"topic":"Cloze Exercise","difficulty":"Medium","passage":"Nora practiced violin every evening. At the concert, her careful preparation helped her perform with ______.","stem":"Choose the most suitable word.","options":"confusion|confidence|delay|nervousness|carelessness","answer":"B","explanation":"Regular practice would naturally lead to confidence."},
 {"topic":"Linked Extracts","difficulty":"Medium","passage":"Extract one describes a growing queue outside the science centre. Extract two says staff admitted that an interactive display was unexpectedly popular.","stem":"Which explanation is supported by both extracts?","options":"The queue was outside a café.|Interest in the display caused the queue.|Staff cancelled the display.|No visitors arrived.|The centre had closed.","answer":"B","explanation":"The display's popularity directly explains the growing queue."},
 {"topic":"Poetry","difficulty":"Hard","passage":"We chase the sun across the hill,\nIt races us, but never runs;\nThen slips behind the blue-grey dusk—\nA lamp extinguished, one by one.","stem":"Which technique is clearly used in the final line?","options":"Dialogue|Imagery and metaphor|Alliteration only|Statistics|Rhyme reversal","answer":"B","explanation":"The sunset becomes a lamp, using visual imagery and metaphor."},
 {"topic":"Cloze Passage","difficulty":"Hard","passage":"Although the instructions were lengthy, Leila read them ______ and avoided making an expensive mistake.","stem":"Choose the word that best fits.","options":"carelessly|slowly|carefully|briefly|angrily","answer":"C","explanation":"Avoiding a mistake suggests careful reading."},
 {"topic":"Paired Comprehension","difficulty":"Medium","passage":"Text one: Digital maps can update road closures immediately. Text two: Paper maps work without batteries but cannot display sudden changes.","stem":"What advantage do paper maps retain?","options":"Battery updates|No need for electricity|Faster road changes|Automatic routes|Live traffic","answer":"B","explanation":"Paper maps do not require batteries or an electronic device."}
]

# Add five original Reading items so the 30-question sample is balanced.
READING_POOL += [
 {"topic":"Cloze Exercise","difficulty":"Hard","passage":"The detective noticed a footprint beneath the window, a clue that the missing necklace had not been lost but ______.","stem":"Choose the best ending word.","options":"returned|misplaced|stolen|donated|displayed","answer":"C","explanation":"A footprint beside the missing necklace suggests theft."},
 {"topic":"Linked Extracts","difficulty":"Hard","passage":"Extract A states that shop sales fell during heavy rain. Extract B reports that online orders rose on the same dates.","stem":"Which conclusion is best supported?","options":"Online shoppers disliked weather.|Weather affected one sales channel more than the other.|All shops closed permanently.|The rain happened in summer.|No customers used phones.","answer":"B","explanation":"The contrasting results suggest different effects on shop and online sales."},
 {"topic":"Poetry","difficulty":"Medium","passage":"Under bridges, beneath old stone,\nA river carries seeds downstream;\nEach twist and turn carries life onward—\nA moving road for dreams unseen.","stem":"The river is mainly symbolising what?","options":"Movement and progress|Danger and fear|Division and conflict|Stillness and silence|Construction","answer":"A","explanation":"The river carries seeds and life onward, symbolising progress."},
 {"topic":"Cloze Passage","difficulty":"Medium","passage":"The coach substituted two players after repeated mistakes. Under new positions, the team immediately looked more ______.","stem":"Choose the best word.","options":"organised|distant|careless|silent|exhausted","answer":"A","explanation":"Changing positions should improve organisation and reduce errors."},
 {"topic":"Paired Comprehension","difficulty":"Hard","passage":"Passage one says lockers reduce backpacks being carried between rooms. Passage two says students leave belongings behind because lockers are outdoors.","stem":"What issue is introduced by the second passage?","options":"The lockers are too heavy.|Outdoor placement may cause students to forget belongings.|Backpacks are banned.|Students dislike every feature.|The lockers are indoors.","answer":"B","explanation":"The outdoor location creates a risk of forgetting belongings."}
]

def make_pdf(path, title, questions, answer_key=False):
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=15*mm, leftMargin=15*mm,
                            topMargin=12*mm, bottomMargin=12*mm, title=title,
                            author="Edu-Kingdom College")
    story = [Paragraph(title, styles["PracticeTitle"]),
             Paragraph(f"<b>Student:</b> {STUDENT} &nbsp;&nbsp; <b>Source report:</b> {TEST}", styles["Small"]),
             Spacer(1, 4*mm)]
    for i, q in enumerate(questions, 1):
        if i > 1 and i % 10 == 1:
            story.append(PageBreak())
        if q.get("passage"):
            story.append(Paragraph(q["passage"].replace("\n", "<br/>"), styles["Small"]))
            story.append(Spacer(1, 2*mm))
        story.append(Paragraph(f"<b>{i}. {q['stem']}</b>  <font color='#718096'>[{q['subject']} · {q['topic']} · {q['difficulty']}]</font>", styles["Question"]))
        for letter, option in zip("ABCDE", q["options"].split("|")):
            story.append(Paragraph(f"{letter}) {option}", styles["Question"]))
        if answer_key:
            story.append(Paragraph(f"<font color='#276749'><b>Answer: {q['answer']}</b> — {q['explanation']}</font>", styles["Small"]))
        story.append(Spacer(1, 2*mm))
    doc.build(story)

# Add subjects and stable source metadata.
for q in MATH_POOL:
    q.update(subject="Mathematical Reasoning", source="original sample — no reused exam item", verified=False)
for q in READING_POOL:
    q.update(subject="Reading", source="original sample — no reused exam item", verified=False)

sets = {"10_questions_basic_review_set": MATH_POOL[:5] + READING_POOL[:5],
        "20_questions_subject_weakness_focus_set": MATH_POOL[:10] + READING_POOL[:10],
        "30_questions_15_to_20_minute_mock_practice_set": MATH_POOL[:] + READING_POOL[:]}

manifest = {"student":"Aanya Surve","student_id":"43031","source_report":"Selective26_Aanya_Surve_Progress_Report.pdf","test":"Selective Trial Test — Round 26","report_date":"2026-10-26","copyright_status":"Original practice questions; not copied from an exam or publication","teacher_review_required":True,"generated_at":"2026-10-26","sets":{}}

for name, questions in sets.items():
    base = OUT / name
    base.mkdir(parents=True, exist_ok=True)
    title = f"Aanya Surve — {name.replace('_',' ').title()}"
    questions_file = base / "questions.json"
    with questions_file.open("w", encoding="utf-8") as f:
        json.dump({"student":"Aanya Surve","student_id":"43031","questions":[dict(q, number=i) for i,q in enumerate(questions,1)]}, f, ensure_ascii=False, indent=2)
    make_pdf(base / "student_practice.pdf", title, questions, answer_key=False)
    make_pdf(base / "teacher_answer_key.pdf", title + " — Teacher Answer Key", questions, answer_key=True)
    manifest["sets"][name] = {"question_count":len(questions),"json_file":"questions.json","student_pdf":"student_practice.pdf","teacher_pdf":"teacher_answer_key.pdf"}

with (OUT / "manifest.json").open("w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print(json.dumps(manifest, ensure_ascii=False, indent=2))


