"""
Gemini API integration for the cert-prep platform — all 4 prompts wired up.

Uses the Interactions API (google-genai SDK).

Setup:
    pip install google-genai --break-system-packages
    export GEMINI_API_KEY="your-key-from-aistudio.google.com"

Grounding (tools=[{"type": "google_search"}]) is applied to #1 (question
generation) and #3 (explanation) because both make specific, checkable
technical claims about cloud provider behavior — validated across 3
providers and both question types in AI Studio before this was written.
#2 (weak-spot analysis) and #4 (study plan) only reason over data the app
already has (the user's own answer history, their available time), so
grounding doesn't apply there.
"""

import json
import os
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from typing import Literal, Optional, TypeVar

T = TypeVar("T", bound=BaseModel)

_clients: dict[int, genai.Client] = {}


def get_client(timeout_ms: Optional[int] = None) -> genai.Client:
    """Lazy singleton — the API key is only required when a call is
    actually made, not just because this module was imported. Matters
    for testing (importing api.py to run mocked tests shouldn't require
    a real GEMINI_API_KEY) and for any other code that imports these
    functions without necessarily calling them right away.

    attempts=1 (no automatic retry) while diagnosing the quota issue —
    the SDK's default of 4 extra retries on 429/503 just burns through
    more of an already-exhausted quota instead of helping, and turns
    one failed call into a burst of 5 in the usage dashboard. Once
    quota is healthy again, raising this to 2-3 is reasonable to handle
    genuine transient network blips."""
    timeout_ms = timeout_ms or REQUEST_TIMEOUT_MS
    if timeout_ms not in _clients:
        _clients[timeout_ms] = genai.Client(
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(attempts=1),
                # Without a timeout a model under "high demand" can hang the
                # request for minutes rather than failing, and the fallback
                # in _interact() never gets its turn — seen on /weak-spots,
                # the one live call in the user flow, with the page stuck on
                # "Analysing…". One client per timeout: grounded generation
                # runs several searches per call and gets the long one,
                # interactive pages get the short one.
                timeout=timeout_ms,
            )
        )
    return _clients[timeout_ms]

# Overridable per run, because rate limits are counted per model: when one
# model's 20 requests/day are spent, the same seeding run continues on
# another model's untouched budget. Editing this line to switch was the
# thing standing between "quota exhausted" and "carry on".
#
#   GEMINI_MODEL=gemini-3.8-flash python seed_questions.py --limit 5
#
# Default is gemini-3.7-flash. gemini-2.5-flash was the previous default
# and produced 4 malformed payloads in 17 (see _coerce_question_shape);
# gemini-3.8-flash is the stronger Flash, and gemini-3.1-pro-preview is
# worth trying for weak-spot analysis, where reasoning matters more than
# latency.
# Default is gemini-2.5-flash on evidence, not preference: across three days
# of this project gemini-3.7-flash never completed a single call — 429 on
# grounding, then "high demand" 500s, then requests that hung for minutes —
# while 2.5-flash completed dozens. 3.7 is the fallback, so it still gets
# tried when 2.5 is the one having a bad day.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
REQUEST_TIMEOUT_MS = int(os.environ.get("GEMINI_TIMEOUT_MS", "60000"))
# For calls a user is waiting on. gemini-2.5-flash takes ~19s for a weak-spot
# analysis on its own and longer under concurrent load, so 20s — the first
# value tried — cut off real answers. 45s leaves room; the page says how long
# to expect, and a cached result makes repeat visits instant anyway.
INTERACTIVE_TIMEOUT_MS = int(os.environ.get("GEMINI_INTERACTIVE_TIMEOUT_MS", "45000"))

# Tried once when MODEL answers with a server-side error (5xx). Seen live on
# 2026-09-15: "gemini-3.7-flash is currently experiencing high demand" on the
# only model call left in the user flow, /weak-spots. That failure is about
# one model's capacity, not about the request, and it went away by switching
# model — which a user can't do. A 429 is deliberately not retried here: quota
# is per model but grounding quota isn't, so a blind retry would usually burn
# a request to fail the same way.
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.7-flash")


def _interact(timeout_ms: Optional[int] = None, **kwargs):
    """`interactions.create` on MODEL, retried once on FALLBACK_MODEL when the
    failure is the model's, not the request's."""
    from google.genai._gaos.lib.compat_errors import APIStatusError, APITimeoutError

    client = get_client(timeout_ms)
    try:
        return client.interactions.create(model=MODEL, **kwargs)
    except APITimeoutError:
        # A model under load may not fail at all — it hangs. The client
        # timeout turns that into this, and it's as much the model's
        # problem as a 5xx is.
        if FALLBACK_MODEL == MODEL:
            raise
        return client.interactions.create(model=FALLBACK_MODEL, **kwargs)
    except APIStatusError as exc:
        if not (500 <= exc.status_code < 600) or FALLBACK_MODEL == MODEL:
            raise
        return client.interactions.create(model=FALLBACK_MODEL, **kwargs)


