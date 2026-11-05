# Russian vocabulary expansion — November 4, 2026

Local branch: `codex/russian-vocabulary-study`. No public deployment or change to
the adaptive demo bank is included.

Nine original fictional dialogues add 54 target meanings, each with three
distractors and a different short reading example. Topics: family visits,
classroom preparation, clothing, travel, a clinic visit, housing, manufacturing,
public policy and weather. These are provisional study materials, not authentic
DLI examination passages or human-reviewed calibration items.

All nine scripts use the previously approved Eleven v3 Text to Dialogue method
with Jessica (`cgSgspJ2msm6clMCkdW9`) and Eric (`cjVigY5qzO86Huf0OWal`). The live
catalog confirmed both as available premade voices and Russian support. There
was no substitution, voice cloning, subscription change or credit purchase.

- Account before: Starter, 0 / 56,197 credits consumed.
- Unique input: **5,208 characters**; operational cap: 8,000.
- Paid requests: nine; no retries or uncertain requests.
- Account immediately after generation: 1,540 / 56,197 (not yet settled).
- Read-only post-run check: **2,084 / 56,197**, or **54,113 remaining**.
- MP3s: 44.1 kHz / 128 kbps; decoded durations 31.28–47.76 seconds.

Every file was staged, fully decoded, fingerprinted against its exact script and
voice/model configuration, and hashed before the new manifest became active.
`data/study/audio.json` retains individual generation dates, creation-time tier,
voice IDs, script fingerprint, audio checksum and license review links. The
ignored local ledger in `storage/workshop/vocabulary-expansion-20261104` retains
reservations and recovery state; no credentials are written into it.

The official [publishing guidance](https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform)
permits commercial use of qualifying paid-plan output, subject to applicable
terms and input/voice rights, and excludes Beta Services. [Eleven v3 became
generally available on February 2, 2026](https://elevenlabs.io/blog/eleven-v3-is-now-generally-available).
The standard [Terms](https://elevenlabs.io/terms-of-use),
[service-specific terms](https://elevenlabs.io/service-specific-terms) and
[ElevenAPI terms](https://elevenlabs.io/elevenapi-terms) were checked for this batch.
The existing standard paid-plan method does not require provider title
attribution; this is not a claim that every ElevenLabs product or custom agreement
has identical terms. Synthetic-audio disclosure and internal provenance remain.
Standing owner method approval is recorded; no individual human listening review
of these nine new files is claimed.

Current coverage counts describe dictionary entries rather than unique headwords:
295 reading entries / 160 listening entries across the full imported catalog,
including 175 / 102 within course modules. There are 270 total context exercises,
23 study recordings (14 reused + nine new), and nine multi-word passage checks.

The assessment-to-review implementation and its uncertainty limitations are
documented in [Vocabulary Study](VOCABULARY_STUDY.md#passage-checks-and-personalized-review).

## Verification

The final combined regression run passed **93 tests**. An earlier run encountered
a transient Windows access-denied error replacing a legacy demo checkpoint; the
demo suite passed on recheck, and the final full run passed without code changes
to the demo. No live demo files or deployments were modified.

Browser checks verified a complete three-passage reading check with 12/18 correct
answers and seven review priorities (six misses plus one correct guess), adaptive
stage changes, a fresh short-context review, persisted evidence after restart,
new listening playback through its 31-second end, transcript withholding, early
stopping, and the listening review handoff. A successful follow-up review reduced
the priority count and scheduled the word for the next day. The answer report is
cleared before focused review. Evidence screenshots remain in ignored local
`storage/study/`; QA uses the disposable `Passage QA` profile, not learner data.
