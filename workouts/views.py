from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
from .models import Exercise, Workout, WorkoutSet, PersonalRecord
from .forms import ExerciseForm, parse_sets
import datetime
import json
import calendar
from itertools import groupby
from operator import attrgetter
from .services import recalculate_prs
from django.contrib.auth import logout
from django.db.models import Count
from django.core.files.storage import default_storage
from django.http import HttpResponse

@login_required
def pr_add(request):
    """Manually add a personal record."""
    from .forms import ManualPRForm

    if request.method == 'POST':
        form = ManualPRForm(request.POST)
        form.fields['exercise'].queryset = Exercise.objects.filter(
            Q(user=request.user) | Q(user__isnull=True)
        )
        if form.is_valid():
            PersonalRecord.objects.create(
                user=request.user,
                exercise=form.cleaned_data['exercise'],
                pr_type=form.cleaned_data['pr_type'],
                reps=form.cleaned_data['reps'],
                weight=form.cleaned_data['weight'],
                sets=form.cleaned_data['sets'],
                date=form.cleaned_data['date'],
                is_manual=True,
                is_current=True,
            )
            return redirect('pr_list')
    else:
        form = ManualPRForm()
        form.fields['exercise'].queryset = Exercise.objects.filter(
            Q(user=request.user) | Q(user__isnull=True)
        )

    return render(request, 'workouts/pr_add.html', {'form': form})

@login_required
def dashboard(request):
    today = datetime.date.today()

    # Get month/year from query params, default to current month
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year, month = today.year, today.month

    # Clamp to valid range
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    # Exercise filter
    exercise_filter_id = request.GET.get('exercise', '')
    show_prs = request.GET.get('show_prs', '')
    user_exercises = Exercise.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )

    # Get workouts for this month
    workouts_qs = Workout.objects.filter(
        user=request.user,
        date__year=year,
        date__month=month,
    ).prefetch_related('sets__exercise')

    # If filtering by exercise, only include workouts that have that exercise
    if exercise_filter_id:
        try:
            exercise_filter_id = int(exercise_filter_id)
            workouts_qs = workouts_qs.filter(sets__exercise_id=exercise_filter_id).distinct()
        except (ValueError, TypeError):
            exercise_filter_id = ''

    # Build set of dates that have workouts
    workout_dates = set()
    for w in workouts_qs:
        workout_dates.add(w.date.day)

    # Build calendar grid
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(year, month)

    # Previous/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    month_name = calendar.month_name[month]

    # Recent workouts (unfiltered, last 5)
    recent_workouts = Workout.objects.filter(user=request.user).annotate(
    set_count=Count('sets')
).filter(set_count__gt=0)[:5]

    # Filtered workouts list (for exercise filter display)
    filtered_sets = []
    if exercise_filter_id:
        filtered_workouts = workouts_qs.order_by('-date')
        for w in filtered_workouts:
            sets = w.sets.filter(exercise_id=exercise_filter_id).order_by('set_number')
            if sets.exists():
                compact = ', '.join(
                    f"{s.set_number}x{s.reps}x{int(s.weight) if s.weight == int(s.weight) else s.weight}"
                    for s in sets
                )
                filtered_sets.append({
                    'date': w.date,
                    'compact': compact,
                    'sets': list(sets),
                })

    # PR dates for calendar highlighting
    pr_dates = set()
    filtered_prs = []
    if show_prs:
        pr_qs = PersonalRecord.objects.filter(
            user=request.user,
            is_current=True,
            date__year=year,
            date__month=month,
        ).select_related('exercise')

        if exercise_filter_id:
            pr_qs = pr_qs.filter(exercise_id=exercise_filter_id)

        for pr in pr_qs:
            pr_dates.add(pr.date.day)

        # Build display list grouped by date
        prs_by_date = {}
        for pr in pr_qs.order_by('-date'):
            d = pr.date
            if d not in prs_by_date:
                prs_by_date[d] = []
            prs_by_date[d].append(pr)
        filtered_prs = [
            {'date': d, 'prs': prs}
            for d, prs in sorted(prs_by_date.items(), reverse=True)
        ]

    return render(request, 'workouts/dashboard.html', {
        'show_prs': show_prs,
        'pr_dates': pr_dates,
        'filtered_prs': filtered_prs,
        'recent_workouts': recent_workouts,
        'month_days': month_days,
        'workout_dates': workout_dates,
        'year': year,
        'month': month,
        'month_name': month_name,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'today': today,
        'exercises': user_exercises,
        'exercise_filter_id': exercise_filter_id,
        'filtered_sets': filtered_sets,
    })


@login_required
def exercise_list(request):
    exercises = Exercise.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )
    return render(request, 'workouts/exercise_list.html', {
        'exercises': exercises,
    })


