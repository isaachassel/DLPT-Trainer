from pathlib import Path

from core.audio import audio_cache_key, naturalize_spoken_text
from core.config import Settings
from core.generation import _natural_voice_profile
from core.models import GenerationMetadata, PassageItem


def _passage(genre: str = "news report", language: str = "ru") -> PassageItem:
    text = "По данным министерства ситуация изменилась. Однако власти продолжают работу. " * 4
    return PassageItem(
        id="p1", language=language, skill="listening", target_ilr="2",
        provisional_difficulty=0.5, genre=genre, topic="government", subtopic="public update",
        orientation_en="You will hear a report.", passage_ru=text, word_count=len(text.split()),
        question_ids=["q1"], content_hash="abc123", duplicate_detection_hash="abc123",
        generation=GenerationMetadata(),
    )


def test_naturalize_spoken_text_repairs_russian_discourse_pauses():
    result = naturalize_spoken_text("По данным министерства всё готово. Однако работа продолжается.", "ru")
    assert "По данным, министерства" not in result
    assert "По данным министерства" in result
    assert "Однако работа" in result


def test_naturalize_spoken_text_does_not_inject_long_pause_boundaries():
    text = "Первое предложение. Второе предложение. Третье предложение. " * 5
    assert "\n" not in naturalize_spoken_text(text, "ru")


def test_natural_profile_is_stable_and_bounded():
    passage = _passage()
    profile = _natural_voice_profile(passage, Settings())
    assert profile == _natural_voice_profile(passage, Settings())
    voice, rate, pitch, volume = profile
    assert voice == "ru-RU-DmitryNeural"
    assert 1 <= int(rate.removesuffix("%")) <= 5
    assert pitch == "+0Hz"
    assert volume == "+0%"


def test_cache_key_changes_for_pitch_and_volume():
    base = audio_cache_key("текст", "voice", "+0%", "v", "+0Hz", "+0%")
    assert base != audio_cache_key("текст", "voice", "+0%", "v", "+1Hz", "+0%")

from core.audio import split_speaker_turns, _dialogue_voice_map, _voice_for_turn


def test_split_named_russian_speaker_turns():
    script = "Ведущий: Почему изменилось решение?\nЭксперт: Появились новые данные.\nВедущий: Что будет дальше?"
    turns = split_speaker_turns(script)
    assert turns == [
        ("Ведущий", "Почему изменилось решение?"),
        ("Эксперт", "Появились новые данные."),
        ("Ведущий", "Что будет дальше?"),
    ]


def test_split_dash_dialogue_alternates_speakers():
    turns = split_speaker_turns("— Вы уже приняли решение?\n— Нет, обсуждение продолжается.\n— Когда будут итоги?")
    assert [label for label, _ in turns] == ["speaker_0", "speaker_1", "speaker_0"]


def test_single_narrator_colon_is_not_misclassified():
    assert split_speaker_turns("Главная причина: изменение погодных условий.") == []


