from __future__ import annotations

GENERATION_SYSTEM_PROMPT = """
You create Russian ILR-aligned reading comprehension practice for serious linguists.
You are not creating official DLPT material. You are creating independent DLPT-style practice.
Return ONLY valid JSON. No markdown. No commentary. No code fences. Use JSON arrays for multi-paragraph passages; never put raw line breaks inside a JSON string.
""".strip()

# One source of truth for passage shape + level behavior.
# These rules are based on official ILR Reading Skill Level Descriptions, adapted for practice generation.
# Paragraph rule requested by user:
# 0/0+/1 = 1 paragraph, 1+/2 = 2 paragraphs, 2+ = 3 paragraphs, 3 = 4 paragraphs.
ILR_STRUCTURE_RULES = {
    "0": {
        "min_words": 15,
        "max_words": 45,
        "paragraphs": 1,
        "sentences_per_paragraph": "1-3 short lines or sentences",
        "description": "no practical prose reading; use isolated signs, labels, names, numbers, dates, addresses, office/shop designations, or very short public text",
        "official_basis": "Reading 0: no practical ability to read; consistently misunderstands or cannot comprehend connected text.",
        "text_requirements": "Do not create connected prose. Create a realistic micro-text such as a sign, label, schedule fragment, address notice, or simple public-facing phrase.",
        "question_profile": "Ask recognition questions only: identify a number, place name, date, type of sign, or isolated word meaning. No inference, no implied meaning, no connected-prose comprehension.",
    },
    "0+": {
        "min_words": 35,
        "max_words": 80,
        "paragraphs": 1,
        "sentences_per_paragraph": "2-5 short sentences or sign-like lines",
        "description": "memorized proficiency; letters, numbers, isolated words/phrases, personal/place names, street signs, office and shop designations; connected prose should be minimal or absent",
        "official_basis": "Reading 0+: can recognize letters, numbers, isolated words/phrases, names, signs, office/shop designations; often inaccurate; unable to read connected prose.",
        "text_requirements": "Use mostly isolated or formulaic text: signs, notices, short labels, names, simple public information. Avoid sustained narrative or full news-report style.",
        "question_profile": "Ask recognition and extraction questions only. Test obvious names, numbers, places, labels, and simple phrases. Do not ask inference questions.",
    },
    "1": {
        "min_words": 80,
        "max_words": 140,
        "paragraphs": 1,
        "sentences_per_paragraph": "5-8 simple sentences",
        "description": "very simple connected written material with high-frequency vocabulary, familiar formulaic exchanges, descriptions of persons/places/things, tourist-style geography/government explanations",
        "official_basis": "Reading 1: can read very simple connected material with highest-frequency patterns and vocabulary; can get some main ideas and identify general subject matter in some authentic texts.",
        "text_requirements": "Use very simple connected prose. Keep sequence predictable. Use high-frequency structures. Avoid dense subordinate clauses, nuance, argumentation, and professional abstraction.",
        "question_profile": "Ask main idea, prominent detail, simple sequence, and obvious subject-matter questions. Distractors should test common simple misunderstandings, not nuance.",
    },
    "1+": {
        "min_words": 130,
        "max_words": 220,
        "paragraphs": 2,
        "sentences_per_paragraph": "3-5 mostly simple sentences",
        "description": "simple discourse for informative social purposes: public announcements, simple event narration, biographical information, straightforward headlines, routine professional information",
        "official_basis": "Reading 1+: can understand simple printed discourse for informative social purposes; announcements, simple narration, headlines; may misread grammar, time reference, cohesive factors, and pronoun referents.",
        "text_requirements": "Use simple discourse with two short paragraphs. Include clear time markers, basic cause/effect, and one pronoun/reference relationship. Keep vocabulary contextualized.",
        "question_profile": "Ask main idea, routine detail, simple cause/effect, sequence, and one basic reference/time question. Inference must be very limited and highly supported by context.",
    },
    "2": {
        "min_words": 190,
        "max_words": 320,
        "paragraphs": 2,
        "sentences_per_paragraph": "5-7 sentences",
        "description": "simple authentic factual material on familiar subjects; straightforward news items, social notices, formulaic business letters, simple technical material for general readers",
        "official_basis": "Reading 2: can read simple authentic factual material on familiar subjects; locate main ideas and details; generally not experienced enough to draw inferences directly from linguistic aspects of the text; factual questions are typical.",
        "text_requirements": "Make it authentic and factual with predictable sequence. Include main ideas and details, but do not rely on subtle implication or disguised intent. Use mostly straightforward/high-frequency sentence patterns.",
        "question_profile": "Prioritize factual comprehension: main idea, detail, sequence, cause/effect, who/what/when/where/why. Avoid subtle inference; any inference must be directly supported and concrete.",
    },
    "2+": {
        "min_words": 280,
        "max_words": 460,
        "paragraphs": 3,
        "sentences_per_paragraph": "4-6 sentences",
        "description": "most factual non-technical prose and concrete professional topics; separates main ideas/details from lesser ones; gist of more difficult material but weak on nuance or disguised meaning",
        "official_basis": "Reading 2+: understands most factual non-technical material and some concrete professional discussions; can separate main and subsidiary ideas; can make sensible guesses, but may miss nuance or intentionally disguised meaning.",
        "text_requirements": "Use denser factual prose with main and subsidiary ideas. Include concrete professional relevance, qualifications, and unfamiliar terms that can be understood from context. Do not require subtle cultural nuance.",
        "question_profile": "Ask main/subsidiary idea distinction, concrete inference from context, detail prioritization, cause/effect, and gist. Include one question that requires separating important from less important information.",
    },
    "3": {
        "min_words": 400,
        "max_words": 650,
        "paragraphs": 4,
        "sentences_per_paragraph": "4-6 sentences",
        "description": "authentic professional prose on unfamiliar subjects: wire-service style reports, international news, routine correspondence, general reports, and technical/professional material with hypothesis, argumentation, and supported opinion",
        "official_basis": "Reading 3: reads authentic prose on unfamiliar subjects with almost complete comprehension; can interpret correctly, relate ideas, and read between the lines; can handle hypothesis, argumentation, and supported opinions, though subtle nuance may remain difficult.",
        "text_requirements": "Use authentic adult professional style with argumentation, supported opinion, implicit intent, and relationships across paragraphs. Include some abstract language and unfamiliar subject matter, but keep it general-reader accessible.",
        "question_profile": "Ask about main argument, supported opinion, implicit intent, inference across paragraphs, relationship of ideas, tone/attitude, and conclusions. Avoid questions answerable by one isolated sentence only.",
    },
}

