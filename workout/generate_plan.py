#!/usr/bin/env python3
"""
Generate a 52-week periodized plan and replace DEFAULT_WORKOUT_DATA in the
two tracker HTML files.

Structure:
  4 phases × 12 weeks = 48 weeks, each phase is 3 build + 1 deload × 3.
  Weeks 49-52: Deload → Technique → Peak prep → TEST.

Features:
  - Rotating primary-lift variants per phase (Squat/Bench/Deadlift/OHP family).
  - Rep schemes shift by phase: Hypertrophy → Strength → Power → Peak.
  - Weekly load cue in notes (RPE/% target) so load progression is explicit.
  - Every strength day ends with 2 rotating core moves.
"""

import json
import re
from datetime import date, timedelta


START_DATE = date(2026, 11, 23)  # Monday
TOTAL_WEEKS = 52


# --- Reusable schemes -------------------------------------------------------

def main_scheme(phase_idx, build_idx):
    """Return (sets, reps, rpe_note) for the main lift based on phase/week."""
    if phase_idx == 0:        # Hypertrophy
        if build_idx == 3: return ('2', '8–10', 'Deload: half volume, RPE 5.')
        rpe = ['6', '7', '8'][build_idx]
        return ('4', '8–10', f'RPE {rpe}; add 2.5–5 lb vs last week.')
    if phase_idx == 1:        # Strength
        if build_idx == 3: return ('3', '3', 'Deload: 60% of W3 load, crisp reps.')
        pct = ['82%', '85%', '88%'][build_idx]
        return ('5', '5', f'~{pct} 1RM (RPE 7–8). Steady loads across all 5 sets.')
    if phase_idx == 2:        # Power/Hybrid
        if build_idx == 3: return ('3', '3', 'Deload: 60% load, focus on bar speed.')
        pct = ['75%', '78%', '82%'][build_idx]
        return ('5', '3', f'~{pct} 1RM, EXPLOSIVE intent on every rep.')
    if phase_idx == 3:        # Peak
        if build_idx == 3: return ('2', '3', 'Deload: 55% load. Prime the nervous system.')
        pct = ['85%', '90%', '95%'][build_idx]
        reps = ['5', '3', '1'][build_idx]
        sets = ['3', '3', '3'][build_idx]
        return (sets, reps, f'~{pct} 1RM. Rest 3–5 min between sets.')
    raise ValueError(phase_idx)


def accessory_reps(phase_idx):
    return ['10–12', '6–8', '5–6', '4–6'][phase_idx]


def accessory_sets(phase_idx, build_idx):
    if build_idx == 3: return '1'  # deload
    return ['3', '4', '3', '3'][phase_idx]


# --- Lift rotations per phase ----------------------------------------------

# (phase 0 Hypertrophy, phase 1 Strength, phase 2 Power, phase 3 Peak)

SQUAT = [
    'Back Squat',             # P1
    'Front Squat',            # P2
    'Trap Bar Jump Squat',    # P3
    'Safety Bar Squat',       # P4
]

HINGE = [
    'Hex Bar Deadlift',
    'Conventional Deadlift',
    'Deficit Deadlift',
    'Rack Pull',
]

HBENCH = [
    'Multi-Grip Bench',
    'Barbell Bench Press',
    'Speed Bench (60% explosive)',
    'Close-Grip Bench',
]

HROW = [
    'Chest-Supported Row',
    'Pendlay Row',
    'Explosive DB Row',
    'Pendlay Row',
]

OHPRESS = [
    'Landmine Press',
    'Standing Overhead Press',
    'Push Press',
    'Standing Overhead Press',
]

VPULL = [
    'Lat Pulldown',
    'Weighted Pull-up',
    'Weighted Chin-up (explosive)',
    'Weighted Pull-up',
]

PHASE_NAMES = ['Hypertrophy Base', 'Strength', 'Power / Hybrid', 'Peak Strength']


# --- Core rotation (two moves per strength day, varies by phase) -----------

