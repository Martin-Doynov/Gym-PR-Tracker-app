from django.db import models
from django.conf import settings
from django.db.models.signals import post_delete
from django.dispatch import receiver

class Exercise(models.Model):
    """An exercise that a user can perform (e.g., Bench Press, Squat)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exercises',
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')


    class Meta:
        # Prevent the same user from creating duplicate exercise names
        constraints = [
            models.UniqueConstraint(fields=['user', 'name'], name='unique_exercise_per_user'),
        ]
        ordering = ['name']

    def __str__(self):
        return self.name


class Workout(models.Model):
    """A workout session on a specific date."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workouts',
    )
    date = models.DateField()
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        constraints = [
        models.UniqueConstraint(fields=['user', 'date'], name='one_workout_per_day'),
    ]

    def __str__(self):
        return f"{self.user.username} — {self.date}"


class WorkoutSet(models.Model):
    """A single set within a workout (e.g., Bench Press: 20 reps @ 50kg)."""
    workout = models.ForeignKey(
        Workout,
        on_delete=models.CASCADE,
        related_name='sets',
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='workout_sets',
    )
    set_number = models.PositiveIntegerField()
    reps = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=7, decimal_places=2)

    class Meta:
        ordering = ['set_number']

    def __str__(self):
        return f"{self.exercise.name}: {self.reps} reps @ {self.weight}kg (set {self.set_number})"


class PersonalRecord(models.Model):
    """Tracks personal records per exercise."""

    PR_TYPE_CHOICES = [
        ('weight', 'Weight PR'),   # heaviest weight for a given rep count
        ('reps', 'Rep PR'),        # most reps at a given weight
        ('sets', 'Set PR'),        # most sets of the same reps+weight in one workout
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='personal_records',
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='personal_records',
    )
    pr_type = models.CharField(max_length=10, choices=PR_TYPE_CHOICES)

    # Context fields – meaning depends on pr_type
    reps = models.PositiveIntegerField()
    weight = models.DecimalField(max_digits=7, decimal_places=2)
    sets = models.PositiveIntegerField(default=1)

    # When this PR was achieved
    date = models.DateField()

    # What the previous record was (for "you beat X from Y" display)
    previous_value = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True
    )
    previous_date = models.DateField(null=True, blank=True)

    # Is this the current standing record, or a historical one?
    is_current = models.BooleanField(default=True)

    is_manual = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"PR ({self.get_pr_type_display()}): {self.exercise.name} — {self.sets}x{self.reps}x{self.weight}kg"
    
class ExerciseMedia(models.Model):
    """Images and videos attached to an exercise (superuser only)."""
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='media',
    )
    file = models.FileField(upload_to='exercises/')
    is_video = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        kind = 'Video' if self.is_video else 'Image'
        return f"{kind} for {self.exercise.name}"


class WorkoutMedia(models.Model):
    """Images and videos attached to a workout (superuser only)."""
    workout = models.ForeignKey(
        Workout,
        on_delete=models.CASCADE,
        related_name='media',
    )
    file = models.FileField(upload_to='workouts/')
    is_video = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        kind = 'Video' if self.is_video else 'Image'
        return f"{kind} for {self.workout}"


@receiver(post_delete, sender=ExerciseMedia)
def delete_exercise_media_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)


@receiver(post_delete, sender=WorkoutMedia)
def delete_workout_media_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)