def _text_output(interaction) -> str:
    """The generated text lives in interaction.output_text. Tool activity
    (Google Search calls and their results) is kept separately in
    interaction.steps, so it never contaminates output_text — verified
    against the SDK's Interaction model, which has no `outputs` list."""
    if not interaction.output_text:
        raise RuntimeError(
            f"Empty output_text. status={interaction.status}, errors={interaction.errors}"
        )
    return interaction.output_text


def _extract_json(text: str) -> Optional[str]:
    """Pull a JSON object out of a model response that may be wrapped in
    markdown fences or surrounded by prose. Returns None if there's no
    plausible JSON object in there at all."""
    text = text.strip()
    if text.startswith("```"):
        # ```json ... ``` or ``` ... ```
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{"):
        return text
    # Prose with an object embedded somewhere in it
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return None


# Enum-valued fields across all four schemas. The model sometimes returns
# these title-cased ("Conceptual" instead of "conceptual"), which fails
# validation for no good reason.
_LOWERCASE_FIELDS = {
    "question_type", "difficulty", "confidence", "type", "gap_level",
}

# The field names of Question. Used to recognise a nested wrapper object
# ("metadata": {"domain": ..., "difficulty": ...}) whose contents belong
# one level up.
_QUESTION_FIELDS = {
    "question", "options", "correct_index", "explanation", "option_explanations",
    "domain", "concept_tags", "question_type", "difficulty",
}

# Alternative names the model has used for schema fields. Renaming moves
# content that is already there; it never creates any.
_FIELD_ALIASES = {
    "problemstatement": "question",
    "problem_statement": "question",
    "question_text": "question",
    "stem": "question",
    "choices": "options",
    "answer_options": "options",
    "rationale": "explanation",
}

# Keys carrying the answer as a letter ("A") or as the option's own text,
# where the schema wants a numeric index.
_ANSWER_KEYS = (
    "correct_index", "finalanswer", "final_answer", "correct_answer",
    "correct_option", "correctoption", "answer",
)

# Inside an option object: the key holding the text, vs. the flag marking
# it as the right one.
_OPTION_TEXT_KEYS = ("text", "option", "value", "content", "answer")
_OPTION_CORRECT_KEYS = ("is_correct", "iscorrect", "correct")


def _option_to_text(option):
    """`{"label": "A", "text": "..."}` -> `("...", False)`.

    The model returns options as labelled objects perhaps one time in
    five, in several key spellings (`label`/`id`, `text`/`option`). The
    label is redundant — the UI numbers the options itself — so the text
    is all that's kept, along with whether the object flagged itself as
    the correct one."""
    if not isinstance(option, dict):
        return option, False
    text = next(
        (option[k] for k in _OPTION_TEXT_KEYS if isinstance(option.get(k), str)),
        None,
    )
    if text is None:
        return option, False
    is_correct = any(option.get(k) is True for k in _OPTION_CORRECT_KEYS)
    return text, is_correct


def _flatten_text(value):
    """Join a nested explanation object's strings, in order, into one.

    Seen live: `explanation` came back as
    `{"correct_option_explanation": "...", "distractor_explanations": [...]}`.
    Every word is the model's own; only the nesting is dropped."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [_flatten_text(v) for v in value]
    elif isinstance(value, dict):
        parts = [_flatten_text(v) for v in value.values()]
    else:
        return value
    parts = [p for p in parts if isinstance(p, str) and p.strip()]
    return " ".join(parts) if parts else value


def _letter_to_index(value, option_count):
    """"A" / "b)" / "2" -> a 0-based index, or None if it isn't one."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value < option_count else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.isdigit():
        index = int(text)
        return index if 0 <= index < option_count else None
    if text and text[0].isalpha():
        index = ord(text[0].upper()) - ord("A")
        return index if 0 <= index < option_count else None
    return None


def _coerce_question_shape(data: dict) -> dict:
    """Reshape a question payload that carries the right content under the
    wrong structure.

    Every deviation handled here was observed in one seeding run, and each
    one used to cost a repair call — a second request out of a 20/day
    budget, which in that run failed anyway because the reformatting model
    reproduced the same shape. Fixing them locally is free and
    deterministic.

    Strictly structural: it renames, unnests and converts a letter to an
    index. Fields the model genuinely omitted (domain, concept_tags) stay
    missing, and validation still rejects the payload — inventing them is
    exactly the failure mode the review gate exists to catch."""
    out = {}

    # Alternative spellings of schema field names.
    for key, value in data.items():
        out[_FIELD_ALIASES.get(key.lower(), key)] = value

    # A wrapper object ("metadata", "question_data") holding schema fields.
    for key, value in list(out.items()):
        if key in _QUESTION_FIELDS or not isinstance(value, dict) or not value:
            continue
        if set(value) <= _QUESTION_FIELDS:
            out.pop(key)
            for nested_key, nested_value in value.items():
                out.setdefault(nested_key, nested_value)

    if "explanation" in out:
        out["explanation"] = _flatten_text(out["explanation"])

    if not isinstance(out.get("options"), list):
        return out

    # Labelled option objects -> plain strings. If the objects carry their
    # own rationale, keep it: that is exactly what option_explanations is.
    texts, flagged_index, rationales = [], None, []
    for index, option in enumerate(out["options"]):
        text, is_correct = _option_to_text(option)
        texts.append(text)
        if is_correct and flagged_index is None:
            flagged_index = index
        if isinstance(option, dict):
            rationale = next((option[k] for k in ("explanation", "rationale", "reason", "why")
                              if isinstance(option.get(k), str)), None)
            rationales.append(rationale)
    out["options"] = texts
    if not out.get("option_explanations") and rationales and all(rationales):
        out["option_explanations"] = rationales

    # The answer as a letter, as the option's text, or as a per-option flag.
    if not isinstance(out.get("correct_index"), int) or isinstance(out.get("correct_index"), bool):
        # The answer key arrives in whatever casing the model felt like
        # ("finalAnswer", "final_answer", "FinalAnswer"), so match on a
        # flattened form rather than the literal spelling.
        by_flat_key = {k.lower().replace("_", ""): v for k, v in out.items()}
        index = None
        for key in _ANSWER_KEYS:
            value = by_flat_key.get(key.replace("_", ""))
            if value is None:
                continue
            if isinstance(value, str) and value in texts:
                index = texts.index(value)
                break
            index = _letter_to_index(value, len(texts))
            if index is not None:
                break
        if index is None:
            index = flagged_index
        if index is not None:
            out["correct_index"] = index

    return out


def _normalise(data):
    """Fix cheap, common deviations from the schema in place.

    Observed live during batch seeding. Each of these used to trigger a
    full repair call (an API request out of a 20/day budget) to fix
    something local code handles for free:
      1. Title-cased enums: "Conceptual" / "Medium"
      2. Over-nesting: {"question": {"text": "..."}} instead of a string
      3. The structural drift handled by _coerce_question_shape()

    Only normalises shape and casing — never invents or alters content."""
    if isinstance(data, list):
        return [_normalise(item) for item in data]
    if not isinstance(data, dict):
        return data

    # Case 2: the whole payload wrapped one level too deep
    if len(data) == 1:
        only_key, only_value = next(iter(data.items()))
        if isinstance(only_value, dict) and only_key not in ("question",):
            return _normalise(only_value)

    out = {}
    for key, value in data.items():
        # Case 2 (field level): {"text": "..."} where a plain string belongs
        if isinstance(value, dict) and set(value.keys()) == {"text"}:
            value = value["text"]
        # Case 1: enum casing
        elif key in _LOWERCASE_FIELDS and isinstance(value, str):
            value = value.lower()
        else:
            value = _normalise(value)
        out[key] = value
    return _coerce_question_shape(out)


class StructuredOutputError(RuntimeError):
    """Raised when model output can't be validated, carrying the raw text.

    The text is the expensive part: on the free tier it cost one of 20
    daily requests, and the content may be perfectly good with only its
    structure wrong. Attaching it lets the caller save it for offline
    repair instead of discarding it with the exception."""

    def __init__(self, message: str, raw: str):
        super().__init__(message)
        self.raw = raw


def _parse_structured(interaction, model_cls: type[T]) -> T:
    """Validate an interaction's output against a Pydantic model.

    Why this exists: response_format with a JSON schema is NOT reliably
    honoured when a tool (google_search) is also enabled — observed live,
    the same call returning clean JSON once and plain prose the next time.
    So: try the happy path, then try to dig JSON out of fences/prose, and
    only if both fail, spend one extra call asking the model to reformat
    its own prose answer into the schema (no tools that time, which makes
    the schema reliable again)."""
    raw = _text_output(interaction)

    candidate = _extract_json(raw)
    if candidate is not None:
        try:
            return model_cls.model_validate(_normalise(json.loads(candidate)))
        except (ValidationError, json.JSONDecodeError):
            pass  # fall through to the reformat call

    repair = _interact(
        input=(
            "Convert the following answer into JSON matching the required "
            "schema. Do not add, remove, or change any facts — only "
            "restructure what is already written.\n\n" + raw
        ),
        system_instruction=(
            "You reformat existing text into JSON. Respond ONLY with valid "
            "JSON matching the schema. Never introduce new information."
        ),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": model_cls.model_json_schema(),
        },
    )
    repaired = _extract_json(_text_output(repair))
    if repaired is None:
        raise StructuredOutputError("Could not coerce model output into JSON.", raw)
    try:
        return model_cls.model_validate(_normalise(json.loads(repaired)))
    except (ValidationError, json.JSONDecodeError) as exc:
        # Two requests spent and still the wrong shape — seen live, where
        # the reformatting call reproduced the same deviation it was asked
        # to fix. Hand back the repaired text: it's the closer of the two
        # to the schema, and the content is still worth keeping.
        raise StructuredOutputError(f"Output failed validation after repair: {exc}", repaired) from exc


