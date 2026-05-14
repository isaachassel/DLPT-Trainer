from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """
You create Russian ILR-aligned reading comprehension practice for serious linguists.
You are not creating official DLPT material. You are creating independent DLPT-style practice.
Return ONLY valid JSON. No markdown. No commentary. No code fences.
""".strip()

PASSAGE_LENGTH_GUIDE = {
    "0+": "90-140 Russian words. Simple concrete report. Mostly explicit facts. Short sentences.",
    "1": "140-200 Russian words. Simple connected news-style report with clear sequence and cause/effect.",
    "1+": "200-280 Russian words. Connected factual report with some formal phrasing and one implied relationship.",
    "2": "300-420 Russian words. Realistic formal news/official style. Multiple actors, timeline, cause/effect, and at least two details that require connecting information across sentences.",
    "2+": "430-600 Russian words. Dense formal report with competing explanations, qualifications, indirect implications, and several details spread across the passage.",
    "3": "620-850 Russian words. Abstract, analytical, formal Russian. Include nuanced argumentation, implications, institutional perspectives, and information that requires inference beyond explicit facts.",
}

PASSAGE_GENERATION_PROMPT = """
Generate ONE fresh Russian reading passage for ILR-style comprehension practice.

Target ILR level: {level}
Topic domain: {topic}
Length guide: {length_guide}
Minimum accepted length: {min_words} Russian words.
Generation ID: {generation_id}
Attempt: {attempt}

Requirements:
- Russian passage only in passage_ru.
- Do not write questions in this step.
- Make the passage realistic, serious, and suitable for adult proficiency testing.
- Topic should match the chosen domain.
- Use natural Russian, not textbook Russian.
- Do not repeat sentences to reach length.
- Do not copy common fallback/demo topics such as gas leaks, labor law changes, generic bridge closures, or rail flooding unless the selected topic clearly demands it.
- Return exactly one JSON object with these fields and no extra text.

JSON schema:
{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "English title, 3-8 words",
  "passage_ru": "Full Russian passage here"
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
      "choices": {{
        "A": "choice A",
        "B": "choice B",
        "C": "choice C",
        "D": "choice D"
      }},
      "correct_answer": "A",
      "explanation": "Short explanation of why the correct answer is right.",
      "evidence": "Short Russian quote or close paraphrase from the passage.",
      "question_type": "main idea"
    }},
    {{
      "id": "Q2",
      "question": "English question 2",
      "choices": {{
        "A": "choice A",
        "B": "choice B",
        "C": "choice C",
        "D": "choice D"
      }},
      "correct_answer": "B",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "detail"
    }},
    {{
      "id": "Q3",
      "question": "English question 3",
      "choices": {{
        "A": "choice A",
        "B": "choice B",
        "C": "choice C",
        "D": "choice D"
      }},
      "correct_answer": "C",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "inference"
    }},
    {{
      "id": "Q4",
      "question": "English question 4",
      "choices": {{
        "A": "choice A",
        "B": "choice B",
        "C": "choice C",
        "D": "choice D"
      }},
      "correct_answer": "D",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "cause and effect"
    }}
  ]
}}
""".strip()
