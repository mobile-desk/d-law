"""
AI-guided intake: structured questions, Nigeria-focused rights snippets, category tagging.

LLM priority:
1. Groq (OpenAI-compatible API) — if GROQ_API_KEY is set.
2. Rule-based fallbacks — always available.
"""

import json
import os
import re
import sys
from typing import Any

GROQ_OPENAI_BASE = "https://api.groq.com/openai/v1"


def _groq_print(msg: str) -> None:
    """Visible in `manage.py runserver` terminal (stderr)."""
    print(f"[groq] {msg}", file=sys.stderr, flush=True)


def _groq_error_hint(exc: BaseException) -> None:
    """Extra line when Groq returns 401 / invalid key."""
    text = f"{type(exc).__name__} {exc}".lower()
    if "401" in text or "invalid_api_key" in text or "authentication" in text:
        _groq_print(
            "hint: invalid API key — put GROQ_API_KEY in .env next to manage.py (one line, no quotes). "
            "Restart runserver after saving. New key: https://console.groq.com/keys"
        )

# Category slugs aligned with matching (lawyer specialization strings)
CATEGORIES = (
    "human_rights",
    "criminal",
    "civil",
    "police_abuse",
    "domestic_violence",
    "general",
)

_KEYWORD_MAP = (
    (("police", "detain", "station", "sars", "extortion"), "police_abuse"),
    (("human rights", "fundamental rights", "constitution"), "human_rights"),
    (("domestic", "abuse", "violence", "battery", "spouse"), "domestic_violence"),
    (("theft", "robbery", "robbed", "rob", "stolen", "fraud", "crime", "arrest", "charge"), "criminal"),
    (
        (
            "contract",
            "land",
            "tenant",
            "debt",
            "employment",
            "sack",
            "evict",
            "kicked out",
            "kicking me out",
            "kick me out",
            "leave my home",
            "leave the house",
            "notice to quit",
            "landlord",
            "tenancy",
            "my home",
            "rent",
            "lease",
            "sue",
            "suing",
            "lawsuit",
            "litigation",
        ),
        "civil",
    ),
)


def classify_category(text: str) -> str:
    t = text.lower()
    for keywords, cat in _KEYWORD_MAP:
        if any(k in t for k in keywords):
            return cat
    return "general"


def _groq_api_key() -> str:
    """Strip whitespace, UTF-8 BOM, and surrounding quotes (common .env mistakes)."""
    k = (os.environ.get("GROQ_API_KEY") or "").strip()
    k = k.removeprefix("\ufeff").strip()
    if len(k) >= 2 and k[0] == k[-1] and k[0] in "\"'":
        k = k[1:-1].strip()
    return k


def _groq_key_looks_valid(k: str) -> bool:
    """GroqCloud keys are typically ~56 chars and start with ``gsk_``."""
    return bool(k) and k.startswith("gsk_") and len(k) >= 20


def _groq_model() -> str:
    return (os.environ.get("GROQ_MODEL") or "llama-3.1-8b-instant").strip()


def _intake_system_prompt_json() -> str:
    return (
        "You are a supportive legal information assistant for people in Nigeria. "
        "You are not a lawyer; give general education about rights and next steps. "
        "Write like a calm, caring person — not a form or a call centre script. "
        "Briefly mirror their words or feeling, then ask at most one short follow-up. "
        "Prefer Nigerian context (1999 Constitution, NHRC, police conduct). "
        "If the user wants to sue someone, go to court, get a lawyer, or take formal legal action, "
        "your reply MUST end with a clear sentence telling them they can use this app’s "
        "“Find help” / lawyer-matching step to request a verified lawyer—not as legal advice, "
        "but as a practical next step. "
        "Respond with JSON only: {\"reply\": string, \"category_guess\": one of "
        + json.dumps(list(CATEGORIES))
        + "}"
    )


