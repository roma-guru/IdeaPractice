from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Comment, Instrument, Invite, Recording, SharedRecording, Tag


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "family")
    list_filter = ("family",)
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "file", "instrument", "recording_type", "idea_stage", "suno_status", "created_at"
    )
    list_filter = ("recording_type", "idea_stage", "instrument", "tags", "suno_status")
    search_fields = ("notes", "location", "mood", "file")
    autocomplete_fields = ("instrument", "tags")
    readonly_fields = ("created_at",)
    filter_horizontal = ("tags",)
    fieldsets = (
        ("File", {"fields": ("file",)}),
        ("Classification", {"fields": ("instrument", "recording_type", "tags", "idea_stage")}),
        ("Details", {"fields": ("duration", "location", "mood", "rating")}),
        ("Notes", {"fields": ("notes",)}),
        ("System", {"fields": ("created_at",)}),
    )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "recording", "author", "created_at")
    raw_id_fields = ("recording",)


@admin.register(SharedRecording)
class SharedRecordingAdmin(admin.ModelAdmin):
    list_display = ("recording", "shared_by", "shared_with", "created_at")
    raw_id_fields = ("recording",)


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ("code", "note", "created_by", "created_at", "used_by", "used_at", "invite_link")
    readonly_fields = ("code", "created_at", "used_by", "used_at", "invite_link")
    fields = ("code", "note", "invite_link", "created_at", "used_by", "used_at")

    def save_model(self, request, obj, form, change):  # type: ignore[override]
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Invite link")
    def invite_link(self, obj: Invite) -> str:
        url = reverse("register", args=[obj.code])
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)
