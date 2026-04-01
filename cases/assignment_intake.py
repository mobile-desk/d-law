"""
Post-assignment client details for lawyers: field schemas per case category.
Stored under case.intake_data["assignment_details"] and assignment_intake_complete.
"""

from __future__ import annotations

from typing import Any

from matching.engine import _normalize_category_slug

# Field: name, label, type (text|textarea|email|tel|select), required, choices (optional), help_text (optional)
COMMON_ANONYMOUS: list[dict[str, Any]] = [
    {
        "name": "contact_full_name",
        "label": "Your full name",
        "type": "text",
        "required": True,
        "help_text": "So your lawyer knows how to address you.",
    },
    {
        "name": "contact_email",
        "label": "Email address",
        "type": "email",
        "required": True,
    },
    {
        "name": "contact_phone",
        "label": "Phone number (WhatsApp preferred if possible)",
        "type": "tel",
        "required": True,
    },
]

COMMON_CONTACT_EXTRA: list[dict[str, Any]] = [
    {
        "name": "contact_phone",
        "label": "Phone number (WhatsApp preferred if possible)",
        "type": "tel",
        "required": True,
        "help_text": "Your lawyer needs a way to reach you.",
    },
]

SCHEMAS: dict[str, list[dict[str, Any]]] = {
    "police_abuse": [
        {
            "name": "police_station_area",
            "label": "Police station or area (if known)",
            "type": "text",
            "required": False,
        },
        {
            "name": "incident_date",
            "label": "Approximate date of incident",
            "type": "text",
            "required": False,
            "help_text": "e.g. “March 2025” or “last week”.",
        },
        {
            "name": "incident_summary",
            "label": "What happened (brief)",
            "type": "textarea",
            "required": True,
        },
        {
            "name": "in_custody_or_summons",
            "label": "Are you in custody, or was a summons issued?",
            "type": "select",
            "required": True,
            "choices": [("", "— Select —"), ("no", "No"), ("custody", "In custody"), ("summons", "Summons / charge"), ("other", "Other / unsure")],
        },
    ],
    "criminal": [
        {
            "name": "charge_or_accusation",
            "label": "Charge or accusation (if any)",
            "type": "select",
            "required": True,
            "choices": [
                ("", "— Select —"),
                ("none", "None / not charged yet"),
                ("theft", "Theft / stealing"),
                ("fraud", "Fraud"),
                ("assault", "Assault / violence"),
                ("drugs", "Drugs / narcotics"),
                ("sexual", "Sexual offence"),
                ("cyber", "Cybercrime"),
                ("other", "Other (describe below)"),
            ],
        },
        {
            "name": "charge_or_accusation_other",
            "label": "Describe the charge or accusation",
            "type": "text",
            "required": False,
            "required_when": {"field": "charge_or_accusation", "value": "other"},
            "help_text": "Required when you choose “Other” above.",
            "conditional_on": {"field": "charge_or_accusation", "value": "other"},
        },
        {
            "name": "court_or_police_station",
            "label": "Court or police station involved (if known)",
            "type": "text",
            "required": False,
        },
        {
            "name": "incident_summary",
            "label": "What happened (brief)",
            "type": "textarea",
            "required": True,
        },
    ],
    "civil": [
        {
            "name": "other_party",
            "label": "Other party (person or organisation, if known)",
            "type": "text",
            "required": False,
        },
        {
            "name": "desired_outcome",
            "label": "What outcome do you want?",
            "type": "textarea",
            "required": True,
        },
        {
            "name": "deadlines",
            "label": "Any deadlines or hearing dates?",
            "type": "textarea",
            "required": False,
        },
    ],
    "domestic_violence": [
        {
            "name": "safe_to_contact",
            "label": "Is it safe for your lawyer to contact you by phone/email?",
            "type": "select",
            "required": True,
            "choices": [("", "— Select —"), ("yes", "Yes"), ("no", "No — use caution"), ("unsure", "Unsure")],
        },
        {
            "name": "incident_summary",
            "label": "What happened (brief)",
            "type": "textarea",
            "required": True,
        },
        {
            "name": "children_involved",
            "label": "Children involved?",
            "type": "select",
            "required": False,
            "choices": [("", "— Select —"), ("no", "No"), ("yes", "Yes"), ("prefer_not", "Prefer not to say")],
        },
    ],
    "human_rights": [
        {
            "name": "rights_issue",
            "label": "Which rights or issues are involved?",
            "type": "textarea",
            "required": True,
        },
        {
            "name": "public_authority",
            "label": "Public body or organisation involved (if any)",
            "type": "text",
            "required": False,
        },
    ],
    "general": [
        {
            "name": "issue_summary",
            "label": "Summarise your issue for your lawyer",
            "type": "textarea",
            "required": True,
        },
        {
            "name": "urgency",
            "label": "How urgent is this?",
            "type": "select",
            "required": True,
            "choices": [
                ("", "— Select —"),
                ("low", "Low"),
                ("medium", "Medium"),
                ("high", "High"),
                ("emergency", "Emergency"),
            ],
        },
    ],
}

