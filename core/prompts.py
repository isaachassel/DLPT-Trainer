from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

PROMPT_VERSION = "genai-pipeline-v8"


@dataclass(frozen=True)
class LevelProfile:
    level: str
    discourse: str
    reading_genres: str
    listening_genres: str
    reasoning: str
    language: str
    soft_reading_words: str
    soft_listening_words: str


LEVEL_PROFILES: dict[str, LevelProfile] = {
    "0": LevelProfile(
        "0",
        "isolated symbols, labels, names, numbers, dates, addresses, or extremely short formulaic text; no connected argument",
        "sign, label, schedule fragment, directory entry, price or address notice",
        "single short announcement fragment, number, name, place, or formulaic phrase",
        "recognition only; no inference",
        "very high-frequency words and fixed expressions",
        "5-35",
        "5-30",
    ),
    "0+": LevelProfile(
        "0+",
        "mostly isolated or memorized phrases with minimal connected prose",
        "sign, shop or office notice, simple timetable, short public information",
        "very short practical exchange or announcement",
        "recognition and direct extraction only",
        "formulaic vocabulary; short simple structures",
        "15-65",
        "15-55",
    ),
    "1": LevelProfile(
        "1",
        "very simple connected discourse with a predictable sequence and one clear purpose",
        "message, simple announcement, basic description, short personal or public notice",
        "simple everyday exchange, instruction, or announcement",
        "main idea, obvious detail, simple place/time/action, or sequence",
        "high-frequency vocabulary; mostly simple sentences",
        "60-150",
        "45-120",
    ),
    "1+": LevelProfile(
        "1+",
        "simple two-part discourse with clear time reference, basic cause/effect, and an accessible reference relationship",
        "public announcement, simple narrative, biography, routine workplace information",
        "short report, interview excerpt, service announcement, routine conversation",
        "main idea, routine detail, sequence, reference, simple cause/effect, tightly supported inference",
        "mostly common vocabulary with limited subordinate structure",
        "100-230",
        "75-170",
    ),
    "2": LevelProfile(
        "2",
        "straightforward factual discourse with a clear information hierarchy and predictable organization",
        "news brief, report, social notice, general-reader professional information, routine correspondence",
        "news report, briefing, interview, public-information segment, workplace discussion",
        "main idea, prominent detail, sequence, cause/effect, reference, concrete meaning from context; avoid subtle implication",
        "authentic-like adult Russian with mostly transparent syntax",
        "170-360",
        "120-230",
    ),
    "2+": LevelProfile(
        "2+",
        "denser factual or concrete professional discourse with main and subsidiary ideas, qualifications, and supported implications",
        "longer report, commentary with concrete claims, professional or public-policy material",
        "extended report, interview, explanatory commentary, multi-speaker workplace or public-affairs discussion",
        "gist, important versus secondary detail, concrete inference, speaker/writer intent, attitude, relationship of ideas",
        "varied syntax and less familiar vocabulary recoverable from context",
        "260-470",
        "170-300",
    ),
    "3": LevelProfile(
        "3",
        "adult professional discourse with argumentation, supported opinion, cross-paragraph relationships, implicit intent, or evolving explanation",
        "analysis, editorial commentary, professional report, essay, policy discussion, complex news feature",
        "analytical interview, commentary, professional briefing, debate excerpt, complex report",
        "main argument, relationship of ideas, supported inference, intent, tone, conclusion, evolution of explanation; at most one isolated-detail item",
        "natural professional Russian with abstraction and embedded clauses, but not obscurity for its own sake",
        "330-500",
        "210-330",
    ),
}

QUESTION_TYPE_GUIDANCE = {
    "main idea": "identify the passage's central communicative purpose or controlling idea",
    "prominent detail": "identify a consequential detail, not a trivial number unless level-appropriate",
    "inference": "draw only a directly supported inference; never require cultural or outside knowledge",
    "speaker/writer intent": "identify what the speaker or writer is trying to accomplish",
    "tone or attitude": "identify a supported attitude from wording and discourse, not a guessed emotion",
    "reference": "resolve a pronoun, noun phrase, or discourse reference",
    "sequence": "track the order of events or procedural steps",
    "cause and effect": "identify an explicitly stated or tightly supported causal relationship",
    "relationship of ideas": "identify contrast, concession, support, qualification, or development across parts",
    "meaning from context": "infer a word or phrase meaning from surrounding linguistic context",
}

