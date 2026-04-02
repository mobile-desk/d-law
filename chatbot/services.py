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
    (
        (
            "police",
            "detain",
            "station",
            "sars",
            "extortion",
            "stop and search",
            "stopped and searched",
            "searched me",
            "checkpoint",
            "roadblock",
            "bribe",
            "harassed by police",
        ),
        "police_abuse",
    ),
    (("human rights", "fundamental rights", "constitution"), "human_rights"),
    (
        (
            "domestic",
            "abuse",
            "violence",
            "battery",
            "spouse",
            "rape",
            "raped",
            "raping",
            "sexual assault",
            "molest",
            "molested",
        ),
        "domestic_violence",
    ),
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
        "When the user describes police, stop-and-search, checkpoints, searches, extortion by officers, "
        "or similar: you MUST include concrete rights information in the same reply—not only questions. "
        "Use a short heading **Your rights (general information)** with bullet points in plain language "
        "(Constitution: dignity, freedom from inhuman treatment; Police Act 2020 principles: powers must be "
        "exercised lawfully; you may ask why you are stopped if it is safe; do not pay illegal bribes; "
        "note officer details if safe; NHRC or official complaints when safe). "
        "Safety first; this is education, not legal advice. "
        "CRITICAL: Never assume facts the user did not state (e.g. do not say they are in court, "
        "have filed a case, or have spoken to police unless they said so). "
        "If the user discloses sexual violence, rape, or assault: lead with empathy and belief; "
        "do not blame or minimise; do not pivot to abstract constitutional trivia. "
        "Mention safety first, then optional reporting, medical evidence, and specialist support in Nigeria "
        "(e.g. Mirabel Centre, Lagos; similar services in other states) in general terms. "
        "Prefer Nigerian context (1999 Constitution, NHRC, police conduct) when relevant. "
        "If the user wants to sue someone, go to court, get a lawyer, or take formal legal action, "
        "your reply MUST end with a clear sentence telling them they can use this app’s "
        "“Find help” / lawyer-matching step to request a verified lawyer—not as legal advice, "
        "but as a practical next step. "
        "Respond with JSON only: {\"reply\": string, \"category_guess\": one of "
        + json.dumps(list(CATEGORIES))
        + "}"
    )


_POLICE_ENCOUNTER_APPENDIX = (
    "Additional instruction for THIS thread: the user may be discussing police contact, stop-and-search, "
    "or a checkpoint. Keep empathy short. Then ALWAYS include the heading **Your rights (general information)** "
    "followed by 3–6 bullet points on Nigerian law in plain language: e.g. right to dignity and freedom from "
    "inhuman treatment (Constitution); police powers must be exercised lawfully (Police Act 2020); you may ask "
    "why you are stopped or what power they rely on if you can do so safely; you should not be forced to pay "
    "illegal bribes; you may note badge numbers or names if safe; you can complain to the NHRC or police "
    "oversight when safe. End with at most one short follow-up question. Do not send empathy-only replies."
)


def _conversation_about_police(user_text: str, history: list[dict[str, Any]]) -> bool:
    """True when recent messages suggest police / stop-and-search so we add the appendix to the system prompt."""
    parts = [user_text or ""]
    for m in history[-20:]:
        parts.append(str(m.get("content", "")))
    blob = " ".join(parts).lower()
    if re.search(r"\b(police|officer|officers|sars|policemen|policeman)\b", blob):
        return True
    if re.search(r"\b(stop\s+and\s+search|stopped\s+and\s+searched)\b", blob):
        return True
    if "searched" in blob and re.search(
        r"\b(me|us|my|our|bag|phone|car|vehicle|pocket|body|room)\b", blob
    ):
        return True
    if re.search(r"\b(checkpoint|roadblock|detained|police station|extortion|bribe|harass)\b", blob):
        return True
    if "stopped" in blob and (
        "police" in blob or "officer" in blob or "search" in blob or "checkpoint" in blob
    ):
        return True
    return False


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