PASSAGE_GENERATION_PROMPT = """
Generate ONE fresh Russian reading passage for ILR-style comprehension practice.

Target ILR level: {level}
Topic domain: {topic}
Generation ID: {generation_id}
Attempt: {attempt}

Official ILR basis for this generated practice level:
{official_basis}

Required structure for ILR {level}:
- Total length: {min_words}-{max_words} Russian words.
- Paragraph count: exactly {paragraphs} paragraph(s).
- Sentence count: {sentences_per_paragraph}.
- Style: {description}.
- Text requirement: {text_requirements}

Hard requirements:
- Write the Russian passage only inside passage_paragraphs.
- Do not write questions in this step.
- Match the selected ILR level. Do not make low levels too complex or high levels too simple.
- Use natural adult Russian, not textbook Russian.
- Topic must match the selected domain.
- Do not use bullet points, numbered lists, headings inside the Russian passage, or English inside the Russian passage.
- Do not repeat sentences to reach length.
- Do not copy common demo topics such as gas leaks, generic labor-law changes, bridge closures, or rail flooding unless the selected topic clearly demands it.
- If you are below the required paragraph count, add paragraph breaks before returning JSON.
- If you are below {min_words} Russian words, continue expanding before returning JSON.

Return exactly one JSON object with these fields and no extra text.

Important JSON formatting rule:
- Do NOT put raw line breaks inside JSON string values.
- Put each Russian paragraph as one separate string in the passage_paragraphs array.
- The passage_paragraphs array must contain exactly {paragraphs} item(s).

JSON schema:
{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "English title, 3-8 words",
  "passage_paragraphs": [
    {paragraph_items}
  ]
}}
""".strip()

PASSAGE_EXPANSION_PROMPT = """
The Russian passage below is too short or has too few paragraphs for ILR-style practice. Expand it while preserving the same event/topic and keeping it natural.

Target ILR level: {level}
Topic domain: {topic}
Official ILR basis:
{official_basis}
Required total length: {min_words}-{max_words} Russian words.
Required paragraph count: exactly {paragraphs} paragraph(s).
Required sentence count: {sentences_per_paragraph}.
Text requirement: {text_requirements}
Current word count: {current_words}
Current paragraph count: {current_paragraphs}

Expansion requirements:
- Keep the same general scenario, but add details appropriate to ILR {level}.
- Do not make low levels too complex.
- Do not add questions.
- Do not use bullet points or lists.
- Do not repeat sentences.
- Russian only inside passage_paragraphs.
- If the passage is still below {min_words} Russian words or {paragraphs} paragraph(s), continue expanding before returning JSON.

Original title: {title}
Original passage:
{passage_ru}

Return exactly one JSON object and no extra text.

Important JSON formatting rule:
- Do NOT put raw line breaks inside JSON string values.
- Put each Russian paragraph as one separate string in the passage_paragraphs array.
- The passage_paragraphs array must contain exactly {paragraphs} item(s).

{{
  "skill": "reading",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "{title}",
  "passage_paragraphs": [
    {paragraph_items}
  ]
}}
""".strip()

