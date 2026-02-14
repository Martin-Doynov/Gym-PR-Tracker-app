from django.core.management.base import BaseCommand
from workouts.models import Exercise


DEFAULT_EXERCISES = [
    {"name": "Bench Press", "description": "Barbell chest press on a flat bench."},
    {"name": "Squat", "description": "Barbell back squat."},
    {"name": "Deadlift", "description": "Barbell deadlift from the floor."},
    {"name": "Overhead Press", "description": "Standing barbell shoulder press."},
    {"name": "Barbell Row", "description": "Bent-over barbell row."},
    {"name": "Pull-Up", "description": "Bodyweight pull-up."},
    {"name": "Dip", "description": "Bodyweight or weighted dip."},
    {"name": "Leg Press", "description": "Machine leg press."},
    {"name": "Romanian Deadlift", "description": "Barbell RDL targeting hamstrings."},
    {"name": "Lat Pulldown", "description": "Cable lat pulldown."},
    {"name": "Incline Bench Press", "description": "Barbell press on an incline bench."},
    {"name": "Lunges", "description": "Dumbbell or barbell lunges."},
    {"name": "Bicep Curl", "description": "Dumbbell or barbell curl."},
    {"name": "Tricep Extension", "description": "Cable or dumbbell tricep extension."},
    {"name": "Leg Curl", "description": "Machine hamstring curl."},
    {"name": "Leg Extension", "description": "Machine quad extension."},
    {"name": "Calf Raise", "description": "Standing or seated calf raise."},
    {"name": "Face Pull", "description": "Cable face pull for rear delts."},
    {"name": "Plank", "description": "Core isometric hold."},
    {"name": "Cable Fly", "description": "Cable chest fly."},
]


class Command(BaseCommand):
    help = "Load default global exercises (user=None)."

    def handle(self, *args, **options):
        created_count = 0
        for ex in DEFAULT_EXERCISES:
            _, created = Exercise.objects.get_or_create(
                user=None,
                name=ex["name"],
                defaults={"description": ex["description"]},
            )
            if created:
                created_count += 1
        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} new exercises created, "
            f"{len(DEFAULT_EXERCISES) - created_count} already existed."
        ))