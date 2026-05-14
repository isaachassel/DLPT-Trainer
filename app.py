from __future__ import annotations

import gradio as gr

from core.generator import GenerationFailure, generate_reading_block
from core.schema import AnswerRecord, ILR_LEVELS, SessionState
from core.scoring import get_level_decision, summarize_records

TOPICS = [
    "Random serious topics",
    "Military and security",
    "Government and politics",
    "Crime and law enforcement",
    "Accidents and disasters",
    "Economics and sanctions",
    "Social issues",
    "Public health",
    "Science and technology",
    "International relations",
    "Culture and society",
]

SESSION_LENGTHS = {
    "Short - 8 questions": 8,
    "Medium - 16 questions": 16,
    "Long - 24 questions": 24,
}

CONTINUE_BLOCK_SIZE = 4


def _radio_update(choices):
    """Return a Gradio update that replaces answer choices and clears any old answer."""
    return gr.update(choices=choices, value=None, visible=True)


def _empty_radio_update():
    return gr.update(choices=[], value=None, visible=True)


def _render_block(block, state: SessionState):
    source_label = "Live GenAI generation"
    quality_note = f"\n\nNote: {block.generation_error}" if getattr(block, "generation_error", "") else ""
    progress = (
        f"Question block {state.block_number} | Current level: ILR {state.current_level} | "
        f"Completed: {state.answered_count}/{state.session_questions}\n\n"
        f"Generation status: {source_label}{quality_note}\n\n"
        f"{state.adaptive_note}"
    )
    passage = (
        f"### {block.passage_title}\n\n"
        f"**Level:** ILR {block.ilr_level}  \n"
        f"**Topic:** {block.topic}\n\n---\n\n{block.passage_ru}"
    )

    q_texts = []
    answer_updates = []
    for q in block.questions:
        q_texts.append(f"**{q.id}. {q.question}**")
        choice_list = [f"{key}. {value}" for key, value in q.choices.items()]
        answer_updates.append(_radio_update(choice_list))

    # The UI has exactly four question/answer slots.
    while len(q_texts) < 4:
        q_texts.append("")
        answer_updates.append(_empty_radio_update())

    return [progress, passage, *q_texts[:4], *answer_updates[:4]]


def _blank_question_area():
    empty_radios = [_empty_radio_update() for _ in range(4)]
    return ["", "", "", "", "", *empty_radios]


def _new_block(state: SessionState) -> SessionState:
    state.block_number += 1
    state.current_block = generate_reading_block(state.current_level, state.topic)
    return state


def _generation_error_area(exc: Exception):
    msg = (
        "### Live GenAI generation failed\n\n"
        "This build does **not** use fallback templates. No questions are shown unless the GenAI model creates them.\n\n"
        f"**Error:** `{type(exc).__name__}: {exc}`\n\n"
        "Try again, or check your Hugging Face Space logs, HF_TOKEN secret, model name, and provider settings. "
        "Recommended starting model: `Qwen/Qwen2.5-7B-Instruct`."
    )
    blank = _blank_question_area()
    return [msg, *blank, gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)]


def start_session(mode, start_level, target_level, length_label, timer_mode, topic):
    if mode != "Reading Practice":
        msg = "Listening Practice and Full Diagnostic are reserved for Version 2. This build proves the adaptive reading engine first."
        blank = _blank_question_area()
        return [None, msg, *blank, gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)]

    state = SessionState(
        mode=mode,
        starting_level=start_level,
        current_level=start_level,
        target_level=target_level,
        session_questions=SESSION_LENGTHS[length_label],
        base_session_questions=SESSION_LENGTHS[length_label],
        timer_mode=timer_mode,
        topic=topic,
    )
    try:
        state = _new_block(state)
    except Exception as exc:
        err = _generation_error_area(exc)
        return [state, *err]
    rendered = _render_block(state.current_block, state)
    return [state, *rendered, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]