def _strip_trailing_json_artifact(text: str) -> str:
    """If the model echoed JSON after prose, or mixed formats, hide it from the user."""
    if not text:
        return text
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s.startswith("{") and ("reply" in s or "category_guess" in s):
            continue
        if s == "}" or s == "{":
            continue
        out.append(line)
    cleaned = "\n".join(out).strip()
    return cleaned or text


def _parse_intake_llm_json(raw: str, user_text: str) -> tuple[str, str | None]:
    raw = raw.strip()
    data: dict[str, Any] | None = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                data = None
    if data is not None:
        reply = data.get("reply", raw)
        cat = data.get("category_guess")
        if cat not in CATEGORIES:
            cat = classify_category(user_text)
        return str(reply).strip(), cat
    fallback = _strip_trailing_json_artifact(raw)
    return fallback, classify_category(user_text)


def _discloses_sexual_violence_crisis(text: str) -> bool:
    """High-risk disclosures: use a fixed template instead of the LLM."""
    t = text.lower()
    if not t:
        return False
    if re.search(
        r"\b(rape|raped|raping|rapist|sexual assault|sexually assaulted|"
        r"defiled|defilement|molested|molestation|groped|forced sex|"
        r"non-?consensual)\b",
        t,
        re.I,
    ):
        return True
    if "rape" in t or "raped" in t:
        return True
    return False


def _crisis_sexual_violence_reply() -> str:
    return (
        "I'm really sorry you went through this. What happened to you is serious, and it's not your fault.\n\n"
        "If you're in immediate danger, please get to a safe place first and contact emergency services or "
        "someone you trust, if you can.\n\n"
        "In Nigeria, survivors can report to the police; a hospital can document injuries for evidence; "
        "and organisations such as **Mirabel Centre** (Lagos) and other women's rights / crisis services "
        "support survivors—search for a rape crisis centre in your state or ask a trusted NGO for a referral. "
        "You are not alone.\n\n"
        "If you're ready, you can say whether you're in a safe place right now, and which state or city you're in "
        "(only what feels safe to share). This app is not a substitute for a lawyer or counsellor—"
        "when you're ready, you can use **Find help** to request a verified professional."
    )


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
    system_text = _intake_system_prompt_json()
    if _conversation_about_police(user_text, history):
        system_text = system_text + "\n\n" + _POLICE_ENCOUNTER_APPENDIX
    messages = [{"role": "system", "content": system_text}]
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
        loc = _pick_variant(
            seed,
            (
                "Thanks — where did this happen? A state or city in Nigeria is enough.",
                "Got it. Which part of Nigeria was this — state or city?",
                "Helpful context. Where did this take place (state or city is fine)?",
            ),
        )
        if category == "police_abuse" or _what_happened_suggests_police(wh):
            rights = (
                "**Your rights (general information):** In Nigeria your dignity is protected under the Constitution; "
                "police powers (including stop-and-search) must be exercised lawfully under the Police Act 2020. "
                "You should not be forced to pay illegal bribes. If it is safe, note officer or vehicle details; "
                "you can complain to the NHRC or official police channels later.\n\n"
            )
            return rights + loc
        return loc
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
            "**Your rights (general information)** — In Nigeria: you have rights to dignity and freedom from "
            "inhuman or degrading treatment (1999 Constitution). Police powers—including stop-and-search—must be "
            "exercised lawfully (Police Act 2020). You may ask why you are stopped or what power is being used, "
            "if you can do so calmly and safely. You should not be forced to pay illegal bribes or “fees.” "
            "If it is safe, note officer names, badges, or vehicle numbers. You can lodge complaints with the "
            "National Human Rights Commission or through official police complaint channels when it is safe. "
            "This is general education, not legal advice."
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

    if _discloses_sexual_violence_crisis(user_message):
        cat = classify_category(user_message)
        if cat not in ("domestic_violence", "human_rights"):
            cat = "human_rights"
        return {
            "reply": _crisis_sexual_violence_reply(),
            "category": cat,
            "intake_patch": intake_patch,
            "show_assignment_cta": True,
            "reply_source": "crisis",
        }

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


