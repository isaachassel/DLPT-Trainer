# Hugging Face Listening Runtime Fix — v1.2.3

## Reported behavior

The Space built and started, but its container log showed repeated asyncio `Invalid file descriptor: -1` finalizer warnings, truncated Content-Length messages, and 405 responses for `/graphql` and `/api/graphql` when the Listening flow was used.

## Root causes

1. Hugging Face enabled Gradio 6 experimental server-side rendering for the Space. The app does not require SSR, and the associated Node proxy was the source of the GraphQL-route noise.
2. Listening callbacks embedded every MP3 as a base64 data URI. That needlessly enlarged callback responses and increased the chance of proxy/body truncation.
3. Optional Edge TTS created and destroyed asyncio loops per request, which was unnecessarily fragile under concurrent callback workers.

The Gradio event-loop finalizer warning is a documented framework/Spaces issue and does not by itself mean the adaptive session crashed. The release nevertheless removes the SSR path that triggered the surrounding noise.

## Implemented correction

- `app.py` passes `ssr_mode=False`.
- `app.py` exposes only the validated starter-audio directory and runtime TTS cache through `allowed_paths`.
- `core/audio.py` returns compact `/gradio_api/file=` URLs rather than base64 MP3 data.
- `ui/layout.py` binds the audio element through Gradio's reactive HTML lifecycle.
- Strict mode still has no controls or replay and removes the source after one completed play.
- Training mode retains replay.
- Optional TTS uses one reusable background asyncio loop with a bounded timeout.
- Every error path continues to preserve the checkpoint and completed responses.

## Validation

- 73 automated tests passed.
- Application page returned HTTP 200.
- Full audio delivery returned HTTP 200 with `audio/mpeg`.
- Range playback returned HTTP 206.
- A stateful Gradio client started a Listening session and invoked playback successfully.