CORE = {
    0: {  # Phase 1: foundational
        'Mon': [('Dead Bug', '3', '10/side', 'Low back pressed into floor.')],
        'Tue': [('Hollow Hold', '3', '30s', 'Lower back flat; small of back pressed down.')],
        'Thu': [('Hanging Knee Raise', '3', '10–12', 'Control the eccentric; no swing.')],
        'Fri': [('Plank', '3', '45s', 'Ribs down, glutes squeezed.')],
        '_common': ('Pallof Press', '3', '10/side', 'Resist rotation; slow exhale.'),
    },
    1: {  # Phase 2: heavier anti-movement
        'Mon': [('Ab Wheel Rollout', '3', '8', 'Stop before lumbar extends.')],
        'Tue': [('Side Plank', '3', '40s/side', 'Stack hips; straight line.')],
        'Thu': [('Suitcase Carry', '3', '30 steps/side', 'Heavy DB; don\'t lean.')],
        'Fri': [('Hanging Leg Raise', '3', '8–10', 'Full control; no kipping.')],
        '_common': ('Farmer Carry', '3', '30 steps', 'Grip + trunk integration.'),
    },
    2: {  # Phase 3: dynamic/rotational
        'Mon': [('Medicine Ball Slam', '3', '6', 'Full-body power expression.')],
        'Tue': [('Cable Chop (high-to-low)', '3', '8/side', 'Rotate through hips; brace trunk.')],
        'Thu': [('Half-Kneeling Pallof Press', '3', '10/side', 'Kneeling adds instability.')],
        'Fri': [('Plank w/ Shoulder Tap', '3', '10/side', 'Minimize hip sway.')],
        '_common': ('Pallof Walkout', '3', '8/side', 'Resist rotation while stepping out.'),
    },
    3: {  # Phase 4: stability under heavy load
        'Mon': [('Dead Bug (pause)', '3', '8/side', 'Hold extended position 2s.')],
        'Tue': [('Ab Wheel Rollout', '3', '8–10', 'Deeper range as able.')],
        'Thu': [('Farmer Carry (heavy)', '3', '40 steps', 'Build full-body stiffness.')],
        'Fri': [('Hollow Rock', '3', '20s', 'Lower back glued down throughout.')],
        '_common': ('Side Plank w/ Reach', '3', '8/side', 'Reach under and up.'),
    },
}


# --- Build a strength session ---------------------------------------------

def session(phase_idx, build_idx, day_label, main_name, acc_list, core_day_key):
    main_sets, main_reps, main_note = main_scheme(phase_idx, build_idx)
    acc_s = accessory_sets(phase_idx, build_idx)
    acc_r = accessory_reps(phase_idx)
    exercises = [{
        'name': main_name,
        'sets': main_sets,
        'reps': main_reps,
        'notes': main_note,
    }]
    for acc_name, acc_hint in acc_list:
        exercises.append({
            'name': acc_name,
            'sets': acc_s,
            'reps': acc_r if '/side' not in (acc_hint or '') else acc_r + '/side',
            'notes': acc_hint,
        })
    # Add core: one day-specific + one common move
    for core_name, c_sets, c_reps, c_notes in CORE[phase_idx][day_label]:
        exercises.append({'name': core_name, 'sets': c_sets, 'reps': c_reps, 'notes': c_notes})
    common = CORE[phase_idx]['_common']
    exercises.append({'name': common[0], 'sets': common[1], 'reps': common[2], 'notes': common[3]})
    return exercises


# --- Day builders ---------------------------------------------------------

