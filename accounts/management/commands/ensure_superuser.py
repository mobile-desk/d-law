"""
Create or promote a Django admin user (non-interactive).

Environment (same as createsuperuser --noinput):
  DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD

  python manage.py ensure_superuser

Deploy (idempotent, like populate_lawyer_profiles --bootstrap):
  python manage.py ensure_superuser --bootstrap

  Creates the first superuser only when none exists and the env vars are set;
  otherwise skips without failing the build.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Create or promote an admin from DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD. "
        "Use --bootstrap on deploy to create only when no superuser exists yet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bootstrap",
            action="store_true",
            help=(
                "If no superuser exists yet, create one from env vars. "
                "If any superuser exists, or env is unset, skip quietly (exit 0). "
                "Safe to run on every deploy."
            ),
        )

    def handle(self, *args, **options):
        bootstrap: bool = options["bootstrap"]
        email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD") or ""

        User = get_user_model()

        if bootstrap:
            if User.objects.filter(is_superuser=True).exists():
                self.stdout.write(
                    self.style.WARNING(
                        "ensure_superuser: bootstrap skipped (superuser already exists)."
                    )
                )
                return
            if not email or not password:
                self.stdout.write(
                    self.style.WARNING(
                        "ensure_superuser: bootstrap skipped "
                        "(set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD "
                        "to create the first admin)."
                    )
                )
                return
        else:
            if not email or not password:
                raise CommandError(
                    "Set DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD, then run again."
                )

        self._create_or_promote(User, email, password)

    def _create_or_promote(self, User, email: str, password: str) -> None:
        existing = User.objects.filter(email__iexact=email).first()

        if existing:
            if existing.is_superuser and existing.is_staff:
                self.stdout.write(self.style.WARNING(f"Superuser already exists: {email}"))
                return
            existing.is_superuser = True
            existing.is_staff = True
            existing.set_password(password)
            existing.save()
            self.stdout.write(self.style.SUCCESS(f"Promoted to superuser: {email}"))
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created superuser: {email}"))