@login_required
def exercise_add(request):
    if request.method == 'POST':
        form = ExerciseForm(request.POST, request.FILES)
        if form.is_valid():
            exercise = form.save(commit=False)
            exercise.user = request.user
            form.save()
            return redirect('exercise_list')
    else:
        form = ExerciseForm()
    return render(request, 'workouts/exercise_add.html', {'form': form})


@login_required
def workout_session(request, date_str=None):
    if date_str:
        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            date = datetime.date.today()
    else:
        date = datetime.date.today()

    workout = Workout.objects.filter(user=request.user, date=date).first()
    # Don't create yet — api_add_sets will create on first save
    
    saved_sets = []
    grouped_sets = []
    if workout:
        saved_sets = workout.sets.select_related('exercise').order_by('exercise__name', 'set_number')
        for exercise, sets in groupby(saved_sets, key=attrgetter('exercise')):
            sets_list = list(sets)
            compact = ', '.join(
                f"{s.set_number}x{s.reps}x{int(s.weight) if s.weight == int(s.weight) else s.weight}"
                for s in sets_list
            )
            grouped_sets.append({
                'exercise': exercise,
                'compact': compact,
                'sets': sets_list,
            })

    exercises = Exercise.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )

    return render(request, 'workouts/workout_session.html', {
        'workout': workout,
        'saved_sets': saved_sets,
        'grouped_sets': grouped_sets,
        'exercises': exercises,
        'date': date,
    })


@login_required
@require_POST
def api_add_sets(request):
    try:
        data = json.loads(request.body)
        workout_id = data.get('workout_id')
        exercise_id = data.get('exercise_id')
        sets_text = data.get('sets_text', '')

        workout_date = data.get('workout_date')

        if workout_id:
            workout = get_object_or_404(Workout, pk=workout_id, user=request.user)
        else:
            date = datetime.date.fromisoformat(workout_date)
            workout, _ = Workout.objects.get_or_create(
                user=request.user,
                date=date,
                defaults={'notes': ''},
            )
        
        exercise = Exercise.objects.filter(
            Q(user=request.user) | Q(user__isnull=True)
        ).get(pk=exercise_id)

        parsed = parse_sets(sets_text)
        created_sets = []
        for s in parsed:
            ws = WorkoutSet.objects.create(
                workout=workout,
                exercise=exercise,
                set_number=s['set_number'],
                reps=s['reps'],
                weight=s['weight'],
            )
            created_sets.append({
                'id': ws.id,
                'exercise': exercise.name,
                'set_number': ws.set_number,
                'reps': ws.reps,
                'weight': str(ws.weight),
            })

        # Snapshot existing PRs for today before recalculating
        existing_prs = set(
            PersonalRecord.objects.filter(
                user=request.user, exercise=exercise,
                date=workout.date, is_manual=False,
            ).values_list('pr_type', 'reps', 'weight', 'sets', flat=False)
        )

        # Recalculate PRs for this exercise
        current_prs = recalculate_prs(request.user, exercise)
        pr_list = [
            {
                'type': pr.get_pr_type_display(),
                'exercise': pr.exercise.name,
                'reps': pr.reps,
                'weight': str(pr.weight),
                'sets': pr.sets,
                'date': str(pr.date),
                'previous_value': str(pr.previous_value) if pr.previous_value else None,
                'previous_date': str(pr.previous_date) if pr.previous_date else None,
            }
            for pr in current_prs
            if pr.date == workout.date
            and (pr.pr_type, pr.reps, pr.weight, pr.sets) not in existing_prs
        ]

        return JsonResponse({
            'status': 'ok',
            'sets': created_sets,
            'workout_id': workout.id,
            'prs': pr_list,
        })

    except Exercise.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid exercise.'}, status=400)
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
@require_POST
def api_delete_set(request):
    try:
        data = json.loads(request.body)
        set_id = data.get('set_id')

        ws = get_object_or_404(WorkoutSet, pk=set_id, workout__user=request.user)
        exercise = ws.exercise  # grab before deleting
        workout = ws.workout     # grab before deleting
        ws.delete()

        # If the workout has no sets left, delete it
        if not workout.sets.exists():
            workout.delete()
        # Recalculate PRs since removing a set might shift records
        recalculate_prs(request.user, exercise)
        
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def workout_history(request):
    workouts = Workout.objects.filter(user=request.user).annotate(
    set_count=Count('sets')
).filter(set_count__gt=0).prefetch_related('sets__exercise')
    return render(request, 'workouts/workout_history.html', {
        'workouts': workouts,
    })

