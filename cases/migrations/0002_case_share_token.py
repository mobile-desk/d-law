import uuid

from django.db import migrations, models


def fill_share_tokens(apps, schema_editor):
    Case = apps.get_model("cases", "Case")
    for row in Case.objects.filter(share_token__isnull=True):
        row.share_token = uuid.uuid4()
        row.save(update_fields=["share_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("cases", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="case",
            name="share_token",
            field=models.UUIDField(
                db_index=True,
                editable=False,
                help_text="Secret link for anonymous clients (email / share); not the numeric case id.",
                null=True,
            ),
        ),
        migrations.RunPython(fill_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="case",
            name="share_token",
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Secret link for anonymous clients (email / share); not the numeric case id.",
                unique=True,
            ),
        ),
    ]
