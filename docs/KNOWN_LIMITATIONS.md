# Known Limitations

1. **No empirical calibration yet.** Starter and generated difficulty/discrimination values are provisional. Estimates must remain labeled as practice estimates.
2. **AI validation is not expert review.** Typed schemas, deterministic gates, independent passage audit, blind verification, optional second verification, duplicate detection, and quarantine reduce risk but do not replace trained human item review and field statistics.
3. **Provider independence depends on configuration.** With both providers, auto verification can reverse provider order. With one provider, separate models improve independence, but same-provider/same-model configuration remains possible and triggers a warning.
4. **Hosted calls were not made with real user keys in this build environment.** Deterministic integration covers the same code path, but deployed model availability, entitlements, latency, quotas, and provider-specific schema behavior must be confirmed in the Space.
5. **Token totals depend on provider telemetry.** Outbound calls are always counted; input/output token totals are stored only when the SDK response includes usage fields.
6. **Fresh content adds latency and cost.** Stage-aware token caps, smart audit, bounded retries, per-stage attempt caps, concurrency limits, per-session bundle limits, and bank fallback reduce cost but cannot eliminate it.
7. **Generated-content persistence still depends on configured durability.** Local commits are atomic and immediately reusable, but the default Space filesystem can reset. Mounted storage or the implemented Hugging Face Dataset mirror must be configured for restart durability.
8. **Dataset synchronization is best-effort, not a transactional multi-writer database.** The app serializes writes within one Space process and merges local/remote records at startup. Multiple independent writers targeting the same Dataset repository could still create last-writer conflicts and should be avoided.
9. **Synthetic Listening audio.** Fresh Listening uses Edge TTS and starter audio is synthetic. The schema supports authentic/open-licensed audio, but a reviewed native-speaker corpus is not bundled.
10. **Strict playback is not secure-browser lockdown.** The UI removes replay controls and records plays, but cannot prevent external recording or developer-tool manipulation.
11. **Timer display is client-rendered while enforcement is server-side.** A sleeping browser tab can visually refresh late, though server deadlines remain authoritative.
12. **Starter-bank ceiling.** The included bank has 48 Reading and 40 Listening questions. It satisfies the full-simulation minimum but needs substantial expansion for repeated broad use without live generation.
13. **No formal accessibility certification.** Labels, keyboard components, contrast, responsive layout, and live status text are included, but WCAG conformance has not been independently audited.
14. **Public live generation is synthetic only.** Authentic/open-licensed ingestion remains an administrator process because provenance and licensing cannot be safely inferred from a public free-text request.
15. **Prompt and validator drift require versioning.** `PROMPT_VERSION` and pipeline metadata are stored, but future prompt releases will require comparative QA and possibly separate calibration cohorts.