def test_gendered_labels_receive_distinct_russian_voices():
    female = _voice_for_turn("Женщина", 0, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    male = _voice_for_turn("Мужчина", 1, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    assert female == "ru-RU-SvetlanaNeural"
    assert male == "ru-RU-DmitryNeural"



def test_generic_host_and_guest_get_distinct_stable_voices():
    turns = split_speaker_turns(
        "Ведущий: Добрый вечер.\nГость: Спасибо за приглашение.\nВедущий: Что изменилось?"
    )
    mapping = _dialogue_voice_map(turns, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    voices = [mapping[label.casefold()] for label, _ in turns]
    assert voices == [
        "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural",
        "ru-RU-DmitryNeural",
    ]


def test_generic_interviewer_and_expert_do_not_collapse_to_one_voice():
    turns = split_speaker_turns(
        "Интервьюер: Почему вы приехали?\nЭксперт: Я участвую в конференции."
    )
    mapping = _dialogue_voice_map(turns, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    assert len(set(mapping.values())) == 2


def test_explicit_female_role_keeps_female_voice_and_other_speaker_gets_opposite():
    turns = split_speaker_turns(
        "Ведущая: Добрый вечер.\nЭксперт: Спасибо за приглашение."
    )
    mapping = _dialogue_voice_map(turns, "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural")
    assert mapping["ведущая"] == "ru-RU-SvetlanaNeural"
    assert mapping["эксперт"] == "ru-RU-DmitryNeural"


def test_manual_female_primary_still_assigns_second_speaker_male_voice():
    turns = split_speaker_turns("Ведущий: Первый вопрос.\nГость: Первый ответ.")
    mapping = _dialogue_voice_map(turns, "ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural")
    assert mapping == {
        "ведущий": "ru-RU-SvetlanaNeural",
        "гость": "ru-RU-DmitryNeural",
    }

def test_naturalize_removes_pause_heavy_typography():
    result = naturalize_spoken_text("Решение…  было принято — после обсуждения.", "ru")
    assert "…" not in result
    assert " — " not in result
    assert "  " not in result


def test_inline_speaker_labels_are_split_and_never_spoken():
    from core.audio import split_speaker_turns
    script = "Ведущий: Добрый вечер. Гость: Спасибо за приглашение. Ведущий: Что изменилось?"
    turns = split_speaker_turns(script)
    assert [label.casefold() for label, _ in turns] == ["ведущий", "гость", "ведущий"]
    assert [text for _, text in turns] == ["Добрый вечер.", "Спасибо за приглашение.", "Что изменилось?"]
    assert all("гость" not in text.casefold() and "ведущий" not in text.casefold() for _, text in turns)


def test_malformed_guest_label_is_removed_from_fallback_audio():
    from core.audio import strip_speaker_labels
    assert strip_speaker_labels("Гост: Спасибо за приглашение.") == "Спасибо за приглашение."


def test_dialogue_assembly_preserves_complete_segment_duration(tmp_path):
    import shutil
    import subprocess
    import pytest
    from pathlib import Path
    from core.audio import audio_duration_seconds, generate_dialogue_cached_tts

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe are required")

    counter = {"value": 0}
    requested_voices = []

    def fake_synth(text, cache_dir, **kwargs):
        counter["value"] += 1
        requested_voices.append(kwargs.get("voice"))
        duration = 1.8 if counter["value"] == 1 else 2.2
        output = Path(cache_dir) / f"segment-{counter['value']}.mp3"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i",
                f"sine=frequency={400 + counter['value'] * 100}:duration={duration}",
                "-codec:a", "libmp3lame", "-q:a", "4", str(output),
            ],
            check=True,
        )
        return output

    output = generate_dialogue_cached_tts(
        "Ведущий: Добрый вечер.\nГость: Спасибо за приглашение.",
        tmp_path,
        synthesizer=fake_synth,
        engine_version="duration-regression-v3",
    )
    duration = audio_duration_seconds(output)
    assert counter["value"] == 2
    assert requested_voices == ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"]
    assert duration is not None
    assert duration >= 3.8


def test_russian_voice_choices_include_edge_and_local_piper_speakers():
    from core.languages import voice_choices, voice_for_label, native_voice_pool

    choices = voice_choices("ru")
    assert "Russian Female — Irina (local Piper)" in choices
    assert "Russian Male — Ruslan (local Piper)" in choices
    assert voice_for_label("ru", "Russian Female — Irina (local Piper)") == "piper:ru_RU-irina-medium"
    # Existing saved sessions that selected the unavailable Dariya label migrate safely.
    assert voice_for_label("ru", "Russian Female — Dariya") == "piper:ru_RU-irina-medium"
    assert native_voice_pool("ru", "ru-RU-DmitryNeural")[:4] == (
        "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural",
        "piper:ru_RU-irina-medium",
        "piper:ru_RU-ruslan-medium",
    )


def test_three_generic_speakers_receive_three_distinct_native_russian_voices():
    from core.audio import _dialogue_speaker_profiles, split_speaker_turns

    turns = split_speaker_turns(
        "Ведущий: Первый вопрос.\nГость: Первый ответ.\nЭксперт: Дополнительный комментарий."
    )
    profiles = _dialogue_speaker_profiles(
        turns, "ru-RU-DmitryNeural", "ru", base_rate="+3%"
    )
    assert [profiles[key].voice for key in ("ведущий", "гость", "эксперт")] == [
        "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural",
        "piper:ru_RU-irina-medium",
    ]
    assert len({profile.voice for profile in profiles.values()}) == 3


def test_fourth_speaker_receives_fourth_distinct_free_russian_voice():
    from core.audio import _dialogue_speaker_profiles, split_speaker_turns

    turns = split_speaker_turns(
        "Ведущий: Один.\nГость: Два.\nЭксперт: Три.\nКорреспондент: Четыре."
    )
    profiles = _dialogue_speaker_profiles(
        turns, "ru-RU-DmitryNeural", "ru", base_rate="+3%"
    )
    fourth = profiles["корреспондент"]
    assert len({profile.voice for profile in profiles.values()}) == 4
    assert fourth.voice == "piper:ru_RU-ruslan-medium"
    assert fourth.rate == "+3%"


def test_repeated_third_speaker_keeps_irina_and_same_rate():
    from core.audio import _dialogue_speaker_profiles, split_speaker_turns

    turns = split_speaker_turns(
        "Ведущий: Один.\nГость: Два.\nЭксперт: Три.\nЭксперт: Ещё три."
    )
    profiles = _dialogue_speaker_profiles(turns, "ru-RU-DmitryNeural", "ru", base_rate="+1%")
    assert profiles["эксперт"].voice == "piper:ru_RU-irina-medium"
    assert profiles["эксперт"].rate == "+1%"


def test_three_speaker_audio_synthesis_calls_three_voice_ids(tmp_path):
    import shutil
    import subprocess
    import pytest
    from pathlib import Path
    from core.audio import generate_dialogue_cached_tts

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required")

    requested: list[tuple[str, str]] = []

    def fake_synth(text, cache_dir, **kwargs):
        requested.append((kwargs["voice"], kwargs["rate"]))
        output = Path(cache_dir) / f"segment-{len(requested)}.mp3"
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=500:duration=0.6",
                "-codec:a", "libmp3lame", "-q:a", "4", str(output),
            ],
            check=True,
        )
        return output

    output = generate_dialogue_cached_tts(
        "Ведущий: Один.\nГость: Два.\nЭксперт: Три.",
        tmp_path,
        voice="ru-RU-DmitryNeural",
        rate="+3%",
        synthesizer=fake_synth,
        engine_version="three-speaker-regression-v1",
    )
    assert output.exists()
    assert requested == [
        ("ru-RU-DmitryNeural", "+3%"),
        ("ru-RU-SvetlanaNeural", "+3%"),
        ("piper:ru_RU-irina-medium", "+3%"),
    ]