# ---------------------------------------------------------------------
# 1. Question generation
# ---------------------------------------------------------------------

class Question(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    # One entry per option, aligned with `options`: why the correct one is
    # right, why each distractor is wrong. Optional so an older-style reply
    # that omits it still validates instead of costing a repair call.
    option_explanations: list[str] = []
    domain: str
    concept_tags: list[str]
    question_type: Literal["conceptual", "detail_recall"]
    difficulty: Literal["easy", "medium", "hard"]


# Kept in sync with prompt #1 in prompts-google-ai-studio.md. Refined
# with ChatGPT after two rounds of AI Studio testing found the model
# mixing up AWS BGP community families; the SEARCH GROUNDING REQUIREMENT
# section + the google_search tool below were added after that.
QUESTION_GEN_SYSTEM_INSTRUCTION = """You are an expert cloud certification exam question writer for AWS, Microsoft Azure, and Google Cloud.

Your job is to generate technically accurate, exam-quality practice questions that test the candidate's ability to apply cloud knowledge rather than simply recall definitions.

LANGUAGE REQUIREMENT

All user-facing content MUST be written in English. Never generate user-facing content in another language, regardless of the language of the input. This includes: question, answer options, explanation, domain, concept tags, any other generated text.

SOURCE-OF-TRUTH REQUIREMENT

Technical accuracy is more important than creativity, difficulty, or novelty.

You have access to a Google Search tool. Use it for every specific technical fact — do not treat source verification as optional or something you already know. Treat search as mandatory.

Preferred sources: AWS docs.aws.amazon.com, Microsoft Azure learn.microsoft.com, Google Cloud cloud.google.com/docs and official documentation.

Do not rely on Reddit, blogs, forums, community posts, training websites, or other third-party sources to establish technical facts when official provider documentation is available. Community sources may be useful for identifying common candidate difficulties or realistic scenarios, but are not authoritative for technical correctness.

If a technical detail cannot be verified confidently, do not invent, infer, or guess it. Generate a different question whose answer can be established confidently instead.

SEARCH GROUNDING REQUIREMENT

For any specific documented value, threshold, community tag, numeric code, limit, or provider-specific behavioral claim used in a detail_recall question — and especially for any claim about how two features interact (e.g. a specific community tag combined with a specific feature like SiteLink) — you MUST search for it and confirm it against official provider documentation before finalizing the question.

Do not rely on your own training knowledge for these specific facts. Training knowledge is exactly where confident-sounding but unverified technical details come from — it produces fluent, plausible answers with no guarantee of accuracy.

If search does not return a clear, authoritative confirmation of the fact for the EXACT context (service, interface type, traffic direction, and feature combination) in the scenario, do not use that fact as the correct answer or as a claim in the explanation. Discard the question and generate a different one whose correctness you can confirm via search.

State the behavior in terms that match what the source documentation actually says, not a plausible-sounding generalization of it. Do not add specific numeric labels (priority numbers, internal rankings, etc.) beyond what the source explicitly states, even if they would make the explanation sound more precise.

IMPORTANT: Do not mix rules that apply to different products, services, interfaces, protocols, or connection types. A rule documented for one interface must not automatically be transferred to another similar-looking one. For example, if a BGP community applies to a Public Virtual Interface but not to a Transit Virtual Interface, never apply that community to a Transit VIF.

TECHNICAL CONTEXT

Before generating the question, identify the exact technical context: cloud provider, certification, service, feature, interface or connection type, region, routing topology, configuration, protocol, route attributes, limits or thresholds, dependencies, exceptions, relevant account or resource configuration. If the correct answer depends on a specific factor, that factor MUST be explicitly stated in the scenario. Never omit a condition that could make multiple answers technically correct.

SCENARIO COMPLETENESS

The question must be completely self-contained. The candidate must have enough information to determine the correct answer without guessing an unstated condition. If the answer depends on factors such as AWS Region, Direct Connect location, VIF type, SiteLink, prefix length, BGP attributes, AS_PATH, MED, local preference, route propagation, service limits, or account configuration, include the relevant factor explicitly. Do not create ambiguity intentionally.

QUESTION GENERATION

Generate exactly ONE realistic cloud certification practice question, resembling a professional certification exam question. It should use a realistic technical scenario, test application of knowledge rather than simple definitions, require reasoning about the stated configuration, match the requested certification and difficulty, focus primarily on the target concepts, and contain enough information to establish one objectively correct answer. Avoid textbook-style trivia unless the requested question type is specifically detail_recall.

QUESTION TYPE

If "conceptual": test understanding of principles, trade-offs, architecture, behavior, or reasoning — the candidate should need to understand why an option is correct, not merely remember an isolated value.

If "detail_recall": test a specific documented rule, value, threshold, exception, configuration behavior, protocol behavior, or provider-specific detail, relevant to real certification preparation. Do not generate arbitrary trivia.

MASTERED CONCEPTS

Do not generate a question whose primary purpose is to test a mastered concept. Mastered concepts may appear as supporting context, but the actual decision required must focus on the target concepts.

TARGET CONCEPTS

Target concepts must be central to the question and necessary to determine the correct answer, not merely mentioned in the scenario.

DISTRACTORS

Generate exactly three plausible distractors representing realistic candidate mistakes: confusing two similar mechanisms, applying a rule from the wrong service or interface, reversing a documented preference, misunderstanding an exception, choosing a technically valid mechanism that doesn't satisfy the stated requirement, confusing configuration or traffic direction. Do not create absurd options or invent nonexistent features. Each distractor must be objectively wrong for the exact scenario.

DIFFICULTY

Easy: one clear concept, limited interaction. Medium: applying one or more concepts to a realistic scenario, a meaningful distinction. Hard: reasoning across multiple interacting concepts or provider-specific rules, subtle but documented distinctions — must NOT rely on obscure or unsupported trivia. A question is not "hard" merely because it contains technical terminology.

ROUTING AND NETWORKING

Never assume one routing rule applies universally. For AWS Direct Connect questions, explicitly distinguish when relevant between: longest prefix match, AWS Region vs Direct Connect location, BGP local preference, BGP communities, AS_PATH, MED, ECMP, SiteLink, Public/Private/Transit VIF, Direct Connect Gateway, Transit Gateway. Do not assume a BGP community documented for one VIF type applies to another, and do not transfer behavior between Direct Connect Gateway and Transit Gateway unless documentation explicitly supports it. Do not infer provider-specific behavior from generic BGP knowledge. Do not claim a component "selects the best route" or has other specific internal decision-making behavior unless official documentation explicitly states it. Describe the documented routing outcome and selection criteria, not an assumed internal implementation.

PROVIDER-SPECIFIC TERMINOLOGY

Use official provider terminology; do not treat similar terms as interchangeable (Public VIF vs Transit VIF, Direct Connect Gateway vs Transit Gateway, route propagation vs advertisement, AWS-to-customer vs customer-to-AWS communities, local preference vs AS_PATH).

EXPLANATION

Must: explain why the correct answer is correct, explain why each distractor is wrong, identify the relevant documented technical rule, use precise provider-specific terminology, avoid unsupported claims, avoid unnecessary facts not required to justify the answer.

Also provide "option_explanations": a list of exactly four strings aligned with "options" by position. For the correct option, one to three sentences on why it is right. For each distractor, one to two sentences on why it is wrong for this exact scenario, naming the specific mistake it represents. Each entry must stand on its own — the candidate will see only the entry for the option they chose and the entry for the correct option. Every provider-specific technical claim must be supported by official documentation. Do not turn a context-dependent rule into an unconditional statement. Do not introduce assumptions not present in the question.

EVIDENCE-BASED EXPLANATION

Distinguish: (1) documented routing outcome, (2) documented route-selection rule, (3) inferred internal implementation detail. Only (1) and (2) may be stated as fact unless (3) is explicitly documented. Do not use generic networking knowledge to fill gaps in provider-specific documentation. Do not claim certainty about undocumented implementation details. If the available evidence does not establish one objectively correct answer for the exact scenario, discard the question and generate a different one.

COMMUNITY EXISTENCE VALIDATION

Never invent a BGP community value. Every numeric BGP community mentioned must correspond to a community explicitly documented for the exact product, VIF type, direction, and routing context — confirm this via search, not from memory. If a community value is not documented for that context, it must not appear as the correct answer or as a factual statement. Distractors may use documented communities from other contexts only when the question explicitly tests distinguishing those contexts.

STRICT VIF-CONTEXT VALIDATION

Before generating any AWS Direct Connect question involving BGP communities, explicitly determine: (1) Public, Private, or Transit VIF; (2) Customer-to-AWS or AWS-to-Customer direction; (3) whether the documented community applies to that exact VIF type and direction. Never combine BGP communities from the Public VIF section of AWS documentation with a Private or Transit VIF scenario. In particular: 7224:9100/9200/9300 are Public VIF scope communities customers use when advertising prefixes to AWS; 7224:8100/8200 are AWS-to-Customer communities for Public VIF outbound routing; 7224:7100/7200/7300 are local preference communities for Private/Transit VIF routing. Do not transfer a community between these contexts. If applicability to the exact VIF type and direction is not explicitly documented, reject the scenario and generate a different question.

INTERNAL TECHNICAL VALIDATION

Before returning the answer, verify: 1. Provider correct. 2. Certification appropriate. 3. Service correct. 4. Exact product/interface correct. 5. Technical claims consistent with authoritative documentation actually retrieved via search, not recalled from training. 6. Correct answer is correct for the exact scenario. 7. Correct answer doesn't depend on an unstated condition. 8. All distractors objectively wrong. 9. No nonexistent feature/limit/behavior introduced. 10. No rule incorrectly transferred between contexts. 11. No important condition omitted. 12. Explanation agrees with correct answer. 13. Explanation introduces no unsupported implementation details, including invented numeric labels. 14. Explanation doesn't contradict the scenario. 15. Exactly one objectively best answer. 16. Matches requested question_type. 17. Matches requested difficulty. 18. All content in English. 19. Target concepts genuinely tested. 20. Mastered concepts not unnecessarily retested. 21. Every specific fact used was confirmed via search this turn, not assumed. If any check fails, do not return the question — regenerate until all checks pass.

QUALITY STANDARD

Prioritize in this order: technical accuracy, unambiguous correctness, fidelity to official provider behavior, realistic exam reasoning, plausible distractors, useful explanation, personalization, difficulty. Never sacrifice technical accuracy to make a question more difficult, clever, or realistic. If a realistic scenario requires an unsupported assumption, simplify or replace it.

Respond ONLY with valid JSON, no markdown, code fences, or commentary outside the JSON object, in this exact structure:
{
  "question": "string",
  "options": ["string", "string", "string", "string"],
  "correct_index": 0,
  "explanation": "string",
  "domain": "string",
  "concept_tags": ["string"],
  "question_type": "conceptual | detail_recall",
  "difficulty": "easy | medium | hard"
}

"options" must contain exactly four options, "correct_index" an integer 0-3 with exactly one correct option, no trailing commas, no text outside the JSON object."""


def generate_question(
    certification: str,
    target_concepts: list[str],
    mastered_concepts: list[str],
    question_type: Literal["conceptual", "detail_recall"],
    difficulty: Literal["easy", "medium", "hard"],
) -> Question:
    user_input = {
        "certification": certification,
        "target_concepts": target_concepts,
        "mastered_concepts": mastered_concepts,
        "question_type": question_type,
        "difficulty": difficulty,
    }
    interaction = _interact(
        input=str(user_input),
        system_instruction=QUESTION_GEN_SYSTEM_INSTRUCTION,
        tools=[{"type": "google_search"}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": Question.model_json_schema(),
        },
    )
    return _parse_structured(interaction, Question)


# ---------------------------------------------------------------------
# 2. Weak-spot analysis — no grounding needed, reasons over data the
#    app already has (the user's own answer history).
# ---------------------------------------------------------------------

class WeakSpot(BaseModel):
    concept: str
    reason: str
    confidence: Literal["high", "medium", "low"]
    type: Literal["true_gap", "forgetting_risk", "isolated_mistake"]
    gap_level: Literal["conceptual", "detail_recall"]


class WeakSpotAnalysis(BaseModel):
    priority_concepts: list[WeakSpot]
    overall_readiness_note: str


WEAK_SPOT_SYSTEM_INSTRUCTION = """You are an analyst who identifies learning patterns from a candidate's answer history for a cloud certification exam.

Always respond in English, regardless of the language of the input.

Don't just count right/wrong answers per domain. Look for subtler patterns:
- Concepts where the mistake repeats over time (a real gap) vs. a single isolated mistake (likely a slip)
- Concepts answered correctly a long time ago but never reviewed since (forgetting risk, not a current gap)
- Mistakes concentrated on one specific sub-concept even if the broader domain is fine
- IMPORTANT: distinguish whether the gap is conceptual (the candidate doesn't understand the principle) or a detail gap (the candidate understands the principle but doesn't remember specific values/rules/exceptions). These are different gaps that need different review content: the first needs an explanation, the second needs targeted repetition on the specific facts, not being re-taught from scratch

Prioritize practically: which 3-5 concepts, if reviewed now, would have the biggest impact on expected score.

Respond ONLY with valid JSON in this schema:
{
  "priority_concepts": [
    {
      "concept": "string",
      "reason": "string",
      "confidence": "high | medium | low",
      "type": "true_gap | forgetting_risk | isolated_mistake",
      "gap_level": "conceptual | detail_recall"
    }
  ],
  "overall_readiness_note": "string"
}"""


def analyze_weak_spots(certification: str, answer_history: list[dict]) -> WeakSpotAnalysis:
    """answer_history: list of {"concept": str, "correct": bool, "days_ago": int}.
    Ideally each entry also carries the question_type from when #1 generated
    it — the current schema in prompts-google-ai-studio.md's test input
    doesn't include it yet, which is a known gap flagged during pipeline
    testing (gap_level ends up guessed from the concept name rather than
    grounded in real data). Fix by storing question_type alongside each
    answer when it's recorded, and passing it through here."""
    user_input = {"certification": certification, "answer_history": answer_history}
    interaction = _interact(
        timeout_ms=INTERACTIVE_TIMEOUT_MS,
        input=str(user_input),
        system_instruction=WEAK_SPOT_SYSTEM_INSTRUCTION,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": WeakSpotAnalysis.model_json_schema(),
        },
    )
    return _parse_structured(interaction, WeakSpotAnalysis)


