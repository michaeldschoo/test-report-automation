#!/usr/bin/env python3
"""
Edu-Kingdom College — Test Report Automation Pipeline
=======================================================
J: 드라이브의 시험 결과 PDF를 파싱하고, 질문 은행을 생성하고,
학생별 영문 분석 보고서 PDF를 생성하는 전체 파이프라인입니다.

사용법:
    python run_pipeline.py                     # 전체 파이프라인 실행 (기본)
    python run_pipeline.py --test-type OC      # OC 시험만 처리
    python run_pipeline.py --test-type Selective  # Selective만
    python run_pipeline.py --dry-run           # 실제 PDF 생성 없이 절차만 확인
    python run_pipeline.py --no-parse          # 파싱 생략, 기존 JSON 재사용
    python run_pipeline.py --no-bank           # 질문 은행 생성 생략, 기존 JSON 재사용
    python run_pipeline.py --no-reports        # PDF 생성 생략, 데이터만 생성

필요 조건:
    - J: 드라이브가 Windows에 마운트되어 있어야 함 (Google Drive for Desktop)
    - Python 3.8+ 
    - pypdf: pip install pypdf
    - reportlab: pip install reportlab

출력 파일 (output/ 디렉토리):
    - parsed_reports_v2.json        : 파싱된 시험 결과 데이터
    - question_bank_by_type.json    : 시험 유형별 질문 은행
    - <시험폴더>/<학생>_Progress_Report.pdf : 학생별 보고서
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

# ===== 경로 설정 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
J_DRIVE_BASE = r"J:\My Drive\EKC  OFFICE"

REPORTS_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
PARSED_JSON = os.path.join(REPORTS_OUTPUT_DIR, "parsed_reports_v2.json")
BANK_JSON = os.path.join(REPORTS_OUTPUT_DIR, "question_bank_by_type.json")


# ============================================================
# 1단계: PDF 파싱
# ============================================================

def detect_test_type_and_round(filename):
    """파일명에서 시험 유형과 차수 추출"""
    # OC: "OC01 Apson.pdf", "OC16 Aanya.pdf"
    m = re.search(r'^OC(\d+)\s', filename)
    if m:
        return 'OC', int(m.group(1))
    
    # Selective: "STT10 Adrio.pdf", "STT20 Zavian.pdf"
    m = re.search(r'^STT(\d+)\s', filename)
    if m:
        return 'Selective', int(m.group(1))
    
    # TermTest: "Apson Y3 T5.pdf" → 학생명 Y학년 T차수
    m = re.search(r'^(.+?)\s+Y(\d+)\s+T(\d+)', filename)
    if m:
        return 'TermTest', int(m.group(3))
    
    return 'Unknown', None


def detect_student_name(filename):
    """파일명에서 학생명 추출 (파서 결과를 우선 신뢰)"""
    # OC/Selective 패턴
    m = re.search(r'^(?:OC\d+\s+|STT\d+\s+)(.+?)\.pdf$', filename)
    if m:
        return m.group(1).strip()
    # TermTest 패턴
    m = re.search(r'^(.+?)\s+Y\d+\s+T\d+\.pdf$', filename)
    if m:
        return m.group(1).strip()
    return None


def parse_question_line(line):
    """문항 데이터 라인 파싱: '1 D O D 62.6% Narrative' 또는 '1 D X B 62.6% Narrative'"""
    stripped = line.strip()
    if not stripped:
        return None
    
    parts = stripped.split()
    if not parts or not parts[0].isdigit():
        return None
    
    qn = int(parts[0])
    if qn < 1 or qn > 100:
        return None
    
    symbol = None
    resp = None
    ans = None
    pct = 0.0
    topic = ''
    
    # 표준 형식: parts[0]=qn, [1]=resp, [2]=O/X, [3]=ans, [4]=pct%, [5:]=topic
    if len(parts) >= 5 and parts[2] in ('O', 'X'):
        resp = parts[1]
        symbol = parts[2]
        ans = parts[3]
        try:
            pct = float(parts[4].replace('%', '').replace(',', ''))
        except ValueError:
            pct = 0.0
        topic = ' '.join(parts[5:]) if len(parts) > 5 else ''
    # Thinking Skills 미응답 형식: parts[0]=qn, [1]=O/X, [2]=ans, [3]=pct%, [4:]=topic
    elif len(parts) >= 4 and parts[1] in ('O', 'X'):
        symbol = parts[1]
        ans = parts[2]
        try:
            pct = float(parts[3].replace('%', '').replace(',', ''))
        except ValueError:
            pct = 0.0
        topic = ' '.join(parts[4:]) if len(parts) > 4 else ''
    else:
        return None
    
    topic = re.sub(r'\s+', ' ', topic).strip()
    
    return {
        'qn': qn,
        'resp': resp,
        'symbol': symbol,
        'ans': ans,
        'pct': pct,
        'topic': topic if topic else '(미지정)',
        'correct': symbol == 'O',
    }


def parse_page(page):
    """한 페이지의 텍스트를 파싱하여 과목 데이터 추출"""
    text = page.extract_text()
    if not text:
        return None
    
    lines = text.split('\n')
    subject = {}
    questions = []
    in_questions = False
    
    for line in lines:
        s = line.strip()
        if s.startswith('Subject:'):
            subject['name_raw'] = s.replace('Subject:', '').strip()
            in_questions = False
        elif s.startswith('Percentage Scores:'):
            try:
                subject['score'] = float(s.replace('Percentage Scores:', '').replace('%', '').strip())
            except ValueError:
                pass
        elif s.startswith('Rank:'):
            m = re.search(r'top\s+(\d+\.?\d*)%', s)
            subject['rank_pct'] = float(m.group(1)) if m else None
        elif s.startswith('Qn'):
            in_questions = True
            continue
        elif in_questions and s:
            q = parse_question_line(s)
            if q:
                questions.append(q)
    
    if not questions:
        return None
    
    subject['questions'] = questions
    subject['total'] = len(questions)
    subject['correct_count'] = sum(1 for q in questions if q['correct'])
    subject['wrong_count'] = sum(1 for q in questions if not q['correct'])
    return subject


def parse_pdf(pdf_path):
    """하나의 결과지 PDF를 파싱하여 구조화된 데이터로 반환"""
    from pypdf import PdfReader
    
    fname = os.path.basename(pdf_path)
    test_type, test_round = detect_test_type_and_round(fname)
    student_name = detect_student_name(fname)
    
    # 파서에서 읽은 학생명을 우선 사용 (파일명보다 신뢰도 높음)
    reader = PdfReader(pdf_path)
    first_text = reader.pages[0].extract_text() if reader.pages else ''
    parsed_name = None
    m = re.search(r'Student Name:\s*(.+?)\s+Student ID:', first_text)
    if m:
        parsed_name = m.group(1).strip()
    
    student_id = None
    m_id = re.search(r'Student ID:\s*(\d+)', first_text)
    if m_id:
        student_id = m_id.group(1).strip()
    
    final_student_name = parsed_name or student_name
    
    subjects = []
    for page in reader.pages:
        s = parse_page(page)
        if s:
            subjects.append(s)
    
    return {
        'filename': fname,
        'filepath': pdf_path,
        'test_type': test_type,
        'test_round': test_round,
        'student_name': final_student_name,
        'student_id': student_id,
        'subjects': subjects,
    }


def scan_result_pdfs(test_type_filter=None):
    """J: 드라이브에서 결과지 PDF를 스캔하고 파싱"""
    print(f"\n{'='*60}")
    print("1단계: 결과지 PDF 스캔 및 파싱")
    print(f"{'='*60}")
    
    if not os.path.exists(J_DRIVE_BASE):
        print(f"오류: J: 드라이브 경로를 찾을 수 없음: {J_DRIVE_BASE}")
        print("  Google Drive for Desktop이 설치되고 J:로 마운트되어 있는지 확인하세요.")
        return None
    
    all_reports = []
    total_pdfs = 0
    
    for root, dirs, files in os.walk(J_DRIVE_BASE):
        for fn in files:
            if not fn.lower().endswith('.pdf'):
                continue
            
            # 시험 유형 필터 적용
            test_type, test_round = detect_test_type_and_round(fn)
            if test_type_filter and test_type != test_type_filter:
                continue
            
            fp = os.path.join(root, fn)
            total_pdfs += 1
            
            try:
                report = parse_pdf(fp)
                all_reports.append(report)
                status = f"R{test_round}" if test_round else "?"
                print(f"  ✓ [{test_type:10s}] {status:>4s} {report['student_name'] or '?':25s} {fn}")
            except Exception as e:
                print(f"  ✗ 파싱 실패: {fn} — {e}")
    
    print(f"\n총 {len(all_reports)}개 결과지 파싱 완료 (스캔: {total_pdfs}개 PDF)")
    
    if not all_reports:
        print("오류: 파싱된 결과지가 없습니다.")
        return None
    
    return all_reports


def save_parsed_reports(reports):
    """파싱된 결과를 JSON으로 저장"""
    os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)
    
    # 통계
    type_stats = defaultdict(lambda: {'reports': 0, 'students': set(), 'rounds': set()})
    for r in reports:
        tt = r.get('test_type', 'Unknown')
        type_stats[tt]['reports'] += 1
        if r.get('student_name'):
            type_stats[tt]['students'].add(r['student_name'])
        if r.get('test_round') is not None:
            type_stats[tt]['rounds'].add(r['test_round'])
    
    with open(PARSED_JSON, 'w', encoding='utf-8') as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    
    print(f"\n파싱 결과 저장: {PARSED_JSON}")
    print("시험 유형별 통계:")
    for tt in sorted(type_stats.keys()):
        s = type_stats[tt]
        rounds = sorted(s['rounds']) if s['rounds'] else []
        print(f"  {tt:12s}: {s['reports']:3d}개, {len(s['students']):2d}명, 차수 {rounds}")
    
    return PARSED_JSON


# ============================================================
# 2단계: 질문 은행 생성
# ============================================================

def norm_topic(t):
    """Topic명 정규화 (변형 통합)"""
    if not t or t == '(미지정)':
        return None
    t = t.strip()
    replacements = [
        ('Problem solving', 'Problem Solving'),
        ('Deductive reasoning', 'Deductive Reasoning'),
        ('Drawing conclusion', 'Drawing Conclusion'),
        ('Assessing the impact of additional', 'Assessing the Impact of Additional Evidence'),
        ('Numerical reasoning', 'Numerical Reasoning'),
        ('Find correct reasoning or', 'Finding Correct Reasoning'),
        ('Detecting Reasoning Error', 'Detecting Reasoning Errors'),
        ('Drawing a Conclusion', 'Drawing Conclusion'),
        ('Find correct reasoning', 'Finding Correct Reasoning'),
        ('Identifying Patterns and\nRelationship', 'Identifying Patterns and Relationship'),
        ('Identifying an Assumption', 'Identifying an Assumption'),
        ('Dialogue reasoning questions', 'Dialogue Reasoning Questions'),
        ('Date calculation', 'Date Calculation'),
        ('Space 3D', 'Space 3D'),
        ('Shape pattern', 'Shape Pattern'),
        ('Evaluative reasoning', 'Evaluative Reasoning'),
        ('Making inferences', 'Making Inferences'),
        ('Letter Patterns', 'Letter Patterns'),
        ('Sentence rearrangement', 'Sentence Rearrangement'),
        ('Subtraction Tower', 'Subtraction Tower'),
        ('Statistics and Probability', 'Statistics and Probability'),
        ('True or False', 'True or False'),
        ('Common saying', 'Common Saying'),
        ('Alphabetical order', 'Alphabetical Order'),
        ('General Knowledge', 'General Knowledge'),
        ('Graph Analysis', 'Graph Analysis'),
        ('Equivalent fraction', 'Equivalent Fraction'),
        ('True Statement', 'True Statement'),
        ('Roman Numeral', 'Roman Numeral'),
        ('Missing Letters', 'Missing Letters'),
        ('Prime number', 'Prime Number'),
        ('Missing number', 'Missing Number'),
        ('Assessing the Impact of Additional', 'Assessing the Impact of Additional Evidence'),
        ('Detecting Reasoning Errorss', 'Detecting Reasoning Errors'),
        ('Drawing Conclusions', 'Drawing Conclusion'),
    ]
    for old, new in replacements:
        t = t.replace(old, new)
    t = t.replace('\n', ' ').strip()
    return t


def build_question_bank(all_reports):
    """파싱된 결과에서 질문 은행 생성"""
    print(f"\n{'='*60}")
    print("2단계: 질문 은행 생성")
    print(f"{'='*60}")
    
    question_stats = defaultdict(lambda: {
        'total_students_seen': 0,
        'correct_count': 0,
        'pct_values': [],
        'students': [],
        'test_types_seen': set(),
    })
    
    for r in all_reports:
        tr = r.get('test_round')
        if tr is None:
            continue
        sn = r.get('student_name')
        if not sn:
            continue
        tt = r.get('test_type', 'Unknown')
        
        for subj in r.get('subjects', []):
            name_raw = subj.get('name_raw', '')
            if 'Reading' in name_raw and 'Mathematical' not in name_raw:
                short = 'Reading'
            elif 'Mathematical Reasoning' in name_raw:
                short = 'Mathematical Reasoning'
            elif 'Thinking Skills' in name_raw:
                short = 'Thinking Skills'
            elif 'Thinking Ability' in name_raw or 'Thinking ability' in name_raw:
                short = 'Thinking Ability'
            elif 'English' in name_raw and 'Reading' not in name_raw and 'Writing' not in name_raw:
                short = 'English'
            elif 'Mathematics' in name_raw:
                short = 'Mathematics'
            else:
                short = name_raw
            
            for q in subj.get('questions', []):
                topic_norm = norm_topic(q.get('topic', ''))
                key = (tr, short, q['qn'], topic_norm)
                st = question_stats[key]
                st['total_students_seen'] += 1
                if q['correct']:
                    st['correct_count'] += 1
                st['pct_values'].append(q['pct'])
                st['students'].append(sn)
                st['test_types_seen'].add(tt)
    
    # 불일치 체크
    inconsistent = 0
    for key, st in question_stats.items():
        if len(set(st['pct_values'])) > 1:
            inconsistent += 1
    
    print(f"문항 키: {len(question_stats)}개, 불일치: {inconsistent}")
    
    # 질문 은행 생성
    def make_bank(filter_types=None):
        bank = []
        for key, st in question_stats.items():
            tr, subject, qn, topic = key
            if not topic:
                continue
            if filter_types:
                if not st['test_types_seen'].intersection(filter_types):
                    continue
                overlap = st['test_types_seen'].intersection(filter_types)
                primary_type = 'Mixed' if len(st['test_types_seen']) > len(overlap) else sorted(overlap)[0]
            else:
                primary_type = 'Mixed' if len(st['test_types_seen']) > 1 else sorted(st['test_types_seen'])[0]
            
            pct_counter = {}
            for p in st['pct_values']:
                pct_counter[p] = pct_counter.get(p, 0) + 1
            most_common_pct = max(pct_counter, key=pct_counter.get) if pct_counter else 0
            
            if most_common_pct >= 80:
                diff = 1
            elif most_common_pct >= 60:
                diff = 2
            elif most_common_pct >= 40:
                diff = 3
            elif most_common_pct >= 20:
                diff = 4
            else:
                diff = 5
            
            acc = round(st['correct_count'] / st['total_students_seen'] * 100, 1) if st['total_students_seen'] > 0 else None
            
            bank.append({
                'round': tr,
                'subject': subject,
                'question_no': qn,
                'topic': topic,
                'overall_pct': round(most_common_pct, 1),
                'difficulty': diff,
                'observed_students': st['total_students_seen'],
                'observed_correct': st['correct_count'],
                'student_accuracy': acc,
                'test_types': sorted(st['test_types_seen']),
                'test_type_primary': primary_type,
            })
        return bank
    
    bank_oc = make_bank({'OC'})
    bank_selective = make_bank({'Selective'})
    bank_termtest = make_bank({'TermTest'})
    bank_all = make_bank()
    
    print(f"\n질문 은행:")
    print(f"  OC 전용:     {len(bank_oc)}문항")
    print(f"  Selective 전용: {len(bank_selective)}문항")
    print(f"  TermTest 전용: {len(bank_termtest)}문항")
    print(f"  전체: {len(bank_all)}문항")
    
    bank_data = {
        'generated_at': datetime.now().isoformat(),
        'total_reports': len(all_reports),
        'by_type': {
            tt: {
                'reports': type_stats[tt]['reports'],
                'students': len(type_stats[tt]['students']),
                'rounds': sorted(type_stats[tt]['rounds']),
            }
            for tt in type_stats
        },
        'question_bank': {
            'OC': {'count': len(bank_oc), 'questions': bank_oc},
            'Selective': {'count': len(bank_selective), 'questions': bank_selective},
            'TermTest': {'count': len(bank_termtest), 'questions': bank_termtest},
            'All': {'count': len(bank_all), 'questions': bank_all},
        }
    }
    
    with open(BANK_JSON, 'w', encoding='utf-8') as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n질문 은행 저장: {BANK_JSON}")
    return bank_data


# ============================================================
# 3단계: 학생별 보고서 PDF 생성
# ============================================================

def get_subject_short(name_raw):
    """과목명을 짧은 표준명으로"""
    if 'Reading' in name_raw and 'Mathematical' not in name_raw:
        return 'Reading'
    if 'Mathematical Reasoning' in name_raw:
        return 'Mathematical Reasoning'
    if 'Thinking Skills' in name_raw:
        return 'Thinking Skills'
    if 'Thinking Ability' in name_raw or 'Thinking ability' in name_raw:
        return 'Thinking Ability'
    if 'English' in name_raw and 'Reading' not in name_raw and 'Writing' not in name_raw:
        return 'English'
    if 'Mathematics' in name_raw:
        return 'Mathematics'
    return name_raw


def find_weak_topics(subject_data, top_n=5):
    """약점 Topic Top N"""
    topics = subject_data['topic_stats']
    weak = []
    for t, ts in topics.items():
        if ts['total'] > 0 and ts['wrong'] > 0:
            wr = ts['wrong'] / ts['total'] * 100
            weak.append({
                'topic': t,
                'wrong': ts['wrong'],
                'total': ts['total'],
                'wrong_rate': round(wr, 1),
                'avg_pct': ts.get('avg_pct'),
            })
    weak.sort(key=lambda x: -x['wrong_rate'])
    return weak[:top_n]


def recommend_for_topic(topic, subject, bank, max_n=2):
    """Topic별 보강 문제 추천"""
    candidates = [q for q in bank
                  if q.get('topic') == topic
                  and q.get('subject') == subject]
    candidates.sort(key=lambda x: x.get('difficulty', 99))
    return candidates[:max_n]


def build_report_data(sn, test_type, target_round, bank, all_reports, student_history):
    """학생별 보고서 데이터 생성"""
    test_rounds = student_history.get(sn, {}).get(test_type, [])
    latest = [r for r in test_rounds if r['round'] == target_round]
    if not latest:
        return None
    latest = latest[0]
    
    other_types = {}
    for tt, rounds in student_history.get(sn, {}).items():
        if tt != test_type:
            other_types[tt] = [r['round'] for r in rounds]
    
    subject_analysis = {}
    for subj in sorted(latest['subjects'].keys()):
        s = latest['subjects'][subj]
        
        past_scores = []
        for r in test_rounds:
            if r['round'] != target_round and subj in r['subjects']:
                past_scores.append((r['round'], r['subjects'][subj]['score']))
        
        trend = None
        if past_scores:
            first_score = past_scores[0][1]
            change = round(s['score'] - first_score, 1)
            trend = {
                'first_round': past_scores[0][0],
                'first_score': first_score,
                'latest_score': s['score'],
                'change': change,
                'direction': 'improved' if change > 0 else ('declined' if change < 0 else 'stable'),
            }
        
        weak_topics = find_weak_topics(s, top_n=5)
        recommendations = []
        bank_for_type = bank.get(test_type, {}).get('questions', [])
        for wt in weak_topics[:3]:
            recs = recommend_for_topic(wt['topic'], subj, bank_for_type, max_n=2)
            if recs:
                recommendations.append({
                    'topic': wt['topic'],
                    'wrong': wt['wrong'],
                    'total': wt['total'],
                    'wrong_rate': wt['wrong_rate'],
                    'avg_pct': wt['avg_pct'],
                    'recommended': [{
                        'round': r.get('round'),
                        'question_no': r.get('question_no'),
                        'difficulty': r.get('difficulty'),
                        'overall_pct': r.get('overall_pct'),
                    } for r in recs]
                })
        
        subject_analysis[subj] = {
            'score': s['score'],
            'rank_pct': s['rank_pct'],
            'total': s['total'],
            'correct': s['correct'],
            'wrong': s['wrong'],
            'trend': trend,
            'weak_topics': weak_topics,
            'recommendations': recommendations,
        }
    
    scores = {subj: data['score'] for subj, data in subject_analysis.items()}
    avg_score = round(sum(scores.values()) / len(scores), 1) if scores else 0
    weakest_subject = min(scores, key=scores.get) if scores else None
    strongest_subject = max(scores, key=scores.get) if scores else None
    
    return {
        'student_name': sn,
        'test_type': test_type,
        'latest_round': target_round,
        'latest_filename': latest.get('filename', ''),
        'student_id': latest.get('student_id'),
        'other_test_types': other_types,
        'subjects': subject_analysis,
        'average_score': avg_score,
        'weakest_subject': weakest_subject,
        'strongest_subject': strongest_subject,
        'generated_at': datetime.now().isoformat(),
    }


# ===== PDF 생성 함수 (reportlab) =====
def generate_pdf(rpt, output_path):
    """학생별 보고서 PDF 생성"""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title2', parent=styles['Title'],
        fontSize=18, textColor=colors.HexColor('#1a365d'), spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=12)
    heading_style = ParagraphStyle('Heading2', parent=styles['Heading2'],
        fontSize=13, textColor=colors.HexColor('#2c5282'), spaceBefore=10, spaceAfter=4)
    subheading_style = ParagraphStyle('Subheading', parent=styles['Heading3'],
        fontSize=11, textColor=colors.HexColor('#2d3748'), spaceBefore=6, spaceAfter=2)
    normal_style = ParagraphStyle('Normal2', parent=styles['Normal'],
        fontSize=10, leading=14, spaceAfter=2)
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#4a5568'), leading=12)
    
    DARK_BLUE = colors.HexColor('#1a365d')
    MED_BLUE = colors.HexColor('#2c5282')
    LIGHT_BLUE = colors.HexColor('#ebf4ff')
    GREEN = colors.HexColor('#276749')
    RED = colors.HexColor('#c53030')
    
    SUBJECT_LABELS = {
        'Reading': 'Reading (English)',
        'Mathematical Reasoning': 'Mathematical Reasoning',
        'Thinking Skills': 'Thinking Skills',
        'Thinking Ability': 'Thinking Ability',
        'English': 'English',
        'Mathematics': 'Mathematics',
    }
    
    doc = SimpleDocTemplate(output_path, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)
    story = []
    today_str = datetime.now().strftime('%B %d, %Y')
    
    # 헤더
    story.append(Paragraph("Edu-Kingdom College Penrith", title_style))
    story.append(Paragraph("Student Progress Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=MED_BLUE, spaceAfter=8))
    
    # 학생 정보
    story.append(Paragraph(f"Student: {rpt['student_name']}", heading_style))
    test_label = 'OC Trial Test' if rpt['test_type'] == 'OC' else 'Selective Trial Test'
    story.append(Paragraph(f"Test: <b>{test_label}</b> — Round {rpt['latest_round']}", normal_style))
    story.append(Paragraph(f"Report Date: {today_str}", normal_style))
    if rpt.get('student_id'):
        story.append(Paragraph(f"Student ID: {rpt['student_id']}", normal_style))
    story.append(Spacer(1, 4*mm))
    
    # 다른 시험 이력
    other = rpt.get('other_test_types', {})
    if other:
        story.append(Paragraph("Student's Other Test History", subheading_style))
        for tt_name, rounds in other.items():
            label = 'OC Trial Test' if tt_name == 'OC' else 'Selective Trial Test'
            rlist = ', '.join(f'R{r}' for r in sorted(rounds))
            story.append(Paragraph(f"• <b>{label}</b>: {rlist}", normal_style))
        story.append(Spacer(1, 3*mm))
    
    # 종합 요약
    story.append(Paragraph("Overall Summary", heading_style))
    avg = rpt['average_score']
    weakest = rpt['weakest_subject']
    strongest = rpt['strongest_subject']
    summary_data = [
        ['Average Across Subjects', f'{avg:.1f}%'],
        ['Strongest Subject', f'{strongest} ({rpt["subjects"][strongest]["score"]:.1f}%)'],
        ['Area Needing Most Attention', f'{weakest} ({rpt["subjects"][weakest]["score"]:.1f}%)'],
    ]
    summary_table = Table(summary_data, colWidths=[70*mm, 80*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_BLUE),
        ('TEXTCOLOR', (0, 0), (0, -1), MED_BLUE),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 4*mm))
    
    # 과목별 상세
    for subj in sorted(rpt['subjects'].keys()):
        data = rpt['subjects'][subj]
        labeled_subj = SUBJECT_LABELS.get(subj, subj)
        
        story.append(Paragraph(f"Subject: {labeled_subj}", heading_style))
        
        score = data['score']
        correct = data['correct']
        total = data['total']
        rank = data['rank_pct']
        score_color = GREEN if score >= 60 else (RED if score < 40 else colors.HexColor('#dd6b20'))
        rank_text = f" — Ranked in the top {rank:.1f}% of all candidates" if rank else ""
        
        story.append(Paragraph(
            f"Score: <font color='#{score_color.hexval()[2:]}'><b>{score:.1f}%</b></font> "
            f"({correct}/{total} correct){rank_text}", normal_style))
        
        if data['trend']:
            t = data['trend']
            arrow = "▲" if t['change'] > 0 else ("▼" if t['change'] < 0 else "─")
            color = GREEN if t['change'] > 0 else (RED if t['change'] < 0 else colors.HexColor('#718096'))
            direction = "improvement" if t['change'] > 0 else ("decline" if t['change'] < 0 else "no change")
            story.append(Paragraph(
                f"<font color='#{color.hexval()[2:]}'>Trend: R{t['first_round']} {t['first_score']:.1f}% → "
                f"R{rpt['latest_round']} {t['latest_score']:.1f}% ({arrow} {t['change']:+.1f} pp — {direction})</font>",
                normal_style))
        
        story.append(Spacer(1, 2*mm))
        
        # 약점 Topic 표
        if data['weak_topics']:
            story.append(Paragraph("Key Areas for Improvement (by error rate, top 5):", subheading_style))
            weak_data = [['Topic', 'Wrong / Total', 'Error Rate', 'Avg Correct (All)']]
            for wt in data['weak_topics']:
                avg_str = f"{wt['avg_pct']}%" if wt['avg_pct'] else 'N/A'
                weak_data.append([wt['topic'], f"{wt['wrong']} / {wt['total']}", f"{wt['wrong_rate']}%", avg_str])
            weak_table = Table(weak_data, colWidths=[55*mm, 30*mm, 25*mm, 30*mm])
            weak_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_BLUE]),
            ]))
            story.append(weak_table)
            story.append(Spacer(1, 2*mm))
        
        # 보강 추천 표
        if data['recommendations']:
            story.append(Paragraph("Recommended Practice (targeted at weak areas):", subheading_style))
            rec_data = [['Weak Topic', 'Recommended Question', 'Difficulty', 'Avg Correct']]
            diff_labels = {1: 'Very Easy', 2: 'Easy', 3: 'Medium', 4: 'Hard', 5: 'Very Hard'}
            for rec in data['recommendations']:
                for r in rec['recommended']:
                    rec_data.append([
                        rec['topic'],
                        f"R{r['round']} {labeled_subj} Q{r['question_no']}",
                        f"{r['difficulty']} — {diff_labels.get(r['difficulty'], '')}",
                        f"{r['overall_pct']}%",
                    ])
            rec_table = Table(rec_data, colWidths=[45*mm, 55*mm, 35*mm, 25*mm])
            rec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#276749')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0fff4')]),
            ]))
            story.append(rec_table)
            story.append(Spacer(1, 2*mm))
        
        story.append(Spacer(1, 1*mm))
    
    # 교사 코멘트 공간
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e0'), spaceAfter=4))
    story.append(Paragraph("Teacher's Comments / Notes for Parents:", subheading_style))
    story.append(Paragraph("_________________________________________________________________________________", normal_style))
    story.append(Paragraph("_________________________________________________________________________________", normal_style))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(f"<i>Generated by Edu-Kingdom College Test Reporting System on {today_str}</i>", small_style))
    
    doc.build(story)
    return output_path


# ============================================================
# 메인 파이프라인
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='EKC Test Report Automation Pipeline — PDF 파싱부터 보고서 생성까지'
    )
    parser.add_argument('--test-type', '-t', choices=['OC', 'Selective', 'TermTest'],
                        help='처리할 시험 유형 필터')
    parser.add_argument('--dry-run', action='store_true',
                        help='실제 PDF 생성 없이 절차만 실행 (파싱·은행 생성은 정상 수행)')
    parser.add_argument('--no-parse', action='store_true',
                        help='1단계 파싱 생략 (기존 parsed_reports_v2.json 재사용)')
    parser.add_argument('--no-bank', action='store_true',
                        help='2단계 질문 은행 생성 생략 (기존 question_bank_by_type.json 재사용)')
    parser.add_argument('--no-reports', action='store_true',
                        help='3단계 PDF 생성 생략 (데이터만 생성하고 종료)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='상세 출력 모드')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Edu-Kingdom College — Test Report Automation Pipeline")
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # ===== 0. 설정 확인 =====
    print(f"\n설정:")
    print(f"  결과지 소스: {J_DRIVE_BASE}")
    print(f"  출력 디렉토리: {REPORTS_OUTPUT_DIR}")
    print(f"  파싱 결과: {PARSED_JSON}")
    print(f"  질문 은행: {BANK_JSON}")
    
    if args.dry_run:
        print("  모드: DRY-RUN (PDF 생성 안 함)")
    
    # ===== 1단계: 파싱 =====
    all_reports = None
    if not args.no_parse:
        all_reports = scan_result_pdfs(args.test_type)
        if all_reports is None:
            print("\n오류: 파싱에 실패했습니다. 파이프라인을 중단합니다.")
            sys.exit(1)
        save_parsed_reports(all_reports)
    else:
        if os.path.exists(PARSED_JSON):
            print(f"\n{'='*60}")
            print("1단계: 파싱 생략 — 기존 파일 사용")
            print(f"{'='*60}")
            print(f"  로드: {PARSED_JSON}")
            with open(PARSED_JSON, 'r', encoding='utf-8') as f:
                all_reports = json.load(f)
            print(f"  로드 완료: {len(all_reports)}개 결과지")
        else:
            print(f"\n오류: --no-parse 지정했으나 파싱 결과 파일이 없음: {PARSED_JSON}")
            print("  --no-parse 없이 실행하거나, 먼저 파싱을 수행하세요.")
            sys.exit(1)
    
    # ===== 2단계: 질문 은행 =====
    bank_data = None
    if not args.no_bank:
        bank_data = build_question_bank(all_reports)
    else:
        if os.path.exists(BANK_JSON):
            print(f"\n{'='*60}")
            print("2단계: 질문 은행 생성 생략 — 기존 파일 사용")
            print(f"{'='*60}")
            print(f"  로드: {BANK_JSON}")
            with open(BANK_JSON, 'r', encoding='utf-8') as f:
                bank_data = json.load(f)
            print(f"  로드 완료")
        else:
            print(f"\n오류: --no-bank 지정했으나 질문 은행 파일이 없음: {BANK_JSON}")
            sys.exit(1)
    
    # ===== 3단계: 보고서 PDF =====
    if args.no_reports:
        print(f"\n{'='*60}")
        print("3단계: PDF 생성 생략 (요청에 따라)")
        print(f"{'='*60}")
    else:
        print(f"\n{'='*60}")
        print("3단계: 학생별 보고서 PDF 생성")
        print(f"{'='*60}")
        
        # 학생별 이력 빌드
        student_history = defaultdict(lambda: defaultdict(list))
        for r in all_reports:
            sn = r.get('student_name')
            if not sn:
                continue
            tt = r.get('test_type', 'Unknown')
            tr = r.get('test_round')
            if tr is None:
                continue
            subjects = {}
            for subj in r.get('subjects', []):
                short = get_subject_short(subj.get('name_raw', ''))
                subjects[short] = {
                    'score': subj.get('score', 0),
                    'rank_pct': subj.get('rank_pct'),
                    'total': subj.get('total', 0),
                    'correct': subj.get('correct_count', 0),
                    'wrong': subj.get('wrong_count', 0),
                    'topic_stats': defaultdict(lambda: {'wrong': 0, 'total': 0, 'pct_values': []}),
                }
                for q in subj.get('questions', []):
                    t = q.get('topic', '')
                    subjects[short]['topic_stats'][t]['total'] += 1
                    subjects[short]['topic_stats'][t]['pct_values'].append(q.get('pct', 0))
                    if not q.get('correct', True):
                        subjects[short]['topic_stats'][t]['wrong'] += 1
            for short, data in subjects.items():
                for t, ts in data['topic_stats'].items():
                    if ts['pct_values']:
                        ts['avg_pct'] = round(sum(ts['pct_values']) / len(ts['pct_values']), 1)
                    else:
                        ts['avg_pct'] = None
            student_history[sn][tt].append({
                'round': tr,
                'filename': r.get('filename', ''),
                'subjects': subjects,
                'student_id': r.get('student_id'),
            })
        for sn in student_history:
            for tt in student_history[sn]:
                student_history[sn][tt].sort(key=lambda x: x['round'])
        
        # 처리할 시험 유형
        test_types_to_process = [args.test_type] if args.test_type else ['OC', 'Selective', 'TermTest']
        
        total_generated = 0
        total_skipped = 0
        
        for test_type in test_types_to_process:
            type_rounds = defaultdict(set)
            for r in all_reports:
                if r.get('test_type') == test_type and r.get('student_name'):
                    tr = r.get('test_round')
                    if tr is not None:
                        type_rounds[r['student_name']].add(tr)
            
            if not type_rounds:
                print(f"\n{test_type}: 해당 유형의 결과지 없음")
                continue
            
            all_rounds_set = set()
            for rounds in type_rounds.values():
                all_rounds_set.update(rounds)
            latest_overall = max(all_rounds_set) if all_rounds_set else None
            target_rounds = {args.round} if args.round else {latest_overall} if latest_overall else set()
            
            for target_round in sorted(target_rounds):
                if target_round not in all_rounds_set:
                    continue
                
                target_folder = get_target_folder(test_type, target_round)
                if not os.path.exists(target_folder):
                    print(f"\n{test_type} Round {target_round}: 폴더 없음 — {target_folder}")
                    continue
                
                students_in_round = []
                for sn, rounds in type_rounds.items():
                    if target_round in rounds:
                        rpt = build_report_data(sn, test_type, target_round, bank_data, all_reports, student_history)
                        if rpt:
                            students_in_round.append((sn, rpt))
                
                if not students_in_round:
                    continue
                
                print(f"\n{test_type} Round {target_round}: {len(students_in_round)}명 보고서 생성")
                
                for sn, rpt in students_in_round:
                    safe_name = sn.replace(' ', '_')
                    filename = f"{test_type}{target_round}_{safe_name}_Progress_Report.pdf"
                    output_path = os.path.join(target_folder, filename)
                    
                    if args.dry_run:
                        print(f"  📄 {filename} (DRY-RUN — 생성 안 함)")
                        continue
                    
                    try:
                        generate_pdf(rpt, output_path)
                        size_kb = os.path.getsize(output_path) / 1024
                        print(f"  ✅ {sn}: {filename} ({size_kb:.1f} KB)")
                        total_generated += 1
                    except Exception as e:
                        print(f"  ❌ {sn}: {e}")
                        total_skipped += 1
        
        print(f"\n{'='*60}")
        print(f"완료: {total_generated}개 PDF 생성, {total_skipped}개 실패")
        print(f"{'='*60}")
    
    # ===== 요약 =====
    print(f"\n{'='*60}")
    print("파이프라인 완료")
    print(f"{'='*60}")
    print(f"  파싱 결과: {PARSED_JSON}")
    print(f"  질문 은행: {BANK_JSON}")
    if not args.no_reports and not args.dry_run:
        print(f"  보고서 PDF: 각 학생별 시험 결과 폴더에 생성됨")


if __name__ == '__main__':
    main()
