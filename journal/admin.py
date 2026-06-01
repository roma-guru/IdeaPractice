from django.contrib import admin

from .models import Comment, Instrument, Recording, SharedRecording, Tag


@admin.register(Instrument)
class InstrumentAdmin(admin.ModelAdmin):
    list_display = ("name", "family")
    search_fields = ("name", "family")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = ("id", "file", "instrument", "recording_type", "idea_stage", "created_at")
    list_filter = ("recording_type", "idea_stage", "instrument", "tags")
    search_fields = ("notes", "location", "mood", "file")
    autocomplete_fields = ("instrument", "tags")
    readonly_fields = ("created_at",)
    filter_horizontal = ("tags",)
    fieldsets = (
        ("File", {"fields": ("file",)}),
        ("Classification", {"fields": ("instrument", "recording_type", "tags", "idea_stage")}),
        ("Details", {"fields": ("duration", "location", "mood", "rating")}),
        ("Flags", {"fields": ("is_practice", "is_idea")}),
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
