from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Instrument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("family", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("technique", "Technique"),
                            ("rhythm", "Rhythm"),
                            ("mood", "Mood"),
                            ("genre", "Genre"),
                            ("experiment", "Experiment"),
                            ("environment", "Environment"),
                        ],
                        default="experiment",
                        max_length=32,
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Recording",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="recordings/%Y/%m/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("duration", models.DurationField(blank=True, null=True)),
                ("location", models.CharField(blank=True, max_length=200)),
                ("mood", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                (
                    "idea_stage",
                    models.CharField(
                        choices=[
                            ("raw", "Raw"),
                            ("promising", "Promising"),
                            ("needs_work", "Needs work"),
                            ("developed", "Developed"),
                            ("archived", "Archived"),
                        ],
                        default="raw",
                        max_length=20,
                    ),
                ),
                ("rating", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("is_practice", models.BooleanField(default=True)),
                ("is_idea", models.BooleanField(default=False)),
                (
                    "instrument",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recordings",
                        to="journal.instrument",
                    ),
                ),
                ("tags", models.ManyToManyField(blank=True, related_name="recordings", to="journal.tag")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
