from django.urls import path

from .views import (
    recording_detail,
    recording_list,
    recording_share,
    recording_stats,
    recording_upload,
)

urlpatterns = [
    path("", recording_list, name="recording-list"),
    path("upload/", recording_upload, name="recording-upload"),
    path("<int:pk>/", recording_detail, name="recording-detail"),
    path("<int:pk>/share/", recording_share, name="recording-share"),
    path("stats/", recording_stats, name="recording-stats"),
]