def build_day(phase_idx, build_idx, week_label, dow):
    """Return (am, pm) workout dicts for this week+day, or (None, None)."""
    phase_name = PHASE_NAMES[phase_idx]
    warm = 'Warm-up: 8–10 min easy bike or row, then 2–3 progressive warm-up sets for the first lift.'
    cardio_warm = 'Warm-up: 5–8 min easy, keep RPE under 4/10.'

    if dow == 'Mon':  # Lower A — Squat
        ex = session(phase_idx, build_idx, 'Mon',
                     SQUAT[phase_idx],
                     [('Bulgarian Split Squat', 'Controlled; load as able.'),
                      ('Standing Calf Raise', 'Pause 1s at top.')],
                     'Mon')
        am = {'session': f'Lower A — Squat ({phase_name})', 'type': 'Strength',
              'exercises': ex, 'notes': warm}
        pm = {'session': 'Bike — Zone 2', 'type': 'Run/Cardio',
              'notes': f'{25 if build_idx==3 else 35} min easy aerobic (RPE 3–4/10).'}
        return am, pm

    if dow == 'Tue':  # Upper A — Horizontal Push/Pull
        ex = session(phase_idx, build_idx, 'Tue',
                     HBENCH[phase_idx],
                     [(HROW[phase_idx], 'Pause 1s at the squeeze.'),
                      ('Rope Face Pull', 'Elbows high; thumbs back.')],
                     'Tue')
        am = {'session': f'Upper A — Horizontal ({phase_name})', 'type': 'Strength',
              'exercises': ex, 'notes': warm}
        pm = {'session': 'Row — Zone 2', 'type': 'Run/Cardio',
              'notes': f'{25 if build_idx==3 else 35} min easy aerobic.'}
        return am, pm

    if dow == 'Wed':  # Mobility + dedicated core
        ex = [
            {'name': 'Ankle Dorsiflexion Rocks', 'sets': '2', 'reps': '10/side', 'notes': 'Heel down; controlled.'},
            {'name': '90/90 Hip Switches', 'sets': '2', 'reps': '8/side', 'notes': 'Smooth transitions, upright trunk.'},
            {'name': 'Open Books (T-spine)', 'sets': '2', 'reps': '8/side', 'notes': 'Breathe into rotation.'},
            {'name': 'Dead Bug', 'sets': '3', 'reps': '10/side', 'notes': 'Opposite arm + leg; low back pinned.'},
            {'name': 'Bird Dog', 'sets': '3', 'reps': '8/side', 'notes': 'Hold 2s at end range.'},
            {'name': 'Side Plank', 'sets': '3', 'reps': '30–45s/side', 'notes': 'Straight line, hips stacked.'},
            {'name': 'Hollow Hold', 'sets': '3', 'reps': '30s', 'notes': 'Small of back pressed down.'},
        ]
        am = {'session': 'Mobility + Core', 'type': 'Strength',
              'exercises': ex, 'notes': cardio_warm}
        pm = {'session': 'Easy Run or Bike', 'type': 'Run/Cardio',
              'notes': '30–35 min aerobic Z2; optional.'}
        return am, pm

    if dow == 'Thu':  # Lower B — Hinge
        ex = session(phase_idx, build_idx, 'Thu',
                     HINGE[phase_idx],
                     [('Single-leg RDL', 'Hinge from hip; neutral spine.'),
                      ('Glider Hamstring Curl', 'Sliders/glider; eccentric focus.')],
                     'Thu')
        am = {'session': f'Lower B — Hinge ({phase_name})', 'type': 'Strength',
              'exercises': ex, 'notes': warm}
        pm = {'session': 'Bike — Zone 2', 'type': 'Run/Cardio',
              'notes': f'{25 if build_idx==3 else 30} min easy aerobic.'}
        return am, pm

    if dow == 'Fri':  # Upper B — Vertical Push/Pull
        ex = session(phase_idx, build_idx, 'Fri',
                     OHPRESS[phase_idx],
                     [(VPULL[phase_idx], 'Full stretch, controlled.'),
                      ('DB Lateral Raise', 'Light; strict form.')],
                     'Fri')
        am = {'session': f'Upper B — Vertical ({phase_name})', 'type': 'Strength',
              'exercises': ex, 'notes': warm}
        pm = {'session': 'Row — Zone 2', 'type': 'Run/Cardio',
              'notes': f'{25 if build_idx==3 else 35} min easy aerobic.'}
        return am, pm

    if dow == 'Sat':  # Long run — progresses across the year
        week_num = 1  # filled in below with global week, overwritten
        base = 55
        return 'SAT', None

    if dow == 'Sun':  # Recovery/mobility
        ex = [
            {'name': 'Walk + Mobility', 'sets': '1', 'reps': '20–30 min', 'notes': 'Easy walk + any lingering mobility.'},
            {'name': 'Couch Stretch', 'sets': '1', 'reps': '45s/side', 'notes': 'Hip flexor length.'},
            {'name': 'Band Pull-aparts', 'sets': '2', 'reps': '15', 'notes': 'Light; shoulder prep.'},
        ]
        am = {'session': 'Recovery + Mobility', 'type': 'Strength',
              'exercises': ex, 'notes': 'Keep this restorative.'}
        pm = {'session': 'Recovery Walk', 'type': 'Run/Cardio',
              'notes': '20–30 min walk; rest if tired.'}
        return am, pm

    return None, None


def long_run_minutes(global_week_num, phase_idx, build_idx):
    """Base trail run length + progressive bump across the year.
       Deload weeks cut to ~60% of build-week length.
    """
    base_by_phase = [55, 65, 75, 60]  # minutes for W1 of each phase
    bump_per_build = [5, 5, 5, 0]     # W1→W2→W3 increment
    base = base_by_phase[phase_idx]
    if build_idx == 3:
        return int(base * 0.6)
    return base + bump_per_build[phase_idx] * build_idx


# --- Taper/test weeks 49-52 -----------------------------------------------