def _user_seeks_lawyer_or_litigation(text: str) -> bool:
    """True when the user is asking about suing, courts, or getting a lawyer — show assignment CTA."""
    t = text.strip().lower()
    if not t:
        return False
    if re.search(
        r"\b("
        r"sue|suing|sued|lawsuit|litigation|barrister|solicitor|"
        r"legal\s+action|legal\s+representation|file\s+(a\s+)?(suit|case|action)|"
        r"take\s+.{0,40}?\s+to\s+court"
        r")\b",
        t,
        re.I,
    ):
        return True
    if re.search(
        r"\b(need|want|get|hire|find|looking\s+for)\s+(a\s+)?(lawyer|attorney|counsel)\b",
        t,
        re.I,
    ):
        return True
    return any(
        p in t
        for p in (
            "take them to court",
            "take him to court",
            "take her to court",
            "go to court",
            "court case",
            "press charges",
        )
    )


def _assistant_reply_prompts_find_help(reply_text: str) -> bool:
    """Model told the user to use Find help — show the CTA even if keywords on the user side missed."""
    t = reply_text.lower()
    if "find help" in t:
        return True
    if "lawyer matching" in t:
        return True
    if "verified lawyer" in t and ("request" in t or "feature" in t or "app" in t):
        return True
    return False


def _user_asks_help_with_legal_context(
    user_message: str,
    history: list[dict[str, Any]],
    merged: dict[str, Any],
) -> bool:
    """e.g. 'can you help' after user already described eviction, police, etc."""
    t = user_message.lower()
    if not re.search(
        r"\b(can you help|help me|please help|need help|how can you help|what can you do)\b",
        t,
    ):
        return False
    parts = [user_message]
    for m in history[-24:]:
        parts.append(m.get("content", ""))
    for key in ("what_happened", "where", "when", "who_involved"):
        v = merged.get(key)
        if v:
            parts.append(str(v))
    blob = " ".join(parts).lower()
    return any(
        k in blob
        for k in (
            "evict",
            "kicked out",
            "landlord",
            "police",
            "rob",
            "sue",
            "court",
            "house",
            "home",
            "abuse",
            "arrest",
            "stolen",
            "fraud",
            "work",
            "employ",
            "domestic",
            "violence",
            "tenant",
            "lease",
            "rent",
        )
    )


def _history_to_chat_messages(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for m in history[-12:]:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": content})
    return messages


def _parse_intake_llm_json(raw: str, user_text: str) -> tuple[str, str | None]:
    raw = raw.strip()
    try:
        data = json.loads(raw)
        reply = data.get("reply", raw)
        cat = data.get("category_guess")
        if cat not in CATEGORIES:
            cat = classify_category(user_text)
        return str(reply), cat
    except json.JSONDecodeError:
        return raw, classify_category(user_text)


def _groq_reply(user_text: str, history: list[dict[str, Any]]) -> tuple[str, str | None]:
    try:
        from openai import OpenAI
    except ImportError:
        _groq_print("skipped: install the `openai` package (pip install openai)")
        return "", None

    key = _groq_api_key()
    if not key:
        return "", None
    if not _groq_key_looks_valid(key):
        _groq_print(
            "WARN: GROQ_API_KEY should start with gsk_ and come from https://console.groq.com/keys "
            f"(got length {len(key)})."
        )

    model = _groq_model()
    _groq_print(f"intake → chat.completions model={model}")

    client = OpenAI(api_key=key, base_url=GROQ_OPENAI_BASE)
    messages = [{"role": "system", "content": _intake_system_prompt_json()}]
    messages.extend(_history_to_chat_messages(history))
    messages.append({"role": "user", "content": user_text})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.72,
        )
    except Exception as e:
        _groq_print(f"intake ERROR: {e!r}")
        _groq_error_hint(e)
        return "", None
    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        _groq_print("intake WARN: empty model content")
        return "", None
    usage = getattr(resp, "usage", None)
    if usage is not None:
        pt = getattr(usage, "prompt_tokens", None)
        ct = getattr(usage, "completion_tokens", None)
        _groq_print(f"intake OK reply_len={len(raw)} tokens in={pt} out={ct}")
    else:
        _groq_print(f"intake OK reply_len={len(raw)}")
    return _parse_intake_llm_json(raw, user_text)


