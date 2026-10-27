import json
import os
from pypdf import PdfReader

base=r'D:\EKCRPA\test-report-automation\output\OC_R11'
manifest_path=os.path.join(base,'personalised_practice_manifest_R11.json')
with open(manifest_path,encoding='utf-8') as f:
    manifest=json.load(f)
expected={'10_questions_basic_review_set':10,'20_questions_subject_weakness_focus_set':20,'30_questions_15_to_20_minute_mock_practice_set':30}
bad=[]; checked=0
for student,data in manifest['students'].items():
    student_folder=os.path.join(base,'personalised_practice_'+student.replace(' ','_'))
    for set_name,expected_count in expected.items():
        folder=os.path.join(student_folder,set_name)
        checked+=1
        if not os.path.isdir(folder):
            bad.append((student,set_name,'folder missing')); continue
        json_path=os.path.join(folder,'questions.json')
        if not os.path.isfile(json_path):
            bad.append((student,set_name,'questions.json missing')); continue
        with open(json_path,encoding='utf-8') as f:
            payload=json.load(f)
        questions=payload.get('questions',[])
        if len(questions)!=expected_count:
            bad.append((student,set_name,'json count',len(questions),expected_count))
        for filename in ('student_practice.pdf','teacher_answer_key.pdf'):
            pdf_path=os.path.join(folder,filename)
            if not os.path.isfile(pdf_path):
                bad.append((student,set_name,filename,'missing')); continue
            try:
                reader=PdfReader(pdf_path)
                if len(reader.pages)==0:
                    bad.append((student,set_name,filename,'no pages'))
            except Exception as exc:
                bad.append((student,set_name,filename,str(exc)))
print(json.dumps({'students':len(manifest['students']),'checked_sets':checked,'bad_count':len(bad),'bad':bad},ensure_ascii=False,indent=2))