QUESTION_GENERATION_PROMPT = """
Create EXACTLY FOUR English multiple-choice comprehension questions for the Russian passage below.

Target ILR level: {level}
Topic domain: {topic}
Passage title: {title}
Attempt: {attempt}

Official/question design guidance for ILR {level}:
{official_basis}
Question profile: {question_profile}

Rules:
- Questions must be in English.
- Choices must be in English.
- Base every correct answer only on the Russian passage.
- Include a hidden answer key using correct_answer.
- Include short explanation and Russian evidence for each item.
- Match the question difficulty to ILR {level}. Do not ask high-level inference questions at 0, 0+, 1, or 1 unless the profile allows it.
- Avoid vocabulary-only questions except at 0 and 0+, where recognition questions are appropriate.
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
      "question_type": "cause and effect"
    }},
    {{
      "id": "Q4",
      "question": "English question 4",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "D",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "comprehension"
    }}
  ]
}}
""".strip()

# Listening rules based on official ILR Listening Skill Level Descriptions, adapted for generated audio practice.
# Paragraph rules requested by user:
# 0/0+/1 = 1 short spoken segment, 1+/2 = 2 short segments, 2+ = 3 segments, 3 = 4 segments.
LISTENING_STRUCTURE_RULES = {
    "0": {
        "min_words": 8,
        "max_words": 30,
        "segments": 1,
        "style": "isolated spoken words or very short memorized formulae; no real communication beyond recognition",
        "delivery": "very slow, clear, with natural pauses",
        "official_basis": "Listening 0: no practical understanding; may catch only occasional isolated words.",
        "text_requirements": "Create a very short audio script with isolated words, names, numbers, or formulaic public phrases. Do not create connected conversation.",
        "question_profile": "Recognition only: identify a number, name, place, basic phrase, or purpose of the announcement. No inference.",
    },
    "0+": {
        "min_words": 20,
        "max_words": 55,
        "segments": 1,
        "style": "memorized utterances about immediate needs: greetings, simple requests, prices, times, locations",
        "delivery": "slow and clear, with pauses between short phrases",
        "official_basis": "Listening 0+: understands memorized utterances in immediate needs; requires frequent pauses/repetition; short formulaic utterances only; context strongly supports meaning.",
        "text_requirements": "Use short memorized utterances and formulae. Strong context. Avoid sustained narration or complex grammar.",
        "question_profile": "Ask recognition/extraction questions: time, price, location, speaker request, simple object/action. No implication.",
    },
    "1": {
        "min_words": 45,
        "max_words": 95,
        "segments": 1,
        "style": "simple face-to-face speech about survival needs, travel, meals, lodging, directions, time, and routine courtesy",
        "delivery": "clearer and slower than normal, as if speaking to a foreigner",
        "official_basis": "Listening 1: understands simple questions, answers, statements, and very simple face-to-face conversations about basic survival, courtesy, travel, time, and directions; main ideas only.",
        "text_requirements": "Use basic vocabulary and simple grammar. Include clear main idea and a few obvious details. Keep it face-to-face or announcement-like.",
        "question_profile": "Ask main idea, obvious detail, time/place, simple direction/sequence. Distractors should reflect basic listening misunderstandings.",
    },
    "1+": {
        "min_words": 85,
        "max_words": 150,
        "segments": 2,
        "style": "short conversation or announcement about survival needs plus limited social demands; short discrete utterances",
        "delivery": "clear standard Russian, slightly slower than normal, with short pauses",
        "official_basis": "Listening 1+: understands short conversations about survival needs and limited social demands; uneven consistency; facts are possible; cohesive features and references are unreliable.",
        "text_requirements": "Use two short spoken segments. Include routine facts, time forms, common question forms, and one simple reference/pronoun connection.",
        "question_profile": "Ask main idea, routine fact, simple time/reference, sequence, and limited concrete inference supported by context.",
    },
    "2": {
        "min_words": 130,
        "max_words": 230,
        "segments": 2,
        "style": "routine social or limited job-related speech, everyday topics, known current events, office matters, descriptions/narration of current/past/future events",
        "delivery": "standard dialect at a normal but clear rate; some natural rewording is allowed",
        "official_basis": "Listening 2: understands routine social demands and limited job requirements; factual content; lines but not between or beyond the lines.",
        "text_requirements": "Create a realistic spoken report, short briefing, phone-style update, or face-to-face conversation. Focus on factual content and predictable sequence.",
        "question_profile": "Prioritize factual listening comprehension: main idea, detail, sequence, cause/effect, who/what/when/where/why. Avoid subtle implication.",
    },
    "2+": {
        "min_words": 200,
        "max_words": 340,
        "segments": 3,
        "style": "routine work requirements and concrete topics in special fields; more ease but may break down under pressure; some implications/emotional overtones",
        "delivery": "standard Russian at normal clear speed, with realistic speech flow",
        "official_basis": "Listening 2+: understands most routine social/work demands and some concrete professional discussions; can sometimes detect emotional overtones and implications.",
        "text_requirements": "Use three spoken segments with factual detail, speaker attitude, concrete professional relevance, and one implication that is supported but not directly stated.",
        "question_profile": "Ask gist, important vs secondary detail, factual detail, concrete implication, emotional overtone or speaker attitude.",
    },
    "3": {
        "min_words": 300,
        "max_words": 520,
        "segments": 4,
        "style": "news broadcast, oral report, public address, technical/professional discussion, supported opinion, hypothesis, educated native speech",
        "delivery": "normal clarity and speed in standard Russian; professional broadcast or briefing style",
        "official_basis": "Listening 3: understands essentials of standard speech including technical discussions, clear telephone calls, radio broadcasts, oral reports, public addresses, hypothesis, supported opinions, implications, and emotional overtones.",
        "text_requirements": "Use four spoken segments. Include argumentation, supported opinion or hypothesis, relationships across segments, and implied intent. Keep it standard Russian, not slang-heavy.",
        "question_profile": "Ask main argument, supported opinion, implication, speaker intent, relationship of ideas, tone/attitude, and conclusion across segments.",
    },
}

