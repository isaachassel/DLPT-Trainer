from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """
You are creating Russian ILR-aligned proficiency practice for serious linguists.
Generate realistic Russian reading comprehension material.
Do not mention that this is an official DLPT. It is DLPT-style, ILR-aligned practice.
Return ONLY valid JSON. No markdown. No commentary.
""".strip()

PASSAGE_LENGTH_GUIDE = {
    "0+": "90-130 Russian words. Simple concrete topic, short sentences, mostly explicit facts.",
    "1": "130-180 Russian words. Everyday or public-information topic with clear chronology and mostly explicit facts.",
    "1+": "180-240 Russian words. Realistic short news/public report with some subordinate clauses and one simple inference.",
    "2": "260-360 Russian words. Substantial news, official, social, economic, security, accident, or policy report. Include several connected facts, cause/effect, and at least one implied conclusion.",
    "2+": "360-500 Russian words. Dense formal report or analytical news piece with competing claims, chronology, indirect wording, and inference across paragraphs.",
    "3": "500-700 Russian words. Advanced authentic-style analytical article, policy briefing, interview excerpt, or investigative report with nuance, implication, author stance, multiple actors, and non-obvious conclusions.",
}

GENERATION_USER_PROMPT = """
Create one Russian reading passage and EXACTLY FOUR English multiple-choice comprehension questions.

Skill: reading
Target ILR level: {level}
Topic domain: {topic}
Passage length and difficulty requirement: {length_guide}

Critical output rules:
- Return ONE complete JSON object only.
- The questions array MUST contain EXACTLY 4 question objects: Q1, Q2, Q3, Q4.
- Every question MUST have choices A, B, C, and D.
- Every question MUST have correct_answer as exactly one letter: A, B, C, or D.
- Do not stop after Q1. Do not summarize the task. Do not add markdown.

Content requirements:
- Passage must be entirely in Russian.
- Questions and answer choices must be in English.
- Passage should feel like realistic source material: news report, official notice, public statement, interview excerpt, security/social/economic report, accident report, or analytical article.
- Do not make the passage too childish or too short.
- The passage_ru field must satisfy the requested length range. Do not use filler or repeat sentences.
- For ILR 2 and above, use multiple paragraphs and make the user connect information across the passage.
- For ILR 2+ and ILR 3, include formal register, nuance, implied meaning, and plausible distractors.
- Include a mix of question types: main idea, detail, inference, writer intent, cause/effect, sequence, tone, or meaning from context.
- Evidence must be a short Russian quote or concise Russian evidence from the passage.
- Explanations must be concise and useful for end-of-test review.
- Do not reveal the correct answer in the question text.
- Keep JSON valid: escape quotation marks inside strings.

Return JSON using this exact structure with all four questions:
{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "English title for internal display",
  "passage_ru": "Russian passage here",
  "questions": [
    {{
      "id": "Q1",
      "question": "English question here",
      "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "explanation": "Why the correct answer is right.",
      "evidence": "Russian evidence from the passage.",
      "question_type": "main idea"
    }},
    {{
      "id": "Q2",
      "question": "English question here",
      "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "B",
      "explanation": "Why the correct answer is right.",
      "evidence": "Russian evidence from the passage.",
      "question_type": "detail"
    }},
    {{
      "id": "Q3",
      "question": "English question here",
      "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "C",
      "explanation": "Why the correct answer is right.",
      "evidence": "Russian evidence from the passage.",
      "question_type": "inference"
    }},
    {{
      "id": "Q4",
      "question": "English question here",
      "choices": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "D",
      "explanation": "Why the correct answer is right.",
      "evidence": "Russian evidence from the passage.",
      "question_type": "cause/effect"
    }}
  ]
}}
""".strip()

QUESTION_REPAIR_PROMPT = """
The previous JSON output did not contain exactly four questions.
Using ONLY the Russian passage below, return the SAME block with EXACTLY FOUR English multiple-choice comprehension questions.

Rules:
- Do not change passage_ru except to copy it exactly.
- Return one valid JSON object only.
- questions must contain Q1, Q2, Q3, Q4.
- Each question must have A, B, C, D choices.
- correct_answer must be exactly A, B, C, or D.
- Include explanation, evidence, and question_type for every question.
- Do not add markdown.

Skill: reading
Target ILR level: {level}
Topic domain: {topic}
Passage title: {title}
Russian passage:
{passage_ru}

Return JSON in the same schema as before.
""".strip()