AUTHORING_SYSTEM = """You are an assessment-content author for an independent Russian proficiency practice application.
You must never reproduce, solicit, reconstruct, or imitate protected DLPT test content. Create original practice material only.
Treat all ILR labels as provisional authoring targets, not calibrated psychometric truth.
Follow the requested JSON schema exactly. Questions and answer choices are in English. The tested passage or transcript is in Russian.
Never use answer letters or a fixed answer-position pattern. Correct answers are represented only by a zero-based index and will be shuffled in Python.
Prioritize genuine discourse complexity, communicative purpose, information hierarchy, cohesion, implication, and reasoning demand over word-count padding.
Do not include markdown, commentary, chain-of-thought, or text outside the structured response."""

VERIFIER_SYSTEM = """You are an independent assessment-item verifier. You did not author the item.
Evaluate only the Russian source text and the English question/choices provided. Do not assume the proposed answer.
Reject ambiguity, unsupported answers, outside knowledge, level mismatch, translation artifacts, answer leakage, and weak distractors.
Return only the requested structured response. Do not reveal private reasoning; provide only concise audit conclusions."""


def _csv(values: Iterable[str] | None, fallback: str) -> str:
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    return ", ".join(cleaned) if cleaned else fallback


def passage_authoring_prompt(
    *,
    skill: str,
    mode: str,
    level: str,
    topics: list[str] | None,
    competencies: list[str] | None,
    novelty_context: list[str] | None,
    generation_nonce: str,
) -> str:
    profile = LEVEL_PROFILES[level]
    genre = profile.reading_genres if skill == "reading" else profile.listening_genres
    soft_length = profile.soft_reading_words if skill == "reading" else profile.soft_listening_words
    medium = "written passage" if skill == "reading" else "spoken transcript"
    strict_rules = (
        "Reading hard limit: no more than 500 Russian words; preserve paragraph structure."
        if skill == "reading"
        else "Listening hard limit: write natural spoken Russian that can be rendered in no more than about 2.5 minutes; avoid long unbroken sentences and TTS-breaking punctuation."
    )
    return f"""Create one original Russian {medium} for a proficiency-practice passage bundle.

REQUEST
- Skill: {skill}
- Product mode: {mode}
- Provisional target ILR: {level}
- Topic guidance: {_csv(topics, 'balanced real-world topics')}
- Competencies likely to be tested later: {_csv(competencies, 'balanced comprehension competencies')}
- Generation nonce: {generation_nonce}

LEVEL PROFILE
- Discourse: {profile.discourse}
- Suitable genres: {genre}
- Expected reasoning: {profile.reasoning}
- Language profile: {profile.language}
- Soft length guidance only: approximately {soft_length} Russian words. Do not pad to hit a number.
- {strict_rules}

CONTENT RULES
- Use a realistic communicative situation and a clear source type.
- The English orientation identifies context/source type without revealing the main idea or any answer.
- The Russian must sound native and internally coherent, with no repeated sentences, contradictions, dangling pronouns, fabricated quotations attributed to real people, or obvious translationese.
- Keep the content safe for a general educational audience and avoid personally identifying information.
- Source type must be synthetic unless verifiable provenance and license are supplied by an administrator; live user generation is synthetic.
- Do not mention DLPT, the app, ILR rules, generation, questions, or answer choices inside the Russian text.
- Avoid close similarity to these existing bank themes/subtopics: {_csv(novelty_context, 'none supplied')}.

METADATA RULES
- Describe register, text mode, cohesion features, reasoning demands, and vocabulary features honestly.
- provisional_difficulty is an authoring estimate on roughly -3.5 to +3.5; it is not calibrated.
- discourse_features and vocabulary_features must describe observable features in this exact passage.
"""