LISTENING_GENERATION_PROMPT = """
Generate ONE fresh Russian listening script for ILR-style listening comprehension practice.

Target ILR listening level: {level}
Topic domain: {topic}
Generation ID: {generation_id}
Attempt: {attempt}

Official ILR listening basis:
{official_basis}

Required listening structure for ILR {level}:
- Total length: {min_words}-{max_words} Russian words.
- Spoken segment count: exactly {segments} segment(s).
- Style: {style}.
- Delivery style to imply in the script: {delivery}.
- Text requirement: {text_requirements}

Hard requirements:
- Write Russian only inside script_segments.
- Do not write questions in this step.
- This is for audio: write natural spoken Russian, not written article prose.
- Do not include speaker labels like "Speaker 1:" unless the level/task clearly needs dialogue.
- Do not include stage directions, SSML, markdown, bullets, or English.
- Do not repeat sentences to reach length.
- If you are below {min_words} Russian words, continue expanding before returning JSON.
- Put each spoken segment as a separate string in script_segments.
- The script_segments array must contain exactly {segments} item(s).

Return exactly one JSON object with these fields and no extra text:
{{
  "skill": "listening",
  "ilr_level": "{level}",
  "topic": "{topic}",
  "passage_title": "English title, 3-8 words",
  "script_segments": [
    {segment_items}
  ]
}}
""".strip()

LISTENING_QUESTION_GENERATION_PROMPT = """
Create EXACTLY FOUR English multiple-choice listening comprehension questions for the Russian audio script below.

Target ILR listening level: {level}
Topic domain: {topic}
Audio title: {title}
Attempt: {attempt}

Official/question design guidance for ILR listening {level}:
{official_basis}
Question profile: {question_profile}

Rules:
- Questions must be in English.
- Choices must be in English.
- Base every correct answer only on the Russian script.
- Include hidden answer key using correct_answer.
- Include short explanation and Russian evidence from the script.
- Match the question difficulty to ILR listening {level}.
- At 0/0+/1, focus on recognition, obvious facts, survival/travel/courtesy info.
- At 2, focus on factual content: lines, not between the lines.
- At 2+/3, include supported implication, attitude, speaker intent, or relationship of ideas when appropriate.
- Distractors must be plausible listening misunderstandings but clearly wrong based on the script.
- Return exactly one JSON object. No markdown. No commentary.
- The questions array must contain exactly Q1, Q2, Q3, Q4.

Russian audio script/transcript, hidden from the learner during the test:
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
      "evidence": "Short Russian evidence from the audio script.",
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
      "question_type": "cause and effect"
    }},
    {{
      "id": "Q4",
      "question": "English question 4",
      "choices": {{"A": "choice A", "B": "choice B", "C": "choice C", "D": "choice D"}},
      "correct_answer": "D",
      "explanation": "Short explanation.",
      "evidence": "Russian evidence.",
      "question_type": "comprehension"
    }}
  ]
}}
""".strip()
