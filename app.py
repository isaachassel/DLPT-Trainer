from __future__ import annotations

import gradio as gr

from core.generator import generate_reading_block
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


def _radio_update(choices):
    """Return a Gradio update that replaces answer choices and clears any old answer."""
    return gr.update(choices=choices, value=None, visible=True)


def _empty_radio_update():
    return gr.update(choices=[], value=None, visible=True)


def _render_block(block, state: SessionState):
    source_label = "Live AI generation" if getattr(block, "generation_source", "live") == "live" else "Demo fallback mode"
    error_note = ""
    if getattr(block, "generation_source", "live") != "live" and getattr(block, "generation_error", ""):
        error_note = f"\n\nFallback reason: {block.generation_error}"
    progress = (
        f"Question block {state.block_number} | Current level: ILR {state.current_level} | "
        f"Completed: {state.answered_count}/{state.session_questions}\n\n"
        f"Generation status: {source_label}{error_note}\n\n"
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


def _new_block(state: SessionState) -> SessionState:
    state.block_number += 1
    state.current_block = generate_reading_block(state.current_level, state.topic)
    return state


def start_session(mode, start_level, target_level, length_label, timer_mode, topic):
    if mode != "Reading Practice":
        msg = "Listening Practice and Full Diagnostic are reserved for Version 2. This build proves the adaptive reading engine first."
        empty_radios = [_empty_radio_update() for _ in range(4)]
        return [None, msg, "", "", "", "", "", *empty_radios, gr.update(visible=False), gr.update(visible=True)]

    state = SessionState(
        mode=mode,
        starting_level=start_level,
        current_level=start_level,
        target_level=target_level,
        session_questions=SESSION_LENGTHS[length_label],
        timer_mode=timer_mode,
        topic=topic,
    )
    state = _new_block(state)
    rendered = _render_block(state.current_block, state)
    return [state, *rendered, gr.update(visible=True), gr.update(visible=False)]


def submit_block(state: SessionState, a1, a2, a3, a4):
    if state is None or state.current_block is None:
        empty_radios = [_empty_radio_update() for _ in range(4)]
        return [state, "Start a session first.", "", "", "", "", "", *empty_radios, gr.update(visible=False), gr.update(visible=True)]

    answers = [a1, a2, a3, a4]
    if any(a is None or str(a).strip() == "" for a in answers):
        rendered = _render_block(state.current_block, state)
        warning = rendered[0] + "\n\nPlease answer all four questions before submitting the block."
        return [state, warning, *rendered[1:], gr.update(visible=True), gr.update(visible=False)]

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
        _, report = summarize_records(state.records, state.starting_level)
        empty_radios = [_empty_radio_update() for _ in range(4)]
        return [state, "Assessment complete.", report, "", "", "", "", *empty_radios, gr.update(visible=False), gr.update(visible=True)]

    state = _new_block(state)
    rendered = _render_block(state.current_block, state)
    return [state, *rendered, gr.update(visible=True), gr.update(visible=False)]


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
        length = gr.Radio(list(SESSION_LENGTHS.keys()), value="Short - 8 questions", label="Session Length")
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
    report_box = gr.Markdown(visible=True)

    outputs = [state, progress, passage, q1, q2, q3, q4, a1, a2, a3, a4, submit_btn, report_box]

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

if __name__ == "__main__":
    demo.launch()
