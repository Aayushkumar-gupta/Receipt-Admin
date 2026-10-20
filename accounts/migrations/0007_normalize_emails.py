from django.db import migrations


def normalize_emails(apps, schema_editor):
    User = apps.get_model("auth", "User")
    for user in User.objects.exclude(email=""):
        email = user.email.strip().lower()
        taken = User.objects.filter(username__iexact=email).exclude(pk=user.pk)
        if taken.exists():
            continue
        user.email = email
        user.username = email
        user.save(update_fields=["email", "username"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_profile_text_fields_not_null"),
    ]

    operations = [
        migrations.RunPython(normalize_emails, migrations.RunPython.noop),
    ]
