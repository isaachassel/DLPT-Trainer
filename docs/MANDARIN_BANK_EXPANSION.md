# Mandarin practice bank through ILR 3

October 4, 2026. Original AI-assisted fictional scenarios in simplified Chinese, with English questions and exact Chinese evidence. No content was copied from official tests or third-party articles, and these are not translations of the Russian bank. The owner requested the same expansion and ElevenLabs method used for Russian, with 31,288 input characters available on Starter.

## Packaged coverage

| Provisional band | Reading passages / questions | Listening passages / questions |
| --- | --- | --- |
| 0 | 2 / 4 | 2 / 4 |
| 0+ | 2 / 4 | 2 / 4 |
| 1 | 2 / 4 | 2 / 4 |
| 1+ | 2 / 4 | 2 / 4 |
| 2 | 2 / 6 | 2 / 6 |
| 2+ | 2 / 6 | 2 / 6 |
| 3 | 2 / 6 | 2 / 6 |
| Total | 14 / 34 | 14 / 34 |

The original 51 starter passages were subsequently removed from the deployed bank; legacy test fixtures are isolated from the app. Russian's approved 14 reading and 24 listening passages are preserved. The ten extra Russian 0+ listening passages reflect its earlier twelve-recording pilot; Mandarin begins with two passages per band in both skills.

`scripts/prepare_mandarin_drafts.py` rebuilds the 28 offline drafts in `data/pilots/mandarin_range_expansion.json`; it neither generates nor approves audio. Approved deployment content lives in `data/assessment/bank.json`. MP3s use Git LFS and checksum-linked local paths. The schema retains the historical names `passage_ru` and `evidence_ru` for target-language text; these items explicitly declare `language: zh-CN`.

## Authoring and review

The working anchors follow the [ILR reading](https://govtilr.org/Skills/Reading.htm) and [ILR listening](https://govtilr.org/Skills/Listening.htm) descriptions used for the Russian expansion. Those descriptions rate people, not item parameters. Individual passage labels remain authoring judgments.

- **0:** isolated word/sign recognition at the estimator floor. This does not define general functional proficiency.
- **0+:** formulaic notices, listings and brief transactions; familiar location, price and time details.
- **1:** simple connected household messages, transport notices and routine exchanges.
- **1+:** changed plans, conditions and ordered actions in everyday work, courses and travel.
- **2:** concrete factual accounts with causes, procedures, timeframes and resource decisions.
- **2+:** qualified opinions, competing explanations, tradeoffs and accessible metaphors.
- **3:** sustained argument, concession, implied consequences, institutional incentives, selection bias and competing values.

Upper reading passages have 498 and 526 Han characters; upper listening transcripts contain 494 and 479 Han characters. Chinese unit counts cannot be compared directly with Russian word counts. English orientation lines give context without translating answers. No pinyin or listening transcript appears during the active assessment. The 68 questions have four distinct choices, balanced at 17 correct answers per letter.

Codex checked transcript/answer consistency, exact evidence, plausible distractors, topic distinctions and difficulty progression. Automated checks cover structural validity, answer-length cues, duplicates, language routing and asset checksums. Approval is under the owner's instruction; it is not independent native-speaker review, pronunciation certification or empirical ILR calibration.

## ElevenLabs method and accounting

Recordings use Eleven v3 Text to Dialogue, Jessica for speaker A and Eric for speaker B, natural delivery and MP3 44.1 kHz / 128 kbps. No voice cloning, speed effects or new subscription purchase is involved. The provider's live catalog confirms Mandarin support with ISO code `zh`; the project retains `zh-CN` and maps it at the API boundary. All requests keep below the documented 2,000-input-character recommendation.

The account check confirmed **Starter**, with **0 / 31,288** used before this expansion. The fourteen scripts total **2,857 input characters**. One final request timed out; provider-history recovery was attempted but unavailable to this key. One manually reviewed 524-character retry succeeded, giving a conservative ledger total of **3,381 characters**, including the original uncertain attempt. The settled live account check reported **1,353 credits used / 31,288**, leaving **29,935 credits**. Input characters and billed credits are distinct; the lower observed billing is not promised for future runs.

The private workspace `storage/workshop/mandarin-expansion` has a separate durable ledger and owner authorization. Each request reserves its entire character count before sending. Failed or uncertain requests remain counted and are not automatically retried. The former Russian authorization and unspent allowance are not added to this new ceiling. Long audio requests now have a bounded 240-second read timeout, with a 20-second connection timeout; automatic retries remain disabled.

The owner explicitly extended the demonstrated method to Mandarin. A named, language-specific method grant allows automatic audio acceptance without recording a fabricated pilot listening review. Model, voice or language changes do not inherit that grant. Content and reuse review remain separate from audio acceptance. No individual human listening review of these new clips is claimed. Jessica and Eric are multilingual preset voices labeled English by the provider; Mandarin pronunciation and accent need future native-speaker evaluation.

New recordings retain their **Starter creation-time tier**. Earlier Russian files retain their **Free creation-time terms**; upgrading does not rewrite their rights. ElevenLabs states that paid-plan generation includes commercial rights subject to applicable terms and exclusions such as Beta Services. No public distribution or deployment is part of this task. See the [publishing guidance](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform), [language/accent guidance](https://help.elevenlabs.io/hc/en-us/articles/19124313713041-What-languages-can-the-AI-speak), and [dialogue API](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert), checked October 4, 2026.

## Running and limitations

Use the existing `.venv` and the local startup instructions in [PRESET_BANK_AND_WORKSHOP.md](PRESET_BANK_AND_WORKSHOP.md). In Session Setup choose **Mandarin Chinese → Adaptive Assessment**, either skill or both, and eligibility **0–3**. Defaults are 6–18 passages per skill. With fourteen available per skill, a section can exhaust its content before the maximum; the report explains that outcome.

The unchanged Bayesian passage-testlet model tracks separate skill posteriors, includes guessing and shared-passage dependence, and reports uncertainty. This small bank does not represent all genres, dialects, accents or endurance demands. Two passages per band is initial coverage, not calibration or a validated official DLPT score. Further expansion should increase variety and add independent language/ILR review and observed item statistics.

## Verification

The full regression suite passed: **331 passed, 5 skipped**. The skipped checks require unavailable ffmpeg/ffprobe tools. On this Windows environment, Gradio tests require permission for local socketpair creation outside the restricted network sandbox. No system configuration was changed.

Tests cover Mandarin provider language mapping, language-specific owner grants, preservation of Russian resume fingerprints, budget rejection, duplicate-call avoidance, mixed-language rejection, model language compatibility, Mandarin auditions and retained edit language/band. Real-bank tests exercise strong/weak routing to both endpoints, stopping and no repetition independently in each language and skill. Existing mixed/borderline and sparse-bank tests remain intact.

All fourteen MP3s decoded in the browser with no errors. Duration ranges from 1.6-second word recognition to level-3 interviews of 135.92 and 124.64 seconds. These playback checks confirm usable files, not independent linguistic quality.

A combined browser assessment completed two level-3 reading passages followed by two level-3 listening passages (12 questions), including checkpoint recovery after the preview process stopped. It verified Mandarin rendering, fixed local audio, browser-confirmed one-play locking, withheld transcripts/answers, and a populated final report with separate skill estimates, credible intervals, explicit maximum-length stopping, inconclusive single-band coverage, answer review and JSON/CSV export links. The final preview is reset to the complete 0–3 range and normal 6–18 limits.
