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
Create one Russian reading passage and four English multiple-choice comprehension questions.

Skill: reading
Target ILR level: {level}
Topic domain: {topic}
Passage length and difficulty requirement: {length_guide}

Requirements:
- Passage must be entirely in Russian.
- Questions and answer choices must be in English.
- Passage should feel like realistic source material: news report, official notice, public statement, interview excerpt, security/social/economic report, accident report, or analytical article.
- Do not make the passage too childish or too short.
- For ILR 2 and above, use multiple paragraphs and make the user connect information across the passage.
- For ILR 2+ and ILR 3, include more formal register, nuance, implied meaning, and plausible distractors.
- Match difficulty to ILR level.
- Include a mix of question types: main idea, detail, inference, writer intent, cause/effect, sequence, tone, or meaning from context.
- Correct answer must be one of A, B, C, D.
- Evidence must be a short Russian quote or concise Russian evidence from the passage.
- Explanations must be concise and useful for end-of-test review.
- Do not reveal the correct answer in the question text.

Return JSON using this exact structure:
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
      "question_type": "inference"
    }}
  ]
}}
""".strip()
