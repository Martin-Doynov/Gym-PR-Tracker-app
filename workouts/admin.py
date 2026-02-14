from django.contrib import admin
from .models import Exercise, Workout, WorkoutSet, PersonalRecord


class WorkoutSetInline(admin.TabularInline):
    model = WorkoutSet
    extra = 1


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'description')
    list_filter = ('user',)
    search_fields = ('name',)


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'notes')
    list_filter = ('user', 'date')
    inlines = [WorkoutSetInline]


@admin.register(WorkoutSet)
class WorkoutSetAdmin(admin.ModelAdmin):
    list_display = ('workout', 'exercise', 'set_number', 'reps', 'weight')
    list_filter = ('exercise',)


@admin.register(PersonalRecord)
class PersonalRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'pr_type', 'sets', 'reps', 'weight', 'date', 'is_current', 'is_manual')
    list_filter = ('user', 'exercise', 'pr_type', 'is_current', 'is_manual')
    search_fields = ('exercise__name',)