@login_required
def pr_list(request):
    """Show current personal records with exercise and type filters."""
    from .models import PersonalRecord

    # Available exercises for the filter dropdown
    user_exercises = Exercise.objects.filter(
        Q(user=request.user) | Q(user__isnull=True)
    )

    # Read filter params
    exercise_filter = request.GET.get('exercise', '')
    type_filter = request.GET.get('type', '')

    # Base queryset: current PRs for this user
    prs_qs = (
        PersonalRecord.objects
        .filter(user=request.user, is_current=True)
        .select_related('exercise')
    )

    # Apply filters
    if exercise_filter:
        try:
            prs_qs = prs_qs.filter(exercise_id=int(exercise_filter))
        except (ValueError, TypeError):
            exercise_filter = ''

    if type_filter in ('weight', 'reps', 'sets'):
        prs_qs = prs_qs.filter(pr_type=type_filter)

    prs_qs = prs_qs.order_by('exercise__name', 'pr_type')

    # Group by exercise for display
    grouped = {}
    for pr in prs_qs:
        name = pr.exercise.name
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(pr)

    return render(request, 'workouts/pr_list.html', {
        'grouped_prs': grouped,
        'exercises': user_exercises,
        'exercise_filter': exercise_filter,
        'type_filter': type_filter,
    })

@login_required
@require_POST
def api_toggle_pr(request):
    """Toggle a manual PR for a specific set."""
    try:
        data = json.loads(request.body)
        set_id = data.get('set_id')

        ws = get_object_or_404(WorkoutSet, pk=set_id, workout__user=request.user)

        # Check if a manual PR already exists for this exact set
        existing = PersonalRecord.objects.filter(
            user=request.user,
            exercise=ws.exercise,
            pr_type='weight',
            reps=ws.reps,
            weight=ws.weight,
            date=ws.workout.date,
            is_manual=True,
        ).first()

        if existing:
            existing.delete()
            return JsonResponse({'status': 'ok', 'pr_active': False})
        else:
            PersonalRecord.objects.create(
                user=request.user,
                exercise=ws.exercise,
                pr_type='weight',
                reps=ws.reps,
                weight=ws.weight,
                sets=1,
                date=ws.workout.date,
                is_manual=True,
                is_current=True,
            )
            return JsonResponse({'status': 'ok', 'pr_active': True})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    

@login_required
def exercise_detail(request, pk):
    """View an exercise's details including photo and description."""
    exercise = get_object_or_404(Exercise, pk=pk)
    # Regular users can only see their own or global exercises
    if exercise.user is not None and exercise.user != request.user and not request.user.is_superuser:
        return redirect('exercise_list')

    can_edit = request.user.is_superuser or exercise.user == request.user
    return render(request, 'workouts/exercise_detail.html', {
        'exercise': exercise,
        'can_edit': can_edit,
    })


@login_required
def exercise_edit(request, pk):
    """Edit an exercise. Superusers can edit any; regular users only their own."""
    exercise = get_object_or_404(Exercise, pk=pk)

    # Permission check
    if not request.user.is_superuser and exercise.user != request.user:
        return redirect('exercise_list')

    if request.method == 'POST':
        form = ExerciseForm(request.POST, request.FILES, instance=exercise)
        if form.is_valid():
            form.save()
            return redirect('exercise_detail', pk=exercise.pk)
    else:
        form = ExerciseForm(instance=exercise)

    return render(request, 'workouts/exercise_edit.html', {
        'form': form,
        'exercise': exercise,
    })


@login_required
def exercise_delete(request, pk):
    """Delete an exercise. Superusers can delete any; regular users only their own."""
    exercise = get_object_or_404(Exercise, pk=pk)

    if not request.user.is_superuser and exercise.user != request.user:
        return redirect('exercise_list')

    if request.method == 'POST':
        exercise.delete()
        return redirect('exercise_list')

    return render(request, 'workouts/exercise_delete.html', {
        'exercise': exercise,
    })

def logout_view(request):
    logout(request)
    return redirect('/login/')

@login_required
def serve_media(request, path):
    """Proxy media files from S3 bucket."""
    try:
        f = default_storage.open(path)
        content = f.read()
        f.close()

        # Determine content type
        if path.lower().endswith('.png'):
            content_type = 'image/png'
        elif path.lower().endswith('.jpg') or path.lower().endswith('.jpeg'):
            content_type = 'image/jpeg'
        elif path.lower().endswith('.gif'):
            content_type = 'image/gif'
        elif path.lower().endswith('.webp'):
            content_type = 'image/webp'
        else:
            content_type = 'application/octet-stream'

        return HttpResponse(content, content_type=content_type)
    except Exception:
        from django.http import Http404
        raise Http404("File not found")
    

@login_required
@require_POST
def api_create_exercise(request):
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()

        if not name:
            return JsonResponse({'status': 'error', 'message': 'Name is required.'}, status=400)

        # Check if it already exists for this user or globally
        existing = Exercise.objects.filter(
            Q(user=request.user) | Q(user__isnull=True),
            name__iexact=name,
        ).first()

        if existing:
            return JsonResponse({'status': 'error', 'message': 'Exercise already exists.'}, status=400)

        exercise = Exercise.objects.create(user=request.user, name=name)
        return JsonResponse({
            'status': 'ok',
            'exercise': {'id': exercise.pk, 'name': exercise.name},
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)