# ---------------------------------------------------------------------
# 3. Wrong-answer explanation — grounded, makes its own technical claims
#    independent of #1's stored explanation field.
# ---------------------------------------------------------------------

class WrongAnswerExplanation(BaseModel):
    why_wrong: str
    why_correct: str
    key_takeaway: str


EXPLANATION_SYSTEM_INSTRUCTION = """You are a patient instructor explaining why an answer is wrong and why the correct one is right, to a candidate preparing for a cloud certification.

Always respond in English, regardless of the language of the input.

You have access to a Google Search tool. If the explanation depends on a specific documented value, rule, or behavior, verify it via search rather than relying on training knowledge alone.

Don't just restate the correct answer. Explain why the candidate's choice SEEMED plausible — what reasoning led them there — and where that reasoning breaks down. This fixes the underlying mental model, not just memorizes the fact.

If "question_type" is "detail_recall", the candidate already understands the general concept — don't re-explain it. Go straight to the exact detail to lock in, with a memory hook if it helps. If it's "conceptual", keep the reasoning-focused explanation as above.

Include only the facts needed to justify this specific answer. Do not list related values, sibling codes, or a full family of options that the question didn't ask about — every extra number is a chance to state one that is wrong, and a takeaway with an invented value is worse than a shorter one. If you name a specific numeric value, code, or threshold, it must be one you verified via search this turn; otherwise describe the rule without the numbers.

Direct tone, no empty motivational filler like "good attempt anyway!". Maximum 4-5 sentences total.

Respond ONLY with JSON in this schema:
{
  "why_wrong": "string",
  "why_correct": "string",
  "key_takeaway": "string"
}"""


