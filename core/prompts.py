from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """
You are creating Russian ILR-aligned proficiency practice for serious linguists.
Generate realistic Russian reading comprehension material.
Do not mention that this is an official DLPT. It is DLPT-style, ILR-aligned practice.
Return ONLY valid JSON. No markdown. No commentary.
""".strip()

GENERATION_USER_PROMPT = """
Create one Russian reading passage and four English multiple-choice comprehension questions.

Skill: reading
Target ILR level: {level}
Topic domain: {topic}

Requirements:
- Passage must be entirely in Russian.
- Questions and answer choices must be in English.
- Passage should feel like realistic source material: news report, official notice, public statement, interview excerpt, security/social/economic report, accident report, or analytical article.
- Do not make the passage too childish.
- Match difficulty to ILR level.
- Include a mix of question types: main idea, detail, inference, writer intent, cause/effect, sequence, tone, or meaning from context.
- Correct answer must be one of A, B, C, D.
- Evidence must be a short Russian quote or paraphrased evidence from the passage.
- Explanations must be concise and useful for end-of-test review.

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