def llm_configured() -> bool:
    """True if Groq API key is set."""
    return bool(_groq_api_key())


def _pick_variant(seed: str, variants: tuple[str, ...]) -> str:
    if not variants:
        return ""
    n = sum(ord(c) for c in seed) % len(variants)
    return variants[n]


def _rule_based_reply(
    *,
    next_key: str | None,
    merged: dict[str, Any],
    category: str,
    seed: str,
) -> str:
    """Rotating copy so scripted intake feels less like one rigid form."""
    if next_key == "what_happened":
        return _pick_variant(
            seed,
            (
                "Hey — when you’re ready, what happened? A few sentences is fine, and you can stay anonymous.",
                "Take your time. What happened, in your own words? You don’t have to use formal language.",
                "I’m listening. What went on — what would you want someone to understand first?",
            ),
        )
    if next_key == "where":
        wh = (merged.get("what_happened") or "").lower()
        if _mentions_housing_stress(wh):
            return _pick_variant(
                seed,
                (
                    "That sounds really stressful. You mentioned home — which state or city in Nigeria is this tied to?",
                    "Thanks for opening up. Since it’s about your home, where in Nigeria is this happening?",
                    "I hear you. For housing issues, location matters — which state or city should we think about?",
                ),
            )
        return _pick_variant(
            seed,
            (
                "Thanks — where did this happen? A state or city in Nigeria is enough.",
                "Got it. Which part of Nigeria was this — state or city?",
                "Helpful context. Where did this take place (state or city is fine)?",
            ),
        )
    if next_key == "when":
        return _pick_variant(
            seed,
            (
                "And roughly when — yesterday, last week, a month ago, or a year? A ballpark is fine.",
                "When did this happen, about? Even “recently” or “last month” helps.",
                "Timeline next: when would you say this happened?",
            ),
        )
    if next_key == "who_involved":
        return _pick_variant(
            seed,
            (
                "Who was involved — e.g. police, someone you know, a stranger, work? Vague is okay.",
                "Do you know who was involved, or what role they played? “Stranger” or “not sure” is fine.",
                "Last bit on context: who was part of this — you can say unknown if that fits.",
            ),
        )
    # Intake complete — rights + handoff
    return _pick_variant(
        seed,
        (
            f"I appreciate you spelling that out. Something that often comes up for situations like yours "
            f"({category.replace('_', ' ')}) is:\n\n{rights_snippet(category)}\n\n"
            f"If you want, we can try to match you with a verified lawyer or advocate to look at what you’ve shared.",
            f"Thank you — that gives a clearer picture. For context like yours ({category.replace('_', ' ')}), "
            f"people often hear:\n\n{rights_snippet(category)}\n\n"
            f"We can try to connect you with someone qualified if you’d like.",
            f"Thanks for sticking with the questions. Here’s a short note that sometimes applies "
            f"({category.replace('_', ' ')}):\n\n{rights_snippet(category)}\n\n"
            f"If it helps, we can try to find a verified lawyer or advocate to review your situation.",
        ),
    )


