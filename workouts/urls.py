from django.urls import path
from . import views

urlpatterns = [
    path('exercises/', views.exercise_list, name='exercise_list'),
    path('exercises/add/', views.exercise_add, name='exercise_add'),
    path('workout/', views.workout_session, name='workout_today'),
    path('workout/<str:date_str>/', views.workout_session, name='workout_session'),
    path('history/', views.workout_history, name='workout_history'),
    path('api/add-sets/', views.api_add_sets, name='api_add_sets'),
    path('api/delete-set/', views.api_delete_set, name='api_delete_set'),
    path('prs/add/', views.pr_add, name='pr_add'),
    path('prs/', views.pr_list, name='pr_list'),
    path('api/toggle-pr/', views.api_toggle_pr, name='api_toggle_pr'),
    path('exercises/<int:pk>/', views.exercise_detail, name='exercise_detail'),
    path('exercises/<int:pk>/edit/', views.exercise_edit, name='exercise_edit'),
    path('exercises/<int:pk>/delete/', views.exercise_delete, name='exercise_delete'),
    path('logout/', views.logout_view, name='logout'),
    path('media/<path:path>', views.serve_media, name='serve_media'),
    ]