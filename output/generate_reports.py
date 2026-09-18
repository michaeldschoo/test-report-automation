#!/usr/bin/env python3
"""
Edu-Kingdom College — Student Progress Report Generator
========================================================
시험 결과 PDF와 문제 은행 데이터를 기반으로,
학생별 영문 분석 보고서를 PDF로 생성합니다.

사용법:
    python generate_reports.py                    # 모든 시험 유형의 최신 회차 자동 감지
    python generate_reports.py --test-type OC     # OC만
    python generate_reports.py --test-type Selective  # Selective만
    python generate_reports.py --round 5          # OC 5회차만
    python generate_reports.py --test-type OC --round 5  # OC 5회차만 (명시적)

필요 파일 (output/ 디렉토리에 있어야 함):
    - parsed_reports_v2.json   : 시험 결과지 파싱 데이터
    - question_bank_by_type.json : 시험 유형별 질문 은행

생성 결과물:
    - 각 학생별 시험 결과 폴더(예: OC_R05/, Selective_R20/)에
      <TT><round>_<학생이름_공백→밑줄>_Progress_Report.pdf
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

# ===== 경로 설정 =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not BASE_DIR:
    BASE_DIR = r"D:\EKCRPA\test-report-automation\output"

REPORTS_JSON = os.path.join(BASE_DIR, "parsed_reports_v2.json")
BANK_JSON = os.path.join(BASE_DIR, "question_bank_by_type.json")


# ===== 과목 라벨 정규화 =====
def get_subject_short(name_raw):
    """결과지 과목명을 짧은 표준명으로 정규화"""
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


# ===== 학생별 이력 빌드 =====
def build_student_history(all_reports):
    """모든 보고서에서 학생별 시험 이력 구축"""
    history = defaultdict(lambda: defaultdict(list))
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

        history[sn][tt].append({
            'round': tr,
            'filename': r.get('filename', ''),
            'subjects': subjects,
            'student_id': r.get('student_id'),
        })

    for sn in history:
        for tt in history[sn]:
            history[sn][tt].sort(key=lambda x: x['round'])

    return history


# ===== 질문 은행 로드 =====
def load_question_bank():
    """시험 유형별 질문 은행 로드"""
    if not os.path.exists(BANK_JSON):
        print(f"경고: 질문 은행 파일을 찾을 수 없음: {BANK_JSON}")
        return {'OC': [], 'Selective': [], 'TermTest': [], 'All': []}

    with open(BANK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    bank = {}
    for tt in ['OC', 'Selective', 'TermTest', 'All']:
        qb = data.get('question_bank', {}).get(tt, {})
        bank[tt] = qb.get('questions', []) if isinstance(qb, dict) else []

    return bank


# ===== 약점 Topic 분석 =====
def find_weak_topics(subject_data, top_n=5):
    """과목별 약점 Topic Top N (오답률 기준)"""
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


# ===== 주제별 보강 추천 =====
def recommend_for_topic(topic, subject, bank, max_n=2):
    """질문 은행에서 특정 Topic의 보강 문제 추천 (난이도 낮은 순)"""
    candidates = [q for q in bank
                  if q.get('topic') == topic
                  and q.get('subject') == subject]
    candidates.sort(key=lambda x: x.get('difficulty', 99))
    return candidates[:max_n]


# ===== 보고서 데이터 생성 =====
def build_report_data(sn, test_type, target_round, bank):
    """학생별 보고서용 데이터 구조 생성"""
    hist = student_history  # 빌드된 이력은 전역/클로저에서 접근
    test_rounds = hist.get(sn, {}).get(test_type, [])
    latest = [r for r in test_rounds if r['round'] == target_round]
    if not latest:
        return None
    latest = latest[0]

    other_types = {}
    if sn in student_history:
        for tt, rounds in student_history[sn].items():
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
        bank_for_type = bank.get(test_type, [])
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


# ===== PDF 생성 (reportlab) =====
def generate_pdf(rpt, output_path):
    """학생별 보고서 PDF 생성 (reportlab)"""
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    # 스타일 정의
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'Title2', parent=styles['Title'],
        fontSize=18, textColor=colors.HexColor('#1a365d'),
        spaceAfter=6, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.grey,
        alignment=TA_CENTER, spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        'Heading2', parent=styles['Heading2'],
        fontSize=13, textColor=colors.HexColor('#2c5282'),
        spaceBefore=10, spaceAfter=4,
    )
    subheading_style = ParagraphStyle(
        'Subheading', parent=styles['Heading3'],
        fontSize=11, textColor=colors.HexColor('#2d3748'),
        spaceBefore=6, spaceAfter=2,
    )
    normal_style = ParagraphStyle(
        'Normal2', parent=styles['Normal'],
        fontSize=10, leading=14, spaceAfter=2,
    )
    small_style = ParagraphStyle(
        'Small', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#4a5568'), leading=12,
    )

    DARK_BLUE = colors.HexColor('#1a365d')
    MED_BLUE = colors.HexColor('#2c5282')
    LIGHT_BLUE = colors.HexColor('#ebf4ff')
    RED = colors.HexColor('#c53030')
    GREEN = colors.HexColor('#276749')

    SUBJECT_LABELS = {
        'Reading': 'Reading (English)',
        'Mathematical Reasoning': 'Mathematical Reasoning',
        'Thinking Skills': 'Thinking Skills',
        'Thinking Ability': 'Thinking Ability',
        'English': 'English',
        'Mathematics': 'Mathematics',
    }

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

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
    avg_score = rpt['average_score']
    weakest = rpt['weakest_subject']
    strongest = rpt['strongest_subject']
    summary_data = [
        ['Average Across Subjects', f'{avg_score:.1f}%'],
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
            f"({correct}/{total} correct){rank_text}",
            normal_style
        ))

        if data['trend']:
            t = data['trend']
            arrow = "▲" if t['change'] > 0 else ("▼" if t['change'] < 0 else "─")
            color = GREEN if t['change'] > 0 else (RED if t['change'] < 0 else colors.HexColor('#718096'))
            direction = "improvement" if t['change'] > 0 else ("decline" if t['change'] < 0 else "no change")
            story.append(Paragraph(
                f"<font color='#{color.hexval()[2:]}'>Trend: R{t['first_round']} {t['first_score']:.1f}% → "
                f"R{rpt['latest_round']} {t['latest_score']:.1f}% ({arrow} {t['change']:+.1f} pp — {direction})</font>",
                normal_style
            ))

        story.append(Spacer(1, 2*mm))

        # 약점 Topic 표
        if data['weak_topics']:
            story.append(Paragraph("Key Areas for Improvement (by error rate, top 5):", subheading_style))
            weak_data = [['Topic', 'Wrong / Total', 'Error Rate', 'Avg Correct (All)']]
            for wt in data['weak_topics']:
                avg_str = f"{wt['avg_pct']}%" if wt['avg_pct'] else 'N/A'
                weak_data.append([
                    wt['topic'],
                    f"{wt['wrong']} / {wt['total']}",
                    f"{wt['wrong_rate']}%",
                    avg_str,
                ])
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
    story.append(Paragraph(
        f"<i>Generated by Edu-Kingdom College Test Reporting System on {today_str}</i>",
        small_style
    ))

    doc.build(story)
    return output_path


# ===== 폴더 경로 결정 =====
def get_target_folder(test_type, target_round):
    """학생별 결과 폴더 경로 반환"""
    if test_type == 'OC':
        return os.path.join(BASE_DIR, f"OC_R{target_round:02d}")
    elif test_type == 'Selective':
        return os.path.join(BASE_DIR, f"Selective_R{target_round:02d}")
    elif test_type == 'TermTest':
        return os.path.join(BASE_DIR, f"TermTest_R{target_round:02d}")
    else:
        return os.path.join(BASE_DIR, f"{test_type}_R{target_round:02d}")


# ===== 메인 =====
def main():
    global BASE_DIR, REPORTS_JSON, BANK_JSON
    parser = argparse.ArgumentParser(
        description='Generate student progress report PDFs (English) for Edu-Kingdom College.'
    )
    parser.add_argument('--test-type', '-t', choices=['OC', 'Selective', 'TermTest'],
                        help='시험 유형 필터 (지정하지 않으면 모든 유형 처리)')
    parser.add_argument('--round', '-r', type=int,
                        help='특정 차수만 처리 (지정하지 않으면 해당 유형의 최신 차수 사용)')
    parser.add_argument('--student', '-s',
                        help='특정 학생만 처리 (이름 부분 일치, 예: "Apson")')
    parser.add_argument('--output-dir', '-o',
                        default=BASE_DIR,
                        help=f'출력 베이스 디렉토리 (기본: {BASE_DIR})')
    parser.add_argument('--reports-json',
                        default=REPORTS_JSON,
                        help=f'파싱된 결과지 JSON 경로 (기본: {REPORTS_JSON})')
    parser.add_argument('--bank-json',
                        default=BANK_JSON,
                        help=f'질문 은행 JSON 경로 (기본: {BANK_JSON})')
    parser.add_argument('--dry-run', action='store_true',
                        help='PDF 생성 없이 어떤 보고서가 생성될지 정보만 출력')

    args = parser.parse_args()

    BASE_DIR = args.output_dir
    REPORTS_JSON = args.reports_json
    BANK_JSON = args.bank_json

    # 입력 파일 확인
    if not os.path.exists(REPORTS_JSON):
        print(f"오류: 결과지 JSON 파일을 찾을 수 없음: {REPORTS_JSON}")
        print("  먼저 parsed_reports_v2.json이 존재하는지 확인하세요.")
        sys.exit(1)

    if not os.path.exists(BANK_JSON):
        print(f"경고: 질문 은행 파일을 찾을 수 없음: {BANK_JSON}")
        print("  질문 은행 없이 보고서를 생성할 수 있지만, 보강 추천은 포함되지 않습니다.")

    # 데이터 로드
    print(f"결과지 로딩: {REPORTS_JSON} ...", end=' ')
    with open(REPORTS_JSON, 'r', encoding='utf-8') as f:
        all_reports = json.load(f)
    print(f"완료 ({len(all_reports)}개 결과지)")

    bank = load_question_bank()
    print(f"질문 은행 로딩: OC={len(bank.get('OC', []))}문, Selective={len(bank.get('Selective', []))}문")

    # 학생별 이력 빌드
    global student_history
    student_history = build_student_history(all_reports)

    # 처리할 시험 유형 결정
    test_types_to_process = []
    if args.test_type:
        test_types_to_process.append(args.test_type)
    else:
        test_types_to_process = ['OC', 'Selective', 'TermTest']

    total_generated = 0
    total_skipped = 0

    for test_type in test_types_to_process:
        # 해당 유형의 모든 학생 + 라운드 찾기
        type_rounds = defaultdict(set)
        for r in all_reports:
            if r.get('test_type') == test_type and r.get('student_name'):
                tr = r.get('test_round')
                if tr is not None:
                    type_rounds[r['student_name']].add(tr)

        if not type_rounds:
            print(f"\n{test_type}: 해당 유형의 결과지 없음 — 건너뜀")
            continue

        # 처리할 라운드 결정
        if args.round:
            target_rounds = {args.round}
        else:
            # 각 학생별 최신 라운드 (또는 전체 중 최신)
            all_rounds_set = set()
            for rounds in type_rounds.values():
                all_rounds_set.update(rounds)
            latest_overall = max(all_rounds_set) if all_rounds_set else None
            target_rounds = {latest_overall} if latest_overall else set()

        if not target_rounds:
            print(f"\n{test_type}: 처리할 라운드 없음 — 건너뜀")
            continue

        for target_round in sorted(target_rounds):
            if target_round not in all_rounds_set:
                continue

            target_folder = get_target_folder(test_type, target_round)
            print(f"\n{'='*60}")
            print(f"{test_type} Round {target_round} 보고서 생성")
            print(f"대상 폴더: {target_folder}")
            print(f"{'='*60}")

            if not os.path.exists(target_folder):
                print(f"  폴더 없음: {target_folder} — 폴더 생성 또는 확인 필요")
                continue

            # 해당 라운드에 결과가 있는 학생들
            students_in_round = []
            for sn, rounds in type_rounds.items():
                if target_round in rounds:
                    # 학생 이름 필터
                    if args.student and args.student.lower() not in sn.lower():
                        continue
                    # 보고서 데이터 생성 가능 확인
                    rpt = build_report_data(sn, test_type, target_round, bank)
                    if rpt:
                        students_in_round.append((sn, rpt))

            if not students_in_round:
                print(f"  보고할 학생 없음")
                continue

            for sn, rpt in students_in_round:
                safe_name = sn.replace(' ', '_')
                filename = f"{test_type}{target_round}_{safe_name}_Progress_Report.pdf"
                output_path = os.path.join(target_folder, filename)

                if args.dry_run:
                    print(f"\n  [{sn}]")
                    print(f"    파일: {filename}")
                    print(f"    평균: {rpt['average_score']:.1f}%")
                    print(f"    최강점: {rpt['strongest_subject']} ({rpt['subjects'][rpt['strongest_subject']]['score']:.1f}%)")
                    print(f"    보강 필요: {rpt['weakest_subject']} ({rpt['subjects'][rpt['weakest_subject']]['score']:.1f}%)")
                    print(f"    과목 수: {len(rpt['subjects'])} | 약점 Topic 수: {sum(len(d['weak_topics']) for d in rpt['subjects'].values())}")
                    print(f"    보강 추천: {sum(len(d['recommendations']) for d in rpt['subjects'].values())}")
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


if __name__ == '__main__':
    main()
