# Russian practice bank through ILR 3

October 4, 2026. Original AI-assisted fictional scenarios; no text copied from official tests or third-party articles. The owner requested expansion of the working bank through level 3 and authorized 8,000 additional ElevenLabs input characters. No subscription upgrade or credit purchase is authorized.

## Packaged coverage

| Provisional band | Reading passages / questions | Listening passages / questions |
| --- | --- | --- |
| 0 | 2 / 4 | 2 / 4 |
| 0+ | 2 / 4 | 12 / 24 |
| 1 | 2 / 4 | 2 / 4 |
| 1+ | 2 / 4 | 2 / 4 |
| 2 | 2 / 6 | 2 / 6 |
| 2+ | 2 / 6 | 2 / 6 |
| 3 | 2 / 6 | 2 / 6 |
| Total | 14 / 34 | 24 / 54 |

The original 51 starter passages remain pending review. `scripts/prepare_expansion_drafts.py` rebuilds the 26 original expansion drafts offline in `data/pilots/russian_range_expansion.json`; it never generates audio or approves content. Approved deployment copies are in `data/assessment/bank.json` with fixed, checksum-linked recordings in `data/assessment/audio`.

## Difficulty rationale

The authoring guide uses the primary [ILR reading descriptions](https://govtilr.org/Skills/Reading.htm) and [ILR listening descriptions](https://govtilr.org/Skills/Listening.htm), consulted October 4. These describe people’s functional proficiency, not calibrated passage parameters. Mapping them onto individual synthetic passages is an authoring judgment, not an official rating.

- **0:** isolated word-recognition probes at the estimator's floor. Success on these does not define a meaningful general “level 0” proficiency.
- **0+:** formulaic signs and familiar phrases. The earlier owner-approved 0+ dialogues retain their existing labels; their connected exchanges may ultimately need upward relabeling after expert review.
- **1:** familiar messages, directions and transactions with explicit information.
- **1+:** routine situations with a changed plan, condition or sequence across connected sentences.
- **2:** factual public/workplace accounts across timeframes, with concrete causes and procedures.
- **2+:** qualified conclusions, competing practical considerations and accessible rhetorical language.
- **3:** supported opinion, counterargument, hypothetical consequences, incentives and implied relationships. Questions require integrating the argument rather than locating an isolated difficult word.

Each new passage records its individual rationale and descriptor link. Reading material ranges from two isolated labels to a 229-word essay; listening material ranges from isolated recognition probes to roughly 200-word interviews. This deliberately samples multiple demands but cannot represent the complete variety, endurance, dialects or authentic material at any proficiency level.

## Review and audio

Codex reviewed transcript/answer consistency, exact evidence, plausible distractors, sentence-level distinctions and difficulty progression under the owner's expansion instruction. All 64 new questions have four distinct English options; answer keys are balanced at 16 per letter. Automated checks cover exact evidence, duplicate passages, answer-length cues, valid relationships and audio checksums. These checks are not independent expert or empirical validation.

New recordings use the demonstrated ElevenLabs Text to Dialogue method: `eleven_v3`, Russian language, Jessica for speaker A and Eric for speaker B, natural delivery, no voice cloning or speed effects. The owner’s standing method authorization is recorded separately from individual listening review; no manual listening review of each new clip is claimed. Content remains explicitly synthetic and difficulty estimates remain provisional.

Generation consumed **7,088 new input characters**, within the **8,000-character additional authorization**, leaving **912 authorized characters**. The live account usage check confirmed **8,712 / 10,000 characters**, below the conservative cumulative ceiling of 9,624 (1,624 already consumed plus 8,000 newly authorized). Requests reserve budget durably and uncertain outcomes are not retried automatically. Recordings retain Free-plan noncommercial terms and attribution; no purchase, public deployment or push is part of this expansion request.

## Verification

The real-bank regression tests check coverage at every band in both skills, checksum-backed assets, no duplicate content, stronger/weaker routing reaching the upper/lower bands, no within-session repetition, final review, and explicit uncertainty for a level-3-only run. Existing tests retain the original 0+-only bank as an isolated sparse fixture so expanded coverage cannot mask its stopping behavior. The original mixed/borderline posterior and separate-skill tests remain applicable.

The full local suite passed: **320 passed, 5 skipped**. The skipped checks require ffmpeg/ffprobe, which are unavailable in the current environment. All twelve new MP3s decoded in the browser without errors; the two level-3 recordings last approximately 104 and 105 seconds. Live ElevenLabs generation was verified for all twelve new recordings.

A browser smoke test completed both level-3 reading passages followed by both level-3 listening passages (12 questions). It confirmed browser-started playback, replay locking, withheld answers until both sections ended, and a populated final report with separate estimates, uncertainty, stopping reasons, answer review and JSON/CSV export links. This workflow test is not an independent human listening review of the recordings.

The bank is ready for broader practice, not an official DLPT prediction. Further work should prioritize multiple genres and topics per band, independent language/ILR review and observed item statistics rather than treating the new labels as calibrated ground truth.
