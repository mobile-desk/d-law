"""Create or update LawyerProfile rows for lawyer users (dev / seeding)."""

from __future__ import annotations

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from lawyers.models import LawyerProfile

User = get_user_model()

SPECIALIZATIONS = [
    "Criminal law",
    "Civil litigation",
    "Family & matrimonial",
    "Employment & labor",
    "Housing & tenancy",
    "Human rights & public interest",
    "Commercial & contracts",
    "Property & land",
]

LOCATIONS = [
    "Lagos",
    "Abuja",
    "Port Harcourt",
    "Kano",
    "Ibadan",
    "Enugu",
    "Benin City",
    "Kaduna",
]

BIOS = [
    "Focus on access to justice and clear communication with clients.",
    "Handles court filings, negotiations, and alternative dispute resolution.",
    "Works with individuals and small businesses on civil matters.",
    "Experience in legal aid and community advocacy.",
    "Advises on documentation, compliance, and dispute strategy.",
]

# Realistic demo names (rotate when --create > len); not real individuals.
DEMO_LAWYER_NAMES: tuple[tuple[str, str], ...] = (
    ("Chinedu", "Okafor"),
    ("Ngozi", "Adeyemi"),
    ("Emeka", "Okonkwo"),
    ("Funke", "Adebayo"),
    ("Ibrahim", "Musa"),
    ("Aisha", "Bello"),
    ("Chioma", "Eze"),
    ("Tunde", "Bakare"),
    ("Yewande", "Ogunleye"),
    ("Adewale", "Soyinka"),
    ("Kemi", "Fashola"),
    ("Obinna", "Nwosu"),
    ("Halima", "Yusuf"),
    ("Segun", "Ajayi"),
    ("Amaka", "Okafor"),
)


def _demo_name_at(index: int) -> tuple[str, str]:
    first, last = DEMO_LAWYER_NAMES[index % len(DEMO_LAWYER_NAMES)]
    return first, last


def _profile_payload(index: int) -> dict:
    i = index % len(SPECIALIZATIONS)
    return {
        "specialization": SPECIALIZATIONS[i],
        "years_experience": 2 + (index % 18),
        "location": LOCATIONS[index % len(LOCATIONS)],
        "is_available": True,
        "rating": round(3.5 + (index % 15) * 0.1, 1),
        "bio": BIOS[index % len(BIOS)],
    }


class Command(BaseCommand):
    help = (
        "Ensure LawyerProfile exists for every user with user_type=lawyer. "
        "Optionally create new demo lawyer accounts. "
        "Use --force to overwrite profiles and reset all lawyer display names to demo names."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--create",
            type=int,
            default=0,
            metavar="N",
            help="Create N new demo lawyer users (email lawyer-seed-*@demo.local) with profiles.",
        )
        parser.add_argument(
            "--password",
            default="demo12345",
            help="Password for newly created demo users (default: demo12345).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Overwrite LawyerProfile fields and set every lawyer user's first/last name "
                "to the built-in demo name list (destructive)."
            ),
        )

    def handle(self, *args, **options):
        create_n: int = options["create"]
        password: str = options["password"]
        force: bool = options["force"]

        created_users = 0
        created_profiles = 0
        updated_profiles = 0
        renamed_users = 0

        base_index = 0
        for n in range(create_n):
            suffix = uuid.uuid4().hex[:8]
            email = f"lawyer-seed-{suffix}@demo.local"
            while User.objects.filter(email=email).exists():
                suffix = uuid.uuid4().hex[:8]
                email = f"lawyer-seed-{suffix}@demo.local"

            first, last = _demo_name_at(n)
            user = User.objects.create_user(
                email,
                password,
                user_type="lawyer",
                first_name=first,
                last_name=last,
                is_verified=True,
            )
            LawyerProfile.objects.create(user=user, **_profile_payload(base_index + n))
            created_users += 1
            created_profiles += 1
            self.stdout.write(self.style.SUCCESS(f"Created user + profile: {email}"))

        base_index += create_n

        skipped = 0
        lawyer_users = User.objects.filter(user_type="lawyer").order_by("pk")
        for idx, user in enumerate(lawyer_users):
            payload = _profile_payload(base_index + idx)
            existing = LawyerProfile.objects.filter(user=user).first()

            if force:
                first, last = _demo_name_at(idx)
                user.first_name = first
                user.last_name = last
                user.save(update_fields=["first_name", "last_name"])
                renamed_users += 1

            if existing is None:
                LawyerProfile.objects.create(user=user, **payload)
                created_profiles += 1
                tag = f"{first} {last}" if force else user.get_full_name() or user.email
                self.stdout.write(self.style.SUCCESS(f"Added profile for {user.email} ({tag})"))
            elif force:
                for key, value in payload.items():
                    setattr(existing, key, value)
                existing.save()
                updated_profiles += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Updated profile & name for {user.email} → {user.first_name} {user.last_name}"
                    )
                )
            else:
                skipped += 1

        if force:
            summary = (
                f"Done. Created {created_users} users, {created_profiles} new profiles, "
                f"{updated_profiles} profiles overwritten, {renamed_users} lawyer names set to demo list."
            )
        else:
            summary = (
                f"Done. Created {created_users} users, {created_profiles} new profiles, "
                f"{updated_profiles} profiles updated, {skipped} skipped (already had a profile)."
            )
        self.stdout.write(self.style.SUCCESS(summary))