def finale_day(week_idx_in_finale, dow):
    """Weeks 49-52: deload, technique, peak-prep, TEST."""
    names = ['Deload', 'Technique & Tempo', 'Peak Prep', 'TEST WEEK']
    label = names[week_idx_in_finale]
    is_test = (week_idx_in_finale == 3)
    is_tech = (week_idx_in_finale == 1)

    def strength_session(primary_name, acc_list, main_sets, main_reps, note):
        ex = [{'name': primary_name, 'sets': main_sets, 'reps': main_reps, 'notes': note}]
        for name, hint in acc_list:
            ex.append({'name': name, 'sets': '2', 'reps': '6–8', 'notes': hint})
        # light core
        ex.append({'name': 'Dead Bug', 'sets': '2', 'reps': '8/side', 'notes': 'Control.'})
        ex.append({'name': 'Pallof Press', 'sets': '2', 'reps': '10/side', 'notes': 'Resist rotation.'})
        return ex

    warm = 'Thorough warm-up; progressive top-down loading.'

    if dow == 'Mon':
        if is_test:
            notes = 'Work up to a 1RM: 5@50%, 3@70%, 2@80%, 1@87%, 1@92%, 1@97%, 1RM attempt. 3 min rest between work sets.'
            ex = strength_session('Back Squat — 1RM Test',
                                  [('Pallof Press', 'Prime trunk.')],
                                  '1', '1', notes)
        elif is_tech:
            ex = strength_session('Tempo Back Squat', [('Goblet Squat', 'Light; form check.')],
                                  '4', '5', '3-second descent, 1-second pause. Empty-to-moderate bar.')
        else:
            pct = ['50–60%', None, '80%'][week_idx_in_finale if week_idx_in_finale < 3 else 2]
            ex = strength_session('Back Squat',
                                  [('Walking Lunge', 'Moderate load.')],
                                  '3', '5', f'{pct} 1RM. Crisp reps; no strain.')
        am = {'session': f'Lower A — {label}', 'type': 'Strength', 'exercises': ex, 'notes': warm}
        pm = {'session': 'Bike — Zone 2', 'type': 'Run/Cardio', 'notes': '25 min easy.'}
        return am, pm

    if dow == 'Tue':
        if is_test:
            notes = 'Work up to a 1RM on the bench: 5@50%, 3@70%, 2@80%, 1@87%, 1@92%, 1@97%, 1RM.'
            ex = strength_session('Bench Press — 1RM Test',
                                  [('Chin-up', 'Prime pull.')],
                                  '1', '1', notes)
        elif is_tech:
            ex = strength_session('Tempo Bench Press', [('DB Row', 'Form focus.')],
                                  '4', '5', '3-sec descent, 2-sec pause on chest.')
        else:
            pct = '50–60%' if week_idx_in_finale == 0 else '80%'
            ex = strength_session('Bench Press',
                                  [('DB Row', 'Pause at the squeeze.')],
                                  '3', '5', f'{pct} 1RM.')
        am = {'session': f'Upper A — {label}', 'type': 'Strength', 'exercises': ex, 'notes': warm}
        pm = {'session': 'Row — Zone 2', 'type': 'Run/Cardio', 'notes': '20 min easy.'}
        return am, pm

    if dow == 'Wed':
        ex = [
            {'name': 'Ankle Rocks', 'sets': '2', 'reps': '10/side', 'notes': 'Easy mobility.'},
            {'name': 'Hip Openers', 'sets': '2', 'reps': '8/side', 'notes': 'Breathe.'},
            {'name': 'Dead Bug', 'sets': '2', 'reps': '8/side', 'notes': 'Low-load.'},
            {'name': 'Side Plank', 'sets': '2', 'reps': '30s/side', 'notes': 'Easy.'},
        ]
        am = {'session': 'Mobility + Core (light)', 'type': 'Strength', 'exercises': ex,
              'notes': 'Recovery day. Keep RPE under 5.'}
        pm = {'session': 'Easy Walk', 'type': 'Run/Cardio', 'notes': '20–30 min, optional.'}
        return am, pm

    if dow == 'Thu':
        if is_test:
            notes = 'Work up to a 1RM: 5@50%, 3@70%, 2@80%, 1@87%, 1@92%, 1@97%, 1RM attempt.'
            ex = strength_session('Deadlift — 1RM Test',
                                  [('Rack Pull', 'Prime lockout.')],
                                  '1', '1', notes)
        elif is_tech:
            ex = strength_session('Deadlift (paused off floor)',
                                  [('RDL', 'Form.')],
                                  '4', '3', '2-sec pause 1 inch off floor; light bar.')
        else:
            pct = '50–60%' if week_idx_in_finale == 0 else '80%'
            ex = strength_session('Deadlift',
                                  [('RDL', 'Hinge drill.')],
                                  '3', '5', f'{pct} 1RM. No grinding.')
        am = {'session': f'Lower B — {label}', 'type': 'Strength', 'exercises': ex, 'notes': warm}
        pm = {'session': 'Bike — Zone 2', 'type': 'Run/Cardio', 'notes': '20 min easy.'}
        return am, pm

    if dow == 'Fri':
        if is_test:
            notes = 'Work up to a 1RM on overhead press: 5@50%, 3@70%, 2@80%, 1@87%, 1@92%, 1@97%, 1RM.'
            ex = strength_session('Overhead Press — 1RM Test',
                                  [('Pull-up', 'Prime pull.')],
                                  '1', '1', notes)
        elif is_tech:
            ex = strength_session('Tempo Overhead Press',
                                  [('Pull-up', 'Form focus.')],
                                  '4', '5', '3-sec descent, pause at shoulders.')
        else:
            pct = '50–60%' if week_idx_in_finale == 0 else '80%'
            ex = strength_session('Overhead Press',
                                  [('Pull-up', 'Full stretch, controlled.')],
                                  '3', '5', f'{pct} 1RM.')
        am = {'session': f'Upper B — {label}', 'type': 'Strength', 'exercises': ex, 'notes': warm}
        pm = {'session': 'Row — Zone 2', 'type': 'Run/Cardio', 'notes': '20 min easy.'}
        return am, pm

    if dow == 'Sat':
        length = [45, 40, 50, 30][week_idx_in_finale]
        am = {'session': 'Trail Run — Easy Endurance', 'type': 'Run/Cardio',
              'notes': f'{length} min easy on trails. Recovery pace — hike climbs if needed.'}
        pm = {'session': 'Easy Recovery Spin', 'type': 'Run/Cardio',
              'notes': '15–20 min very easy.'}
        return am, pm

    if dow == 'Sun':
        ex = [
            {'name': 'Walk + Mobility', 'sets': '1', 'reps': '20–30 min', 'notes': 'Easy.'},
            {'name': 'Couch Stretch', 'sets': '1', 'reps': '45s/side', 'notes': 'Hip flexor.'},
        ]
        am = {'session': 'Recovery + Mobility', 'type': 'Strength', 'exercises': ex,
              'notes': 'Restorative.'}
        pm = {'session': 'Recovery Walk', 'type': 'Run/Cardio', 'notes': '20–30 min, optional.'}
        return am, pm

    return None, None