def _what_happened_suggests_police(wh: str) -> bool:
    t = (wh or "").lower()
    return any(
        k in t
        for k in (
            "police",
            "officer",
            "search",
            "searched",
            "stopped",
            "checkpoint",
            "roadblock",
            "sars",
            "bribe",
            "detain",
            "station",
            "extort",
            "harass",
        )
    )


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
        "rape",
        "raped",
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


def _intake_transcript_summarize_system_prompt() -> str:
    return (
        "You are a legal assistant for lawyers in Nigeria. "
        "You are given a transcript of a conversation between a client and an AI legal guide (not a lawyer). "
        "Write a neutral digest for the assigned lawyer: "
        "what the client says happened, their main concerns, and what they want. "
        "Use a short heading **DIGEST** then 4–8 bullet points. Plain English. "
        "Do not give legal advice or predict outcomes. Do not paste long quotes."
    )


def _groq_summarize_intake_transcript(transcript: str) -> str | None:
    key = _groq_api_key()
    if not key:
        return None
    if not transcript.strip():
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    model = _groq_model()
    _groq_print(f"intake_transcript_summary → chat.completions model={model}")
    client = OpenAI(api_key=key, base_url=GROQ_OPENAI_BASE)
    t = transcript.strip()[:14000]
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _intake_transcript_summarize_system_prompt()},
                {"role": "user", "content": "Summarize this transcript:\n\n" + t},
            ],
            temperature=0.2,
        )
    except Exception as e:
        _groq_print(f"intake_transcript_summary ERROR: {e!r}")
        _groq_error_hint(e)
        return None
    text = (resp.choices[0].message.content or "").strip()
    return text or None


def _rules_fallback_transcript_summary(intake_messages: list) -> str:
    if not intake_messages:
        return ""
    lines = ["**DIGEST** (from Guide chat; structured summary unavailable)", ""]
    for m in intake_messages[-40:]:
        label = "Guide" if m.is_ai else "Client"
        body = (m.content or "").strip().replace("\n", " ")
        if len(body) > 220:
            body = body[:217] + "…"
        lines.append(f"• {label}: {body}")
    return "\n".join(lines).strip()


def refresh_intake_conversation_summary(case) -> None:
    """Rebuilds Case.intake_chat_summary from intake (Guide) messages only."""
    from cases.models import Case as CaseModel
    from cases.threading import intake_thread_messages

    msgs = intake_thread_messages(case)
    if not msgs:
        CaseModel.objects.filter(pk=case.pk).update(intake_chat_summary="")
        return
    parts = []
    for m in msgs:
        label = "Guide" if m.is_ai else "Client"
        parts.append(f"{label}: {m.content}")
    transcript = "\n\n".join(parts)
    text = _groq_summarize_intake_transcript(transcript)
    if not text:
        text = _rules_fallback_transcript_summary(msgs)
    CaseModel.objects.filter(pk=case.pk).update(intake_chat_summary=text)


def process_intake_post(case, content: str, sender=None):
    """
    Persist user + AI messages and update case. Returns (case, ai_message, show_assignment_cta).
    """
    from cases.models import Message
    from cases.threading import THREAD_INTAKE

    content = (content or "").strip()
    Message.objects.create(
        case=case,
        sender=sender,
        content=content,
        is_ai=False,
        metadata={"thread": THREAD_INTAKE},
    )

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
            "thread": THREAD_INTAKE,
            "category": result["category"],
            "show_assignment_cta": result["show_assignment_cta"],
            "reply_source": result.get("reply_source", "rules"),
        },
    )
    case.refresh_from_db()
    refresh_intake_conversation_summary(case)
    return case, ai_msg, result["show_assignment_cta"]
