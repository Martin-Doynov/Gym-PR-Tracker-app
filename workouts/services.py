from collections import defaultdict
from decimal import Decimal

from django.db.models import Max, Count

from .models import PersonalRecord, WorkoutSet


def recalculate_prs(user, exercise):
    """
    Recalculate all automatic PRs for a given user + exercise
    by walking through ALL their WorkoutSets chronologically.

    Manual PRs (is_manual=True) are left untouched.
    """

    # 1. Delete all auto-detected PRs for this user+exercise
    PersonalRecord.objects.filter(
        user=user, exercise=exercise, is_manual=False
    ).delete()

    # 2. Get all sets for this user+exercise, ordered by date then set_number
    all_sets = (
        WorkoutSet.objects
        .filter(workout__user=user, exercise=exercise)
        .select_related('workout')
        .order_by('workout__date', 'set_number')
    )

    if not all_sets.exists():
        return []

    # 3. Group sets by workout date
    workouts_by_date = defaultdict(list)
    for s in all_sets:
        workouts_by_date[s.workout.date].append(s)

    # Trackers for current bests
    best_weight = {}    # key: reps → value: (weight, date)
    best_reps = {}      # key: weight → value: (reps, date)
    best_sets = {}      # key: (reps, weight) → value: (count, date)

    new_prs = []  # collect all PR records to bulk create

    # 4. Walk through dates chronologically
    for date in sorted(workouts_by_date.keys()):
        day_sets = workouts_by_date[date]

        # --- WEIGHT PR: for each rep count, find max weight this day ---
        day_max_weight = {}  # reps → max weight
        for s in day_sets:
            if s.reps not in day_max_weight or s.weight > day_max_weight[s.reps]:
                day_max_weight[s.reps] = s.weight

        for reps, weight in day_max_weight.items():
            prev = best_weight.get(reps)
            if prev is None or weight > prev[0]:
                new_prs.append(PersonalRecord(
                    user=user,
                    exercise=exercise,
                    pr_type='weight',
                    reps=reps,
                    weight=weight,
                    sets=1,
                    date=date,
                    previous_value=prev[0] if prev else None,
                    previous_date=prev[1] if prev else None,
                    is_current=True,  # will fix below
                ))
                best_weight[reps] = (weight, date)

        # --- REP PR: for each weight, find max reps this day ---
        day_max_reps = {}  # weight → max reps
        for s in day_sets:
            if s.weight not in day_max_reps or s.reps > day_max_reps[s.weight]:
                day_max_reps[s.weight] = s.reps

        for weight, reps in day_max_reps.items():
            prev = best_reps.get(weight)
            if prev is None or reps > prev[0]:
                new_prs.append(PersonalRecord(
                    user=user,
                    exercise=exercise,
                    pr_type='reps',
                    reps=reps,
                    weight=weight,
                    sets=1,
                    date=date,
                    previous_value=Decimal(prev[0]) if prev else None,
                    previous_date=prev[1] if prev else None,
                    is_current=True,
                ))
                best_reps[weight] = (reps, date)

        # --- SET PR: count sets with same reps+weight this day ---
        day_set_counts = defaultdict(int)  # (reps, weight) → count
        for s in day_sets:
            day_set_counts[(s.reps, s.weight)] += 1

        for (reps, weight), count in day_set_counts.items():
            prev = best_sets.get((reps, weight))
            if prev is None or count > prev[0]:
                new_prs.append(PersonalRecord(
                    user=user,
                    exercise=exercise,
                    pr_type='sets',
                    reps=reps,
                    weight=weight,
                    sets=count,
                    date=date,
                    previous_value=Decimal(prev[0]) if prev else None,
                    previous_date=prev[1] if prev else None,
                    is_current=True,
                ))
                best_sets[(reps, weight)] = (count, date)

    # 5. Mark only the latest PR per type+context as is_current
    #    Walk backwards — first seen per key is the current one
    seen_weight = set()
    seen_reps = set()
    seen_sets = set()

    for pr in reversed(new_prs):
        if pr.pr_type == 'weight':
            key = pr.reps
            if key in seen_weight:
                pr.is_current = False
            else:
                seen_weight.add(key)
        elif pr.pr_type == 'reps':
            key = pr.weight
            if key in seen_reps:
                pr.is_current = False
            else:
                seen_reps.add(key)
        elif pr.pr_type == 'sets':
            key = (pr.reps, pr.weight)
            if key in seen_sets:
                pr.is_current = False
            else:
                seen_sets.add(key)

    # 6. Bulk create all PR records
    PersonalRecord.objects.bulk_create(new_prs)

    # 7. Return only the current PRs (for toast notifications)
    return [pr for pr in new_prs if pr.is_current]