from django.urls import path

from .views import recording_list, recording_upload

urlpatterns = [
    path("", recording_list, name="recording-list"),
    path("upload/", recording_upload, name="recording-upload"),
]