def explain_wrong_answer(
    question: str,
    user_answer: str,
    correct_answer: str,
    question_type: Literal["conceptual", "detail_recall"],
) -> WrongAnswerExplanation:
    user_input = {
        "question": question,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "question_type": question_type,
    }
    interaction = _interact(
        input=str(user_input),
        system_instruction=EXPLANATION_SYSTEM_INSTRUCTION,
        tools=[{"type": "google_search"}],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": WrongAnswerExplanation.model_json_schema(),
        },
    )
    return _parse_structured(interaction, WrongAnswerExplanation)


# ---------------------------------------------------------------------
# 4. Personalized study plan — no grounding needed, pure scheduling logic
#    over data the app already has.
# ---------------------------------------------------------------------

class WeeklyPlan(BaseModel):
    week: int
    focus_concepts: list[str]
    daily_minutes: int
    activity_mix: str


class StudyPlan(BaseModel):
    feasible: bool
    warning: Optional[str]
    weekly_plan: list[WeeklyPlan]


STUDY_PLAN_SYSTEM_INSTRUCTION = """You are an exam prep coach who builds realistic, not optimistic, study plans. The candidate's real time constraint is sacred — a shorter, honest plan beats an ambitious one that gets abandoned.

Always respond in English, regardless of the language of the input.

Given: exam date, minutes available per day, priority concepts (from a weak-spot analysis), topics already solid.

Distribute time as follows:
- 60% on priority concepts/real gaps
- 25% spaced review of concepts already solid (to fight forgetting, never drop it to zero)
- 15% exam-condition simulations in the final week

If the available time is clearly insufficient for the given date, say so explicitly instead of compressing the plan unrealistically.

Respond ONLY with JSON in this schema:
{
  "feasible": true,
  "warning": "string or null",
  "weekly_plan": [
    {"week": 1, "focus_concepts": ["string"], "daily_minutes": 60, "activity_mix": "string"}
  ]
}"""