# --- Main generator -------------------------------------------------------

DOWS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def generate_plan():
    plan = {}
    for wk in range(1, TOTAL_WEEKS + 1):
        in_finale = wk >= 49
        if not in_finale:
            phase_idx = (wk - 1) // 12          # 0..3
            build_idx = (wk - 1) % 4            # 0=W1, 1=W2, 2=W3, 3=Deload
        for i, dow in enumerate(DOWS):
            d = START_DATE + timedelta(days=(wk - 1) * 7 + i)
            if in_finale:
                am, pm = finale_day(wk - 49, dow)
            else:
                if dow == 'Sat':
                    length = long_run_minutes(wk, phase_idx, build_idx)
                    am = {'session': 'Trail Run — Easy Endurance', 'type': 'Run/Cardio',
                          'notes': f'{length} min on trails at conversational effort. Hike steep climbs.'}
                    pm = {'session': 'Easy Recovery Spin', 'type': 'Run/Cardio',
                          'notes': '20–30 min very easy bike spin or relaxed walk.'}
                else:
                    am, pm = build_day(phase_idx, build_idx, wk, dow)
            entry = {'date': d.isoformat(), 'week': wk, 'day': dow,
                     'am': am, 'pm': pm}
            plan[d.isoformat()] = entry
    return plan


def inject_into_html(path, plan):
    with open(path) as f:
        html = f.read()
    m = re.search(r'const DEFAULT_WORKOUT_DATA = (\{.*?\});\n', html, re.DOTALL)
    if not m:
        raise RuntimeError(f'DEFAULT_WORKOUT_DATA not found in {path}')
    new_json = json.dumps(plan, separators=(',', ':'), ensure_ascii=False)
    new_line = f'const DEFAULT_WORKOUT_DATA = {new_json};\n'
    new_html = html[:m.start()] + new_line + html[m.end():]
    with open(path, 'w') as f:
        f.write(new_html)


if __name__ == '__main__':
    plan = generate_plan()
    print(f'Generated {len(plan)} days, weeks '
          f'{min(v["week"] for v in plan.values())}–{max(v["week"] for v in plan.values())}')
    print(f'First: {min(plan)}  Last: {max(plan)}')
    for path in [
        '/Users/justinlannoy/Documents/GIT/workout/strength-cardio.html',
        '/Users/justinlannoy/Documents/GIT/workout/strength-cardio-sites.html',
    ]:
        inject_into_html(path, plan)
        print(f'Updated {path}')