def submit_block(state: SessionState, a1, a2, a3, a4):
    if state is None or state.current_block is None:
        blank = _blank_question_area()
        return [state, "Start a session first.", *blank, gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)]

    answers = [a1, a2, a3, a4]
    if any(a is None or str(a).strip() == "" for a in answers):
        rendered = _render_block(state.current_block, state)
        warning = rendered[0] + "\n\nPlease answer all four questions before submitting the block."
        return [state, warning, *rendered[1:], gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]

    block = state.current_block
    correct_count = 0
    for q, selected in zip(block.questions, answers):
        selected_letter = str(selected).split(".", 1)[0].strip()
        is_correct = selected_letter == q.correct_answer
        if is_correct:
            correct_count += 1
        state.records.append(
            AnswerRecord(
                block_number=state.block_number,
                skill=block.skill,
                ilr_level=block.ilr_level,
                topic=block.topic,
                passage_title=block.passage_title,
                passage_ru=block.passage_ru,
                question=q,
                selected_answer=selected_letter,
                is_correct=is_correct,
            )
        )

    block_score = correct_count / 4
    old_recent = list(state.recent_block_scores)
    next_level, adaptive_note = get_level_decision(state.current_level, block_score, old_recent)
    state.current_level = next_level
    state.adaptive_note = adaptive_note
    state.recent_block_scores.append(block_score)

    if state.is_complete:
        _, report = summarize_records(state.records, state.starting_level, state.session_questions)
        progress = (
            f"Base session complete | Completed: {state.answered_count}/{state.session_questions}\n\n"
            f"{adaptive_note}\n\n"
            "You can stop here, or continue with another 4-question adaptive block. "
            "Continuing keeps your current adaptive level and improves the estimate."
        )
        blank = _blank_question_area()
        return [state, progress, *blank, gr.update(visible=False), report, gr.update(visible=True)]

    try:
        state = _new_block(state)
    except Exception as exc:
        err = _generation_error_area(exc)
        return [state, *err]
    rendered = _render_block(state.current_block, state)
    return [state, *rendered, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]


def continue_session(state: SessionState):
    if state is None:
        blank = _blank_question_area()
        return [state, "Start a session first.", *blank, gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)]

    state.session_questions += CONTINUE_BLOCK_SIZE
    state.adaptive_note = (
        f"Continuing session. Added {CONTINUE_BLOCK_SIZE} more questions. "
        f"The next block starts at your current adaptive level: ILR {state.current_level}."
    )
    try:
        state = _new_block(state)
    except Exception as exc:
        err = _generation_error_area(exc)
        return [state, *err]
    rendered = _render_block(state.current_block, state)
    return [state, *rendered, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)]


def reset_answers():
    return [gr.update(value=None), gr.update(value=None), gr.update(value=None), gr.update(value=None)]


with gr.Blocks(title="Russian ILR Trainer") as demo:
    gr.Markdown(
        "# Russian ILR Trainer\n"
        "Adaptive Russian reading practice for serious proficiency test preparation. "
        "This is DLPT-style, ILR-aligned practice, not an official DLPT product."
    )

    state = gr.State(value=None)

    with gr.Row():
        mode = gr.Radio(
            ["Reading Practice", "Listening Practice", "Full Diagnostic"],
            value="Reading Practice",
            label="Mode",
        )
        start_level = gr.Dropdown(ILR_LEVELS, value="1+", label="Starting ILR Level")
        target_level = gr.Dropdown(ILR_LEVELS, value="2", label="Target ILR Level")

    with gr.Row():
        length = gr.Radio(list(SESSION_LENGTHS.keys()), value="Short - 8 questions", label="Base Session Length")
        timer_mode = gr.Radio(["Off", "Standard", "Strict"], value="Off", label="Timer")
        topic = gr.Dropdown(TOPICS, value="Random serious topics", label="Topic Domain")

    start_btn = gr.Button("Begin Session", variant="primary")

    progress = gr.Markdown()
    passage = gr.Markdown()

    q1 = gr.Markdown()
    a1 = gr.Radio(label="Answer 1", choices=[])
    q2 = gr.Markdown()
    a2 = gr.Radio(label="Answer 2", choices=[])
    q3 = gr.Markdown()
    a3 = gr.Radio(label="Answer 3", choices=[])
    q4 = gr.Markdown()
    a4 = gr.Radio(label="Answer 4", choices=[])

    submit_btn = gr.Button("Submit Block", variant="primary", visible=False)
    continue_btn = gr.Button("Continue Practice (+4 questions)", variant="secondary", visible=False)
    report_box = gr.Markdown(visible=True)

    outputs = [state, progress, passage, q1, q2, q3, q4, a1, a2, a3, a4, submit_btn, report_box, continue_btn]

    start_btn.click(
        start_session,
        inputs=[mode, start_level, target_level, length, timer_mode, topic],
        outputs=outputs,
    ).then(reset_answers, outputs=[a1, a2, a3, a4])

    submit_btn.click(
        submit_block,
        inputs=[state, a1, a2, a3, a4],
        outputs=outputs,
    ).then(reset_answers, outputs=[a1, a2, a3, a4])

    continue_btn.click(
        continue_session,
        inputs=[state],
        outputs=outputs,
    ).then(reset_answers, outputs=[a1, a2, a3, a4])

if __name__ == "__main__":
    demo.launch()
