import json
from collections import defaultdict
p=r'D:\EKCRPA\test-report-automation\output\parsed_reports_v2.json'
d=json.load(open(p,encoding='utf-8'))
rows=[x for x in d if x.get('test_type')=='OC' and x.get('test_round')==11]
for r in sorted(rows,key=lambda x:x.get('student_name','')):
    print(r.get('student_name'),r.get('student_id'))
    for s in r.get('subjects',[]):
        c=defaultdict(lambda:[0,0])
        for q in s.get('questions',[]):
            t=str(q.get('topic','')).strip()
            if t:
                c[t][1]+=1
                c[t][0]+=int(not q.get('correct',True))
        ws=sorted([(t,v[0],v[1],round(v[0]/v[1]*100,1)) for t,v in c.items() if v[0]>0],key=lambda x:(-x[3],-x[1],x[0]))[:5]
        print(' ',s.get('name_raw'),ws)
