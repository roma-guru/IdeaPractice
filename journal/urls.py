from django.urls import path

from .views import (
    recording_detail,
    recording_list,
    recording_peaks,
    recording_share,
    recording_stats,
    recording_upload,
    register,
)

urlpatterns = [
    path("", recording_list, name="recording-list"),
    path("upload/", recording_upload, name="recording-upload"),
    path("<int:pk>/", recording_detail, name="recording-detail"),
    path("<int:pk>/share/", recording_share, name="recording-share"),
    path("<int:pk>/peaks/", recording_peaks, name="recording-peaks"),
    path("stats/", recording_stats, name="recording-stats"),
    path("register/<str:code>/", register, name="register"),
]
