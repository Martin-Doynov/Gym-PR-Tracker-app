import math
from django import forms
from .models import Exercise, Workout, WorkoutSet
import re
from .models import Exercise, PersonalRecord

class ExerciseForm(forms.ModelForm):
    class Meta:
        model = Exercise
        fields = ['name', 'description']

class ManualPRForm(forms.Form):
    exercise = forms.ModelChoiceField(queryset=Exercise.objects.none())
    pr_type = forms.ChoiceField(choices=PersonalRecord.PR_TYPE_CHOICES)
    reps = forms.IntegerField(min_value=1)
    weight = forms.DecimalField(max_digits=7, decimal_places=2, min_value=0)
    sets = forms.IntegerField(min_value=1, initial=1)
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

def parse_sets(text):
    """Parse shorthand like '2x9x5, 3x12x30' into list of dicts.
    
    Format: AMOUNTxREPSxWEIGHT
    Example: 2x9x5 means 2 sets of 9 reps at 5kg.
    
    Struggle reps: 1x15+5+3+4x20
    Effective reps = 15 + math_ceil((5+3+4) / 2) = 15 + 6 = 21
    """
    sets = []
    entries = re.split(r'[,;\s]+', text.strip())
    set_counter = 1
    for entry in entries:
        if not entry:
            continue
        parts = entry.lower().split('x')
        if len(parts) != 3:
            raise ValueError(
                f"Invalid format: '{entry}'. Use AMOUNTxREPSxWEIGHT (e.g. 2x9x5)."
            )
        try:
            amount = int(parts[0])
            weight = float(parts[2])

            # Handle struggle reps: 15+5+3+4
            if '+' in parts[1]:
                rep_parts = parts[1].split('+')
                base_reps = int(rep_parts[0])
                struggle_reps = sum(int(r) for r in rep_parts[1:])
                reps = base_reps + math.ceil(struggle_reps / 2)
            else:
                reps = int(parts[1])
        except ValueError:
            raise ValueError(
                f"Non-numeric value in '{entry}'. Use numbers only (e.g. 2x9x5)."
            )
        for _ in range(amount):
            sets.append({
                'set_number': set_counter,
                'reps': reps,
                'weight': weight,
            })
            set_counter += 1
    return sets