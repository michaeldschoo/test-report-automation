import json, os
from pypdf import PdfReader
root=r'D:\EKCRPA\test-report-automation\output'
cases=[('OC_R11','personalised_practice_manifest_R11.json'),('Selective_R26','personalised_practice_manifest_R26.json')]
bad=[]; student_total=0; set_total=0
for folder,manifest_name in cases:
    base=os.path.join(root,folder)
    with open(os.path.join(base,manifest_name),encoding='utf-8') as f: manifest=json.load(f)
    student_total+=len(manifest['students'])
    for student,data in manifest['students'].items():
        sf=os.path.join(base,'personalised_practice_'+student.replace(' ','_'))
        for set_name,expected in data['sets'].items():
            set_total+=1; d=os.path.join(sf,set_name)
            jp=os.path.join(d,'questions.json')
            if not os.path.isfile(jp): bad.append((student,set_name,'json missing')); continue
            with open(jp,encoding='utf-8') as f: questions=json.load(f)['questions']
            if len(questions)!=expected['question_count']:
                bad.append((student,set_name,'count mismatch',len(questions),expected['question_count']))
            for filename in ('student_practice.pdf','teacher_answer_key.pdf'):
                pdf=os.path.join(d,filename)
                if not os.path.isfile(pdf): bad.append((student,set_name,filename+' missing')); continue
                try:
                    if len(PdfReader(pdf).pages)==0: bad.append((student,set_name,filename+' no pages'))
                except Exception as exc: bad.append((student,set_name,filename,str(exc)))
print(json.dumps({'student_total':student_total,'set_total':set_total,'bad_count':len(bad),'bad':bad[:20]},ensure_ascii=False,indent=2))
