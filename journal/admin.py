from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Clip,
    Comment,
    DAWFile,
    Instrument,
    Invite,
    Project,
    ProjectComment,
    ProjectParticipant,
    Recording,
    Tag,
)


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


class ProjectParticipantInline(admin.TabularInline):
    model = ProjectParticipant
    extra = 0
    autocomplete_fields = ("user",)
    readonly_fields = ("added_at",)


class ProjectCommentInline(admin.StackedInline):
    model = ProjectComment
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "creator", "participant_count", "sample_count", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "creator__username")
    readonly_fields = ("created_at", "updated_at")
    inlines = [ProjectParticipantInline, ProjectCommentInline]
    fieldsets = (
        (None, {"fields": ("name", "creator", "logo")}),
        ("Description", {"fields": ("description",), "classes": ("wide",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Participants")
    def participant_count(self, obj: Project) -> int:
        return obj.participants.count()

    @admin.display(description="Samples")
    def sample_count(self, obj: Project) -> int:
        return obj.samples.count()


@admin.register(Recording)
class RecordingAdmin(admin.ModelAdmin):
    list_display = (
        "id", "file", "project", "owner", "instrument", "recording_type",
        "idea_stage", "suno_status", "created_at",
    )
    list_filter = ("recording_type", "idea_stage", "instrument", "tags", "suno_status", "project")
    search_fields = ("notes", "location", "mood", "file", "project__name")
    autocomplete_fields = ("instrument", "tags", "project")
    readonly_fields = ("created_at",)
    filter_horizontal = ("tags",)
    fieldsets = (
        ("File", {"fields": ("file", "project", "owner")}),
        ("Classification", {"fields": ("instrument", "recording_type", "tags", "idea_stage")}),
        ("Details", {"fields": ("duration", "location", "mood", "rating", "bpm", "key")}),
        ("Notes", {"fields": ("notes",)}),
        ("System", {"fields": ("created_at", "suno_status", "suno_raw", "peaks"),
                    "classes": ("collapse",)}),
    )


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "recording", "author", "created_at")
    raw_id_fields = ("recording",)


@admin.register(ProjectComment)
class ProjectCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "author", "created_at")
    raw_id_fields = ("project",)


class ClipInline(admin.TabularInline):
    model = Clip
    extra = 0
    readonly_fields = ("created_at",)


class DAWFileInline(admin.TabularInline):
    model = DAWFile
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Clip)
class ClipAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "uploaded_by", "created_at")
    list_filter = ("project",)
    search_fields = ("title", "notes", "project__name")
    raw_id_fields = ("project",)
    readonly_fields = ("created_at",)


@admin.register(DAWFile)
class DAWFileAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "title", "uploaded_by", "created_at")
    list_filter = ("project",)
    search_fields = ("title", "notes", "project__name")
    raw_id_fields = ("project",)
    readonly_fields = ("created_at",)


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
