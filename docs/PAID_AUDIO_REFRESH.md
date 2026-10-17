# Paid audio refresh — October 6, 2026

The owner authorized replacing recordings generated without commercial rights,
deploying replacements, and removing required provider attribution. The scheduled
follow-up began at 04:24 PDT; ordinary Codex usage had reset (1% used).

## Scope and licensing

All 24 Russian Free-plan recordings were regenerated under the live-verified
Starter plan. The 14 Mandarin Starter recordings were retained byte-for-byte.
Both use generally available Eleven v3 with Jessica/Eric premade voices. The
model left Alpha on February 2, 2026, before these paid recordings were generated.
The standard paid-plan terms permit commercial use subject to applicable terms
and input/voice rights; no provider title credit is required. Publishing guidance,
Terms of Service, service-specific terms, ElevenAPI and Speech Engine terms were
reviewed. Exact links and dated, checksum-bound reviews are retained in each
recording's `license_review` and [the audio notice](../data/assessment/audio/NOTICE.md).

Scripts, questions, correct answers and provisional difficulty labels did not
change. The bank remains **66 passages, 156 questions, 38 recordings**. New audio
uses Isaac's standing method approval; no individual human listening or
native-speaker review is claimed. Synthetic-audio and unvalidated-score
disclosures remain in the demo.

## Cost and recovery

- Unique scripts: 8,712 input characters.
- One 636-character request timed out. History recovery was unavailable to the
  restricted key. One reviewed retry succeeded; the uncertain attempt remains
  counted, totaling 9,348 reserved input characters.
- Account before: Starter, 1,353 / 31,288 credits used.
- Settled account after: 5,091 / 31,288 credits used.
- Observed usage: **3,738 credits**, with **26,197 remaining**. Input characters
  and billed credits differ. No credits or subscriptions purchased.

Generation was staged in an ignored local workshop. Replacements were decoded
before changing the active bank. Retired files were removed from the active
audio directory into an excluded local rollback archive; Git history was not
rewritten. Those historical files retain their original restrictions. The
deployment includes only current manifest-referenced recordings.

## Verification

All 38 MP3s were fully decoded using PyAV installed only in the project venv;
durations range from 1.60 to 135.92 seconds. Schema round-trip, content validation,
audio/transcript checksums and bank loading passed without warnings. 104 focused
tests passed across bank/workshop, Mandarin, demo, reporting, hosting and audio
release. After adding the audit to packaging, all 8 release checks passed again.
Tests include both skills/languages with strong/weak/mixed performance, playback
locking, stopping/reports and rejection of Free-plan, beta, missing-review,
changed-audio and unsafe-path releases.

The deployment ZIP has 90 allowlisted files, including 38 MP3s and provenance.
It excludes secrets, local results, workshops and retired audio. SHA-256:
`71f83a9279563ffea5404b0a7981e699e57d85ec2511999f23b40201966ba297`.
Provider names remain in internal provenance and implementation, not mandatory
visitor-facing branding. No GitHub push or main merge was performed.

## Published deployment

Hugging Face deployment commit: `c5affd71c8cc5dbc77e65f127e45c6ceb32ab223`.
The protected Space is titled **Language Test** and serves the public app at
https://isaachassel-dlpt-adaptive-demo.hf.space. WordPress page 892 at
https://isaachassel.com/language-test/ embeds it under **Start your assessment**.
The provider-credit paragraph and iframe-title attribution were removed;
independent-practice, synthetic-audio, approximate-score and hosting disclosures
remain.

An anonymous request to the published WordPress page returned HTTP 200 with the
clean heading, iframe and no provider attribution. A public request for the new
Russian level-2 recording returned HTTP 200 and 721,859 bytes whose SHA-256
matches the approved release manifest. The embedded app served audio from this
release's extraction directory (`_demo_71f83a9279563ffe`). Live browser testing
confirmed two listens, the intervening beep status, answer submission unlocking
only after playback, and progression to distinct replacement passages.
The Russian listening smoke test completed all 12 questions across 6 passages.
Its report displayed the chosen test answers' 4/12 result, an estimated practice
level around ILR 0+, low confidence, an ILR 0–1+ uncertainty range, and the explicit
ending reason that all 12 questions were completed. These were deliberately
selected test answers, not a learner assessment. Refreshing WordPress afterward
confirmed the published clean heading and removed attribution in the browser.

Screenshot proof: `storage/exports/wordpress-paid-audio-live.jpg` (local only).

The one-time `refresh-demo-audio-licensing` heartbeat was paused after deployment
to prevent another generation or deployment run. No additional generation was
performed during final verification.
