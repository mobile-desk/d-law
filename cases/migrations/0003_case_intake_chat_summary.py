from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0002_case_share_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="intake_chat_summary",
            field=models.TextField(
                blank=True,
                help_text="Short digest of the client’s AI (Guide) chat for the lawyer — not the live thread.",
            ),
        ),
    ]