def passage_repair_prompt(*, skill: str, level: str, issues: list[str], candidate_json: str) -> str:
    profile = LEVEL_PROFILES[level]
    return f"""Repair the candidate Russian {skill} passage so it becomes operationally usable.
Target ILR: {level}
Expected discourse: {profile.discourse}
Validation issues: {json.dumps(issues, ensure_ascii=False)}

Candidate JSON:
{candidate_json}

Return a complete replacement object, not a patch. Preserve the broad topic when possible, but rewrite any defective content.
Do not add questions. Do not explain the repair outside the schema.
"""


def passage_audit_prompt(*, skill: str, requested_level: str, candidate_json: str) -> str:
    return f"""Audit this independently generated Russian {skill} passage.
Requested provisional ILR target: {requested_level}

Candidate JSON:
{candidate_json}

Judge whether the Russian is natural, coherent, non-repetitive, level-appropriate, and suitable for comprehension questions.
Check whether the orientation leaks the central answer, whether discourse complexity matches the target, and whether the text appears padded or translated unnaturally.
Choose one estimated ILR band from 0, 0+, 1, 1+, 2, 2+, 3. The estimate is provisional.
Use concise flags and repair notes. Mark acceptable=false for contradictions, incoherent references, severe translation artifacts, answer-revealing orientation, protected-test imitation, or a level mismatch greater than one adjacent half-level.
"""


def question_authoring_prompt(
    *,
    skill: str,
    mode: str,
    level: str,
    desired_count: int,
    competencies: list[str] | None,
    passage_json: str,
) -> str:
    profile = LEVEL_PROFILES[level]
    competency_details = [QUESTION_TYPE_GUIDANCE[c] for c in (competencies or []) if c in QUESTION_TYPE_GUIDANCE]
    return f"""Create exactly {desired_count} English multiple-choice comprehension questions for the Russian {skill} passage below.

REQUEST
- Product mode: {mode}
- Provisional target ILR: {level}
- Level-appropriate reasoning: {profile.reasoning}
- Preferred competencies: {_csv(competencies, 'balanced types')}
- Competency interpretation: {_csv(competency_details, 'use the level profile')}

Passage JSON:
{passage_json}

QUESTION RULES
- Return one top-level object with exactly one key: questions.
- Each question object contains exactly: stem_en, choices, proposed_correct_index, rationale_en, evidence_ru, and question_type.
- question_type must be exactly one of: main idea; prominent detail; inference; speaker/writer intent; tone or attitude; reference; sequence; cause and effect; relationship of ideas; meaning from context.
- Do not return target_ilr, difficulty, IDs, answer letters, validation fields, or any other metadata. The application assigns those in Python.
- Each stem and all four choices are in English.
- proposed_correct_index is zero-based (0-3). Never use answer letters.
- Every correct answer must be supported by the passage alone.
- evidence_ru must be a short exact contiguous Russian quotation from the passage, normally a phrase or clause rather than the whole passage.
- rationale_en explains why the answer is correct and, when useful, why the strongest distractor is wrong.
- Distractors must be plausible misunderstandings yet clearly wrong from the source text.
- Keep answer choices parallel in grammar, comparable in length and specificity, and free of unique wording clues.
- Do not reuse a sentence from the passage as one choice while paraphrasing all others.
- Do not require arithmetic, unstated assumptions, specialist outside knowledge, or cultural trivia.
- Do not ask a vague cause question when the passage presents an early explanation and a later revised explanation; ask what changed or what is currently emphasized.
- Do not ask duration math. Ask "how long" only when the exact duration is explicitly stated.
- Do not duplicate the same competency unless the passage length and target level justify it.
- At ILR 0/0+, use recognition only. At ILR 1/1+, keep inference minimal and concrete. At ILR 2, emphasize factual discourse comprehension. At ILR 2+, include supported hierarchy or implication. At ILR 3, use at most one isolated-detail item and emphasize cross-part relationships.
- The set must cover distinct evidence locations or distinct discourse functions.
"""