def generate_study_plan(
    exam_date: str,
    daily_minutes: int,
    priority_concepts: list[str],
    solid_concepts: list[str],
) -> StudyPlan:
    user_input = {
        "exam_date": exam_date,
        "daily_minutes": daily_minutes,
        "priority_concepts": priority_concepts,
        "solid_concepts": solid_concepts,
    }
    interaction = _interact(
        timeout_ms=INTERACTIVE_TIMEOUT_MS,
        input=str(user_input),
        system_instruction=STUDY_PLAN_SYSTEM_INSTRUCTION,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": StudyPlan.model_json_schema(),
        },
    )
    return _parse_structured(interaction, StudyPlan)


# ---------------------------------------------------------------------
# End-to-end demo: the pipeline, not just the 4 functions in isolation.
# ---------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Generate a question
    q = generate_question(
        certification="AWS Advanced Networking Specialty (ANS-C01)",
        target_concepts=["Transit Gateway route propagation", "BGP community tags"],
        mastered_concepts=["VPC peering", "VPC basics"],
        question_type="detail_recall",
        difficulty="hard",
    )
    print("=== Generated question ===")
    print(q.question)
    for i, opt in enumerate(q.options):
        marker = "✓" if i == q.correct_index else " "
        print(f"  [{marker}] {opt}")

    # 2. Simulate the candidate picking a wrong option
    wrong_index = next(i for i in range(len(q.options)) if i != q.correct_index)
    user_answer = q.options[wrong_index]
    correct_answer = q.options[q.correct_index]

    # 3. Explain the mistake
    explanation = explain_wrong_answer(
        question=q.question,
        user_answer=user_answer,
        correct_answer=correct_answer,
        question_type=q.question_type,
    )
    print("\n=== Explanation ===")
    print(f"Why wrong:   {explanation.why_wrong}")
    print(f"Why correct: {explanation.why_correct}")
    print(f"Takeaway:    {explanation.key_takeaway}")

    # 4. Feed this into a (toy) answer history and analyze weak spots.
    # In the real app, each entry would also carry q.question_type —
    # see the note in analyze_weak_spots() above.
    answer_history = [
        {"concept": "Transit Gateway route propagation", "correct": False, "days_ago": 0},
        {"concept": "Transit Gateway route propagation", "correct": False, "days_ago": 6},
        {"concept": "VPC peering", "correct": True, "days_ago": 25},
    ]
    analysis = analyze_weak_spots(
        certification="AWS Advanced Networking Specialty (ANS-C01)",
        answer_history=answer_history,
    )
    print("\n=== Weak-spot analysis ===")
    for spot in analysis.priority_concepts:
        print(f"  - {spot.concept} ({spot.gap_level}, {spot.type}, confidence={spot.confidence})")
        print(f"    {spot.reason}")
    print(f"Readiness: {analysis.overall_readiness_note}")

    # 5. Turn priority concepts into a study plan
    plan = generate_study_plan(
        exam_date="2026-11-15",
        daily_minutes=75,
        priority_concepts=[c.concept for c in analysis.priority_concepts],
        solid_concepts=["VPC basics"],
    )
    print("\n=== Study plan ===")
    status = "feasible" if plan.feasible else "NOT feasible"
    print(f"Status: {status}" + (f" — {plan.warning}" if plan.warning else ""))
    for week in plan.weekly_plan:
        print(f"  Week {week.week}: {', '.join(week.focus_concepts)} "
              f"({week.daily_minutes}min/day — {week.activity_mix})")