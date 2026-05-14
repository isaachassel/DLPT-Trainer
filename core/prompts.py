from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """
You create Russian ILR-aligned reading comprehension practice for serious linguists.
You are not creating official DLPT material. You are creating independent DLPT-style practice.
Return ONLY valid JSON. No markdown. No commentary. No code fences.
""".strip()

# One source of truth for passage shape. These values are used by the prompt and by validation.
ILR_STRUCTURE_RULES = {
    # User-selected structure: lower levels should be shorter and not forced into too many paragraphs.
    # 0+/1 = 1 paragraph, 1+/2 = 2 paragraphs, 2+ = 3 paragraphs, 3 = 4 paragraphs.
    "0+": {
        "min_words": 70,
        "max_words": 130,
        "paragraphs": 1,
        "sentences_per_paragraph": "5-8",
        "description": "simple concrete factual report with mostly explicit facts and short sentences",
    },
    "1": {
        "min_words": 100,
        "max_words": 180,
        "paragraphs": 1,
        "sentences_per_paragraph": "7-10",
        "description": "simple connected news-style report with clear sequence and cause/effect",
    },
    "1+": {
        "min_words": 150,
        "max_words": 240,
        "paragraphs": 2,
        "sentences_per_paragraph": "4-6",
        "description": "connected factual report with formal phrasing, cause/effect, and at least one implied relationship",
    },
    "2": {
        "min_words": 220,
        "max_words": 360,
        "paragraphs": 2,
        "sentences_per_paragraph": "6-8",
        "description": "realistic formal news or official-report style with multiple actors, timeline, causes, consequences, and details that must be connected across sentences",
    },
    "2+": {
        "min_words": 330,
        "max_words": 520,
        "paragraphs": 3,
        "sentences_per_paragraph": "5-7",
        "description": "dense formal report with competing explanations, qualifications, indirect implications, and several details spread across the passage",
    },
    "3": {
        "min_words": 480,
        "max_words": 750,
        "paragraphs": 4,
        "sentences_per_paragraph": "5-7",
        "description": "extended analytical article with abstract language, nuance, institutional perspectives, and inference beyond explicit facts",
    },
}

PASSAGE_GENERATION_PROMPT = """
Generate ONE fresh Russian reading passage for ILR-style comprehension practice.

Target ILR level: {level}
Topic domain: {topic}
Generation ID: {generation_id}
Attempt: {attempt}

Required structure for ILR {level}:
- Total length: {min_words}-{max_words} Russian words.
- Paragraph count: exactly {paragraphs} paragraphs.
- Sentence count: {sentences_per_paragraph} sentences per paragraph.
- Style: {description}.

Hard requirements:
- Write the passage in Russian only inside passage_ru.
- Do not write questions in this step.
- Use natural adult Russian, not textbook Russian.
- Make the passage realistic, serious, and suitable for proficiency testing.
- Topic must match the selected domain.
- Do not use bullet points, numbered lists, headings inside passage_ru, or English inside passage_ru.
- Do not summarize. Create a complete passage with enough details for comprehension questions.
- Do not repeat sentences to reach length.
- Do not copy common demo topics such as gas leaks, generic labor-law changes, bridge closures, or rail flooding unless the selected topic clearly demands it.
- If you are about to write fewer than {min_words} Russian words or fewer than {paragraphs} paragraphs, continue expanding before returning JSON.

Return exactly one JSON object with these fields and no extra text.

JSON schema:
{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "English title, 3-8 words",
  "passage_ru": "Full Russian passage here, formatted as exactly {paragraphs} paragraphs separated by newline characters"
}}
""".strip()

PASSAGE_EXPANSION_PROMPT = """
The Russian passage below is too short or has too few paragraphs for ILR-style practice. Expand it while preserving the same event/topic and keeping it natural.

Target ILR level: {level}
Topic domain: {topic}
Required total length: {min_words}-{max_words} Russian words.
Required paragraph count: exactly {paragraphs} paragraphs.
Required sentence count: {sentences_per_paragraph} sentences per paragraph.
Current word count: {current_words}
Current paragraph count: {current_paragraphs}

Expansion requirements:
- Keep the same general scenario, but add realistic context, timeline, official comments, consequences, background, and implications appropriate to ILR {level}.
- Do not add questions.
- Do not use bullet points or lists.
- Do not repeat sentences.
- Russian only inside passage_ru.
- If the passage is still below {min_words} Russian words, continue expanding before returning JSON.

Original title: {title}
Original passage:
{passage_ru}

Return exactly one JSON object and no extra text:
{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "{title}",
  "passage_ru": "Expanded Russian passage here, exactly {paragraphs} paragraphs separated by newline characters"
}}
""".strip()

QUESTION_GENERATION_PROMPT = """
Create EXACTLY FOUR English multiple-choice comprehension questions for the Russian passage below.

Target ILR level: {level}
Topic domain: {topic}
Passage title: {title}
Attempt: {attempt}

Rules:
- Questions must be in English.
- Choices must be in English.
- Base every correct answer only on the Russian passage.
- Include a hidden answer key using correct_answer.
- Include short explanation and Russian evidence for each item.
- Use a mix of question types. Include at least one inference question unless level is 0+.
- Avoid vocabulary-only questions. Test comprehension.
- Distractors must be plausible but clearly wrong based on the passage.
- Return exactly one JSON object. No markdown. No commentary.
- The questions array must contain exactly Q1, Q2, Q3, Q4.

Russian passage:
{passage_ru}

JSON schema:
{{
  "questions": [
    {{
      "id": "Q1",
      "question": "English question 1",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "A",
      "explanation": "Short explanation of why the correct answer is right.",
      "evidence": "Short Russian quote or close paraphrase from the passage.",
      "question_type": "main idea"
    }},
    {{
      "id": "Q2",
      "question": "English question 2",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "B",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "detail"
    }},
    {{
      "id": "Q3",
      "question": "English question 3",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "C",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "inference"
    }},
    {{
      "id": "Q4",
      "question": "English question 4",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "D",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "cause and effect"
    }}
  ]
}}
""".strip()