def question_repair_prompt(
    *,
    skill: str,
    level: str,
    desired_count: int,
    passage_json: str,
    questions_json: str,
    issues: list[str],
    repair_indices: list[int] | None = None,
) -> str:
    targeted = sorted(set(repair_indices or []))
    if targeted:
        labels = [f"Q{index + 1}" for index in targeted]
        scope = f"""Repair only these failed questions: {', '.join(labels)}.
Return exactly {len(targeted)} replacement question object(s), in the same order as {', '.join(labels)}.
Do not return the valid unchanged questions. The application will merge the replacements into their original positions."""
        output_count = len(targeted)
    else:
        scope = f"Return a complete replacement set containing exactly {desired_count} questions."
        output_count = desired_count
    return f"""Repair English comprehension questions for the supplied Russian {skill} passage.
Target ILR: {level}
Original required bundle size: {desired_count}
Validation and verifier issues: {json.dumps(issues, ensure_ascii=False)}

{scope}

Passage JSON:
{passage_json}

Current question-set JSON:
{questions_json}

Return one top-level object with exactly one key: questions. The questions array must contain exactly {output_count} item(s).
Each question contains exactly stem_en, choices, proposed_correct_index, rationale_en, evidence_ru, and question_type.
question_type must use one exact allowed value: main idea; prominent detail; inference; speaker/writer intent; tone or attitude; reference; sequence; cause and effect; relationship of ideas; meaning from context.
Use zero-based proposed_correct_index only. Never prescribe answer letters.
Do not return target_ilr, difficulty, IDs, answer letters, or validation metadata; the application assigns those in Python.
Every evidence_ru value must be a short exact contiguous quotation copied from the Russian passage.
For no_near_duplicate_choices, rewrite the distractors so each option asserts a materially different proposition; parallel grammar is encouraged, but synonyms or tiny qualifier changes are not enough.
For evidence_in_passage, copy a short exact phrase or clause from the passage character-for-character rather than paraphrasing or reproducing a whole paragraph.
Remove ambiguity, outside knowledge, answer leakage, duplicate competencies, weak distractors, level mismatch, and unsupported rationales.
"""


def blind_verification_prompt(*, passage_ru: str, stem_en: str, choices: list[str], target_level: str, question_type: str) -> str:
    return f"""Blindly verify one comprehension item. The proposed answer is intentionally hidden.
Target ILR: {target_level}
Question type: {question_type}

<RUSSIAN_SOURCE>
{passage_ru}
</RUSSIAN_SOURCE>

<ENGLISH_STEM>
{stem_en}
</ENGLISH_STEM>

<CHOICES_ZERO_BASED>
{json.dumps(choices, ensure_ascii=False)}
</CHOICES_ZERO_BASED>

Select the single best zero-based index from the source alone.
Identify whether a second option is plausibly defensible, whether outside knowledge is required, whether evidence is sufficient, whether the reasoning demand matches the target, and whether any choice leaks the answer through wording/length/specificity.
Copy a short exact contiguous Russian evidence span. Do not paraphrase it. If no
exact span supports the selected choice, return an empty evidence_quote_ru and
set evidence_sufficient=false. Keep the explanation concise.
"""

def blind_verification_batch_prompt(*, passage_ru: str, items: list[dict]) -> str:
    """Blindly verify multiple questions in one independent provider call.

    Each question is evaluated separately. Proposed answer keys are intentionally
    excluded, and each item carries its own independently shuffled choice order.
    """
    return f"""Blindly verify every comprehension item below. The proposed answers are intentionally hidden.
Evaluate each item independently from the Russian source alone. Return exactly one verification object for every question_index.

<RUSSIAN_SOURCE>
{passage_ru}
</RUSSIAN_SOURCE>

<ITEMS_JSON>
{json.dumps(items, ensure_ascii=False)}
</ITEMS_JSON>

For each item:
- select the single best zero-based choice index;
- identify whether a second choice is plausibly defensible;
- reject outside knowledge, insufficient evidence, reasoning-level mismatch, or answer leakage;
- copy only a short exact contiguous Russian evidence span; do not paraphrase it;
- if no exact span supports the answer, return an empty evidence_quote_ru and set evidence_sufficient=false;
- keep the explanation concise.
Do not infer or reconstruct any hidden proposed answer.
"""

