import json
import os
from pypdf import PdfReader

base=r'D:\EKCRPA\test-report-automation\output\Selective_R26'
manifest_path=os.path.join(base,'personalised_practice_manifest_R26.json')
manifest=json.load(open(manifest_path,encoding='utf-8'))
bad=[]
set_count=0
for student,data in manifest['students'].items():
    student_folder=os.path.join(base,'personalised_practice_'+student.replace(' ','_'))
    for set_name,expected in data['sets'].items():
        set_count+=1
        folder=os.path.join(student_folder,set_name)
        json_path=os.path.join(folder,'questions.json')
        questions=json.load(open(json_path,encoding='utf-8'))['questions']
        if len(questions)!=expected['question_count']:
            bad.append((student,set_name,'json count',len(questions),expected['question_count']))
        for filename in ('student_practice.pdf','teacher_answer_key.pdf'):
            pdf_path=os.path.join(folder,filename)
            try:
                PdfReader(pdf_path)
            except Exception as exc:
                bad.append((student,set_name,filename,str(exc)))
print(json.dumps({'students':len(manifest['students']),'sets':set_count,'bad_count':len(bad),'bad':bad[:20]},ensure_ascii=False,indent=2))
