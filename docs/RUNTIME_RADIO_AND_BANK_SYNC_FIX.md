# Runtime Radio and Durable-Bank Sync Fix

## Answer radio failure

Gradio 6 validates incoming Radio values against the choices stored on the server component instance. The application originally created each answer Radio with an empty choice list and supplied A/B/C/D dynamically when a passage rendered. The browser displayed the answers correctly, but a queued callback could still validate against the original empty server list and reject a legitimate value such as `B`.

Version 1.3.2 creates every answer Radio with stable A/B/C/D values from the beginning and uses dynamic labels only for presentation. A component-specific preprocessor independently validates the stable answer key.

## Dataset synchronization failure

Earlier versions reduced every remote persistence failure to a generic “last sync failed” status. Version 1.3.2 performs a real create/access check, retries transient errors, tries the dedicated bank token and the general HF token when both exist, and surfaces a sanitized HTTP error.

The **Test / Retry Durable Bank Sync** button performs an immediate access test and uploads the current JSONL bank, manifest, and generated Listening audio. A 401 or 403 still requires a Hugging Face token with repository write permission; application code cannot grant account permissions.

## Storage safety

Fresh content remains operational immediately after its atomic local commit. It is restart-safe only when either mounted persistent storage is active or the private Dataset synchronization succeeds. The interface now states the exact condition instead of implying durability after a failed mirror.