def test_training_audio_profile_honors_explicit_irina_selection():
    from core.session import create_session
    from ui.callbacks import _training_audio_profile

    state = create_session(
        language="ru",
        mode="training",
        selected_skills=["listening"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Russian Female — Irina (local Piper)",
        speech_rate_label="Normal",
    )
    voice, rate, pitch, volume, display, explicit = _training_audio_profile(state, _passage())
    assert voice == "piper:ru_RU-irina-medium"
    assert rate == "+0%"
    assert pitch == "+0Hz"
    assert volume == "+0%"
    assert display == "Russian Female — Irina (local Piper)"
    assert explicit is True


def test_training_playback_uses_irina_without_first_rendering_canonical_edge_voice(monkeypatch, bank, tmp_path):
    import ui.callbacks as callbacks
    from core.session import create_session, select_next_bundle

    state = create_session(
        language="ru",
        mode="training",
        selected_skills=["listening"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Russian Female — Irina (local Piper)",
        speech_rate_label="Normal",
    )
    bundle = select_next_bundle(state, bank)
    calls: list[str] = []
    rendered = tmp_path / "irina.mp3"
    rendered.write_bytes(b"ID3" + b"0" * 1024)

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["voice"])
        return rendered

    monkeypatch.setattr(callbacks, "generate_dialogue_cached_tts", fake_generate)
    monkeypatch.setattr(callbacks.STORAGE, "save_checkpoint", lambda *_: None)
    result = callbacks.play_audio_callback(state, callbacks._bundle_to_dict(bundle), progress=None)
    assert calls == ["piper:ru_RU-irina-medium"]
    assert "Russian Female — Irina (local Piper)" in result[3]["value"]
    assert str(rendered.resolve()) in result[1]["value"]


def test_irina_failure_falls_back_to_svetlana_and_reports_actual_voice(monkeypatch, bank, tmp_path):
    import ui.callbacks as callbacks
    from core.session import create_session, select_next_bundle

    state = create_session(
        language="ru",
        mode="training",
        selected_skills=["listening"],
        start_level="1+",
        target_level="2",
        topics=[],
        competencies=[],
        max_questions_per_skill=8,
        minimum_questions_per_skill=8,
        timer_mode="off",
        time_limit_seconds_per_skill=None,
        profile_id=None,
        feedback_mode="end_only",
        hints_enabled=False,
        transcript_review_enabled=True,
        replay_allowed=True,
        slow_audio_allowed=True,
        voice_label="Russian Female — Irina (local Piper)",
        speech_rate_label="Normal",
    )
    bundle = select_next_bundle(state, bank)
    calls: list[str] = []
    fallback = tmp_path / "svetlana.mp3"
    fallback.write_bytes(b"ID3" + b"0" * 1024)

    def fake_generate(*args, **kwargs):
        calls.append(kwargs["voice"])
        if kwargs["voice"] == "piper:ru_RU-irina-medium":
            raise RuntimeError("voice unavailable")
        return fallback

    monkeypatch.setattr(callbacks, "generate_dialogue_cached_tts", fake_generate)
    monkeypatch.setattr(callbacks.STORAGE, "save_checkpoint", lambda *_: None)
    result = callbacks.play_audio_callback(state, callbacks._bundle_to_dict(bundle), progress=None)
    assert calls[:2] == ["piper:ru_RU-irina-medium", "ru-RU-SvetlanaNeural"]
    assert "fell back to Russian Female — Svetlana" in result[3]["value"]


def test_explicit_dialogue_mode_does_not_silently_replace_failed_segment_voice(tmp_path):
    import pytest
    from core.audio import VoiceUnavailableError, generate_dialogue_cached_tts

    requested: list[str] = []

    def fake_synth(text, cache_dir, **kwargs):
        requested.append(kwargs["voice"])
        if kwargs["voice"] == "piper:ru_RU-irina-medium":
            raise RuntimeError("voice unavailable")
        output = Path(cache_dir) / f"segment-{len(requested)}.mp3"
        output.write_bytes(b"ID3" + b"0" * 1024)
        return output

    with pytest.raises(VoiceUnavailableError) as exc_info:
        generate_dialogue_cached_tts(
            "Ведущий: Один.\nГость: Два.\nЭксперт: Три.",
            tmp_path,
            voice="ru-RU-DmitryNeural",
            rate="+0%",
            synthesizer=fake_synth,
            engine_version="no-silent-fallback-v1",
            allow_segment_fallback=False,
        )
    assert exc_info.value.voice == "piper:ru_RU-irina-medium"
    assert requested == [
        "ru-RU-DmitryNeural",
        "ru-RU-SvetlanaNeural",
        "piper:ru_RU-irina-medium",
    ]


def test_explicit_training_helper_retries_with_unavailable_voice_removed(monkeypatch, tmp_path):
    import ui.callbacks as callbacks
    from core.audio import VoiceUnavailableError

    passage = _passage(genre="interview")
    attempts: list[tuple[str, tuple[str, ...]]] = []
    rendered = tmp_path / "retry.mp3"
    rendered.write_bytes(b"ID3" + b"0" * 1024)

    def fake_generate(*args, **kwargs):
        pool = tuple(kwargs.get("voice_pool") or ())
        attempts.append((kwargs["voice"], pool))
        if len(attempts) == 1:
            raise VoiceUnavailableError("piper:ru_RU-irina-medium")
        return rendered

    monkeypatch.setattr(callbacks, "generate_dialogue_cached_tts", fake_generate)
    path, actual, unavailable = callbacks._generate_explicit_training_audio(
        passage,
        tmp_path,
        "ru-RU-DmitryNeural",
        "+0%",
        "+0Hz",
        "+0%",
    )
    assert path == rendered
    assert actual == "ru-RU-DmitryNeural"
    assert unavailable == ("piper:ru_RU-irina-medium",)
    assert "piper:ru_RU-irina-medium" not in attempts[1][1]


def test_seller_buyer_roles_are_detected_and_labels_are_not_spoken():
    from core.audio import split_speaker_turns
    turns = split_speaker_turns(
        "Продавец: Добрый день. Чем могу помочь?\n"
        "Покупатель: Мне нужен новый телефон.\n"
        "Продавец: Есть несколько моделей."
    )
    assert [label for label, _ in turns] == ["Продавец", "Покупатель", "Продавец"]
    assert [spoken for _, spoken in turns] == [
        "Добрый день. Чем могу помочь?",
        "Мне нужен новый телефон.",
        "Есть несколько моделей.",
    ]
    assert all("продав" not in spoken.casefold() and "покуп" not in spoken.casefold() for _, spoken in turns)


def test_arbitrary_two_role_dialogue_gets_two_distinct_voices():
    from core.audio import _dialogue_speaker_profiles, split_speaker_turns
    turns = split_speaker_turns(
        "Продавец: Добрый день.\nПокупатель: Здравствуйте.\nПродавец: Что вы ищете?"
    )
    profiles = _dialogue_speaker_profiles(turns, "ru-RU-DmitryNeural", "ru", base_rate="+3%")
    assert profiles["продавец"].voice == "ru-RU-DmitryNeural"
    assert profiles["покупатель"].voice == "ru-RU-SvetlanaNeural"


def test_generic_colon_prose_still_is_not_misclassified_as_dialogue():
    from core.audio import split_speaker_turns
    assert split_speaker_turns("Москва: сегодня ожидается дождь.\nТемпература: около десяти градусов.") == []

def test_seller_buyer_audio_path_calls_two_voices_and_never_synthesizes_labels(tmp_path):
    import shutil
    import subprocess
    import pytest
    from pathlib import Path
    from core.audio import generate_dialogue_cached_tts

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is required")

    requested = []
    def fake_synth(text, cache_dir, **kwargs):
        requested.append((text, kwargs["voice"]))
        output = Path(cache_dir) / f"seller-buyer-{len(requested)}.mp3"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=500:duration=0.35",
            "-codec:a", "libmp3lame", "-q:a", "4", str(output),
        ], check=True)
        return output

    output = generate_dialogue_cached_tts(
        "Продавец: Добрый день.\nПокупатель: Здравствуйте.\nПродавец: Что вы ищете?",
        tmp_path,
        voice="ru-RU-DmitryNeural",
        rate="+3%",
        synthesizer=fake_synth,
        engine_version="seller-buyer-routing-v1",
    )
    assert output.exists()
    assert [voice for _text, voice in requested] == [
        "ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"
    ]
    assert all("продавец" not in text.casefold() and "покупатель" not in text.casefold() for text, _voice in requested)
