from django.urls import path

from .views import (
    project_create,
    project_detail,
    project_list,
    recording_detail,
    recording_list,
    recording_peaks,
    recording_stats,
    recording_upload,
    register,
)

urlpatterns = [
    path("", recording_list, name="recording-list"),
    path("upload/", recording_upload, name="recording-upload"),
    path("<int:pk>/", recording_detail, name="recording-detail"),
    path("<int:pk>/peaks/", recording_peaks, name="recording-peaks"),
    path("stats/", recording_stats, name="recording-stats"),
    path("register/<str:code>/", register, name="register"),
    # Projects
    path("projects/", project_list, name="project-list"),
    path("projects/create/", project_create, name="project-create"),
    path("projects/<int:pk>/", project_detail, name="project-detail"),
]