def rights_snippet(category: str) -> str:
    snippets = {
        "police_abuse": (
            "In Nigeria, you have the right to dignity and freedom from torture (Constitution). "
            "You may ask why you are being stopped; note officer details if safe. "
            "NHRC and legal aid can help with complaints."
        ),
        "domestic_violence": (
            "Your safety comes first. Consider reaching police or trusted services when safe. "
            "Protection orders and support exist; a lawyer or NGO can guide next steps."
        ),
        "human_rights": (
            "Fundamental rights are in Chapter IV of the 1999 Constitution. "
            "If rights are violated, documentation and timely legal advice matter."
        ),
        "criminal": (
            "If you are accused of an offence, you have rights to fair hearing and legal representation. "
            "Avoid self-incrimination; seek a lawyer as soon as you can."
        ),
        "civil": (
            "Many civil disputes can be resolved through negotiation, mediation, or courts. "
            "Gather documents and timelines; a lawyer can assess your options."
        ),
        "general": (
            "Knowing your rights is the first step. Consider speaking with a verified lawyer "
            "or human rights organisation for guidance tailored to your situation."
        ),
    }
    return snippets.get(category, snippets["general"])


def build_intake_reply(
    *,
    user_message: str,
    intake_data: dict[str, Any],
    message_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Returns dict: reply, category, intake_patch, show_assignment_cta, reply_source (llm|rules)."""
    history = message_history or []

    intake_patch = _infer_intake_patches(user_message, intake_data)
    merged = merge_intake(intake_data, intake_patch)

    raw_llm, ai_cat = _groq_reply(user_message, history)
    base_cat = classify_category(user_message)

    if raw_llm and str(raw_llm).strip():
        reply_text = str(raw_llm).strip()
        reply_source = "llm"
        category = ai_cat or base_cat
    else:
        if _groq_api_key():
            _groq_print("intake → rule-based fallback (Groq unavailable or empty reply)")
        category = base_cat
        next_key = _first_missing_intake_step(merged)
        seed = f"{user_message}|{len(history)}"
        reply_text = _rule_based_reply(
            next_key=next_key,
            merged=merged,
            category=category,
            seed=seed,
        )
        reply_source = "rules"

    intake_complete = _first_missing_intake_step(merged) is None
    show_cta = (
        intake_complete
        or _user_seeks_lawyer_or_litigation(user_message)
        or _user_asks_help_with_legal_context(user_message, history, merged)
        or _assistant_reply_prompts_find_help(reply_text)
    )

    return {
        "reply": reply_text,
        "category": category,
        "intake_patch": intake_patch,
        "show_assignment_cta": show_cta,
        "reply_source": reply_source,
    }


def _mentions_housing_stress(text: str) -> bool:
    t = text.lower()
    return any(
        x in t
        for x in (
            "kicked out",
            "kick out",
            "kicking me out",
            "evict",
            "eviction",
            "landlord",
            "my home",
            "apartment",
            "tenancy",
            "rent",
            "lease",
            "housing",
            "notice to quit",
            "leave my home",
        )
    )


def _is_greeting_or_chitchat(text: str) -> bool:
    """Avoid storing one-line hellos/thanks as the incident narrative."""
    t = text.strip().lower()
    if not t or len(t) > 80:
        return False
    if t in (
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "no",
    ):
        return True
    if re.match(
        r"^(hi|hello|hey|good (morning|afternoon|evening))[\s!.]*$",
        t,
    ):
        return True
    return False


def _should_capture_what_happened(text: str) -> bool:
    """
    Narrative must be captured for short but real reports (e.g. 'I got robbed' is 13 chars;
    the old `len > 15` gate never stored it, so the bot kept repeating the opening question).
    """
    t = text.strip()
    if len(t) < 8:
        return False
    if _is_greeting_or_chitchat(text):
        return False
    tl = t.lower()
    incident_kw = (
        "rob",
        "robbed",
        "robbery",
        "theft",
        "stole",
        "stolen",
        "mugged",
        "assault",
        "police",
        "arrest",
        "detain",
        "sars",
        "abuse",
        "fraud",
        "scam",
        "landlord",
        "evict",
        "kicked",
        "sack",
        "employ",
    )
    if any(k in tl for k in incident_kw):
        return True
    return len(t) >= 12


def _first_missing_intake_step(intake_data: dict[str, Any]) -> str | None:
    for s in ("what_happened", "where", "when", "who_involved"):
        if not intake_data.get(s):
            return s
    return None


def _looks_like_who_answer(text: str) -> bool:
    """Short answers like 'stranger' or 'I don't know' when we're on the who step."""
    t = text.strip()
    if len(t) < 2 or len(t) > 500:
        return False
    if _is_greeting_or_chitchat(text):
        return False
    tl = t.lower()
    if re.match(
        r"^(yesterday|today|last week|last month|this month|recently|20\d{2})\s*$",
        tl,
    ):
        return False
    if re.match(
        r"^(lagos|abuja|kano|ibadan|enugu|kaduna|jos|benin|calabar|port\s*harcourt)\s*$",
        tl,
        re.I,
    ):
        return False
    return True


def _infer_intake_patches(user_message: str, intake_data: dict[str, Any]) -> dict[str, Any]:
    """Extract multiple intake fields from one message when possible."""
    out: dict[str, Any] = {}
    text = user_message.strip()
    if not text:
        return out
    t = text.lower()

    if not intake_data.get("what_happened") and _should_capture_what_happened(text):
        out["what_happened"] = text[:5000]

    if not intake_data.get("where"):
        cities = (
            r"(lagos|abuja|kano|ibadan|port\s+harcourt|enugu|kaduna|calabar|benin|jos|owerri|abeokuta|"
            r"uyo|akure|ilorin)"
        )
        m = re.search(rf"\b{cities}\b", t, re.I)
        if m:
            raw = m.group(1).strip()
            w = re.sub(r"\s+", " ", raw)
            out["where"] = "Port Harcourt" if w.lower().replace(" ", "") == "portharcourt" or w.lower() == "port harcourt" else w.title()
        elif intake_data.get("what_happened") and len(text) < 48:
            if re.match(r"^(lagos|abuja|kano|ibadan|enugu|kaduna|jos|benin|calabar)\s*$", t, re.I):
                out["where"] = text.strip().title()

    if not intake_data.get("when") and re.search(
        r"\b(20\d{2}|yesterday|last week|last month|this month|today|recently)\b", t, re.I
    ):
        out["when"] = text[:500]

    if not intake_data.get("who_involved"):
        who_kw = (
            r"\b(police|officer|officers|employer|landlord|landlady|husband|wife|partner|"
            r"ex[- ]?partner|family|neighbor|neighbour|stranger|strangers|unknown|"
            r"thief|thieves|robber|robbers|attacker|attackers|assailant|perpetrator|"
            r"friend|friends|colleague|coworker|co[- ]?worker|boss|sibling|parent|"
            r"someone i know|acquaintance)\b"
        )
        if re.search(who_kw, t, re.I):
            out["who_involved"] = text[:500]
        elif (
            intake_data.get("what_happened")
            and intake_data.get("where")
            and intake_data.get("when")
            and _looks_like_who_answer(text)
        ):
            # e.g. "stranger", "no one", "I don't know" — not matched by keywords alone
            out["who_involved"] = text[:500]

    return out


def merge_intake(intake_data: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(intake_data)
    out.update({k: v for k, v in patch.items() if v is not None})
    return out


def _rules_case_description(merged: dict[str, Any]) -> str:
    """Offline, labeled summary for `Case.description`."""
    what = (merged.get("what_happened") or "").strip()
    loc = (merged.get("where") or "").strip()
    if loc and what:
        tail = re.compile(rf"[,\s]+{re.escape(loc)}[.\s]*$", re.I)
        what = tail.sub("", what).strip()
    when = (merged.get("when") or "").strip()
    who = (merged.get("who_involved") or "").strip()
    if not any([what, loc, when, who]):
        return ""

    lines: list[str] = []
    if what:
        lines.append("SUMMARY")
        lines.append(what)
    if loc:
        lines.extend(["", "LOCATION", loc])
    if when:
        lines.extend(["", "TIMELINE", when])
    if who:
        lines.extend(["", "PARTIES INVOLVED", who])
    return "\n".join(lines).strip()


def _case_summary_system_prompt() -> str:
    return (
        "You format anonymized legal intake notes for people in Nigeria. "
        "Write a neutral case summary a lawyer could skim. "
        "Use exactly these section headings in ALL CAPS on their own line, then content on the following lines:\n"
        "SUMMARY\n"
        "LOCATION\n"
        "TIMELINE\n"
        "PARTIES\n"
        "Under SUMMARY, 2–4 short sentences in plain English. "
        "If housing/tenancy/landlord/eviction is involved, say so clearly. "
        "If a location (e.g. Abuja) appears anywhere in the notes, repeat it under LOCATION. "
        "If unknown, write 'Not stated yet.' for that section. "
        "Do not give legal advice or predict outcomes."
    )


def _groq_case_summary(merged: dict[str, Any], category: str) -> str | None:
    key = _groq_api_key()
    if not key:
        return None
    if not any(merged.get(k) for k in ("what_happened", "where", "when", "who_involved")):
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None

    model = _groq_model()
    _groq_print(f"case_summary → chat.completions model={model}")

    client = OpenAI(api_key=key, base_url=GROQ_OPENAI_BASE)
    payload = {
        "intake_category": category,
        "what_happened": (merged.get("what_happened") or "")[:8000],
        "where": (merged.get("where") or "")[:500],
        "when": (merged.get("when") or "")[:500],
        "who_involved": (merged.get("who_involved") or "")[:800],
    }
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _case_summary_system_prompt()},
                {
                    "role": "user",
                    "content": "Structure this intake into the required sections:\n"
                    + json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0.25,
        )
    except Exception as e:
        _groq_print(f"case_summary ERROR: {e!r}")
        _groq_error_hint(e)
        return None
    text = (resp.choices[0].message.content or "").strip()
    usage = getattr(resp, "usage", None)
    if usage is not None:
        pt = getattr(usage, "prompt_tokens", None)
        ct = getattr(usage, "completion_tokens", None)
        _groq_print(f"case_summary OK len={len(text)} tokens in={pt} out={ct}")
    else:
        _groq_print(f"case_summary OK len={len(text)}")
    return text or None


def build_case_description(merged: dict[str, Any], category: str) -> str:
    """Structured case description: Groq if configured, else rule-based formatting."""
    if not any(merged.get(k) for k in ("what_happened", "where", "when", "who_involved")):
        return ""
    ai = _groq_case_summary(merged, category)
    if ai:
        return ai
    return _rules_case_description(merged)


def process_intake_post(case, content: str):
    """
    Persist user + AI messages and update case. Returns (case, ai_message, show_assignment_cta).
    """
    from cases.models import Message

    content = (content or "").strip()
    Message.objects.create(case=case, sender=None, content=content, is_ai=False)

    history = [
        {"role": "assistant" if m.is_ai else "user", "content": m.content}
        for m in case.messages.order_by("created_at")
    ]
    result = build_intake_reply(
        user_message=content,
        intake_data=case.intake_data or {},
        message_history=history[:-1],
    )
    merged = merge_intake(case.intake_data or {}, result["intake_patch"])
    case.intake_data = merged
    case.ai_classified_category = result["category"]
    if not case.category:
        case.category = result["category"]
    desc = build_case_description(merged, result["category"])
    if desc:
        case.description = desc
    case.save()

    ai_msg = Message.objects.create(
        case=case,
        sender=None,
        content=result["reply"],
        is_ai=True,
        metadata={
            "category": result["category"],
            "show_assignment_cta": result["show_assignment_cta"],
            "reply_source": result.get("reply_source", "rules"),
        },
    )
    case.refresh_from_db()
    return case, ai_msg, result["show_assignment_cta"]
