"""Local private workspace with env/.env credentials; same ledger and pilot gate as the UI."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from core.content_workshop import Workshop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "preflight", "generate", "approve-voices", "export"])
    parser.add_argument("--workspace", type=Path, default=Path("storage/workshop/local"))
    parser.add_argument("--model", default="eleven_v3")
    parser.add_argument("--voices", type=Path, help="JSON mapping speaker identifiers to voice IDs")
    parser.add_argument("--characters", type=int, default=0)
    parser.add_argument("--kind", choices=["pilot", "batch", "selected", "audition"], default="pilot")
    parser.add_argument("--item")
    parser.add_argument("--acknowledge-uncertain", action="store_true")
    parser.add_argument("--confirm-spend", action="store_true", help="Authorize paid generation after reviewing identical preflight")
    parser.add_argument("--output", type=Path, default=Path("storage/workshop/dlpt-drafts.zip"))
    args = parser.parse_args()
    work = Workshop(args.workspace)
    if args.action == "init":
        print("Draft workspace created; edit package.json. No provider called. Credentials are never persisted.")
    elif args.action == "approve-voices":
        work.approve_voices()
        print("Pilot voice approval recorded. Content remains draft.")
    elif args.action == "export":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(work.export())
        print("Private package exported. Review before sharing.")
    else:
        load_dotenv()
        work.configure(os.environ.get("ELEVENLABS_API_KEY", ""))
        if not args.voices:
            raise SystemExit("Provide --voices JSON and --characters explicitly")
        plan = work.preflight(args.model, json.loads(args.voices.read_text(encoding="utf-8")), args.characters,
                              args.kind, args.item, args.acknowledge_uncertain)
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        if args.action == "generate":
            if not args.confirm_spend:
                raise SystemExit("Preflight only. Review it, then repeat with --confirm-spend to authorize paid requests.")
            print(work.generate())


if __name__ == "__main__":
    main()