def category_slug_for_case(case) -> str:
    raw = (case.category or case.ai_classified_category or "").strip()
    slug = _normalize_category_slug(raw)
    if slug in SCHEMAS:
        return slug
    if slug in ("housing", "tenancy", "landlord", "eviction"):
        return "civil"
    return "general"


CHARGE_OR_ACCUSATION_LABELS: dict[str, str] = {
    "none": "None / not charged yet",
    "theft": "Theft / stealing",
    "fraud": "Fraud",
    "assault": "Assault / violence",
    "drugs": "Drugs / narcotics",
    "sexual": "Sexual offence",
    "cyber": "Cybercrime",
    "other": "Other",
}


def fields_for_case(case, request) -> list[dict[str, Any]]:
    slug = category_slug_for_case(case)
    base = list(SCHEMAS.get(slug, SCHEMAS["general"]))
    if not request.user.is_authenticated:
        return COMMON_ANONYMOUS + base
    user = request.user
    if not (getattr(user, "phone", "") or "").strip():
        return COMMON_CONTACT_EXTRA + base
    return base


def _details(case) -> dict[str, Any]:
    data = case.intake_data or {}
    return dict(data.get("assignment_details") or {})


def assignment_initial_values(case, request) -> dict[str, str]:
    out = {k: str(v) for k, v in _details(case).items() if v is not None}
    if request.user.is_authenticated and not out.get("contact_email"):
        out["contact_email"] = request.user.email or ""
    return out


def field_rows_with_values(case, request, posted: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Each field dict includes \"value\" for templates."""
    initial = assignment_initial_values(case, request)
    fields = fields_for_case(case, request)
    rows: list[dict[str, Any]] = []
    for f in fields:
        name = f["name"]
        if posted is not None:
            val = posted.get(name, "")
        else:
            val = initial.get(name, "")
        rows.append({**f, "value": val})
    return rows


def assignment_detail_rows_for_lawyer(case) -> list[tuple[str, str]]:
    """Human-readable (label, value) for professional case view."""
    details = (case.intake_data or {}).get("assignment_details") or {}
    if not details:
        return []
    label_map: dict[str, str] = {}
    for group in (COMMON_ANONYMOUS, COMMON_CONTACT_EXTRA, *SCHEMAS.values()):
        for f in group:
            label_map[f["name"]] = f["label"]
    rows: list[tuple[str, str]] = []
    for k in sorted(details.keys()):
        v = details.get(k)
        if v is None or (isinstance(v, str) and not str(v).strip()):
            continue
        label = label_map.get(k, k.replace("_", " ").title())
        display = str(v)
        if k == "charge_or_accusation":
            display = CHARGE_OR_ACCUSATION_LABELS.get(display, display)
        rows.append((label, display))
    return rows


def _field_required_ok(f: dict[str, Any], details: dict[str, Any]) -> bool:
    name = f["name"]
    raw = details.get(name)
    val = (raw or "").strip() if isinstance(raw, str) else raw
    rw = f.get("required_when")
    if rw:
        dep = (details.get(rw["field"]) or "").strip()
        if dep == rw["value"]:
            return bool(val and str(val).strip())
        return True
    if not f.get("required"):
        return True
    return val is not None and (not isinstance(val, str) or bool(val.strip()))


def assignment_intake_complete(case, request) -> bool:
    if not (case.intake_data or {}).get("assignment_intake_complete"):
        return False
    fields = fields_for_case(case, request)
    details = _details(case)
    for f in fields:
        if not _field_required_ok(f, details):
            return False
    return True


def merge_assignment_details(case, cleaned: dict[str, str]) -> None:
    data = dict(case.intake_data or {})
    prev = dict(data.get("assignment_details") or {})
    prev.update({k: (v or "").strip() for k, v in cleaned.items()})
    data["assignment_details"] = prev
    data["assignment_intake_complete"] = True
    case.intake_data = data
    case.save(update_fields=["intake_data", "updated_at"])


def validate_post(case, request, posted: dict[str, str]) -> tuple[bool, list[str], dict[str, str]]:
    fields = fields_for_case(case, request)
    errors: list[str] = []
    cleaned: dict[str, str] = {}
    for f in fields:
        name = f["name"]
        val = (posted.get(name) or "").strip()
        cleaned[name] = val
        if f.get("required") and not val:
            errors.append(f"{f['label']} is required.")
    for f in fields:
        rw = f.get("required_when")
        if not rw:
            continue
        if cleaned.get(rw["field"]) == rw["value"] and not cleaned.get(f["name"]):
            errors.append(f"{f['label']} is required when you select that option.")
    return (len(errors) == 0, errors, cleaned)
