#!/usr/bin/env python3
"""Batch-generate MP3 files for all pre-built conversations."""

import argparse
import os
import sys
import time

from conversations import CONVERSATIONS
from tts_engine import assign_default_voices, detect_speakers, generate_audio


def main():
    parser = argparse.ArgumentParser(
        description="Generate MP3 audio for pre-built Chinese conversations"
    )
    parser.add_argument(
        "--rate",
        default="+0%",
        help='Speech rate adjustment, e.g. "-15%%" for slower (default: +0%%)',
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Generate only the conversation with this id (e.g. 01)",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for generated MP3 files (default: output)",
    )
    args = parser.parse_args()

    conversations = CONVERSATIONS
    if args.only:
        conversations = [c for c in conversations if c["id"] == args.only]
        if not conversations:
            print(f"Error: no conversation with id '{args.only}'")
            sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    for c in conversations:
        lines = c["lines"]
        speakers = detect_speakers(lines)
        voice_map = assign_default_voices(speakers)
        filename = f"{c['id']}_{c['name']}.mp3"
        output_path = os.path.join(args.output_dir, filename)

        print(f"  Generating {filename} ... ", end="", flush=True)
        t0 = time.time()
        generate_audio(lines, voice_map, rate=args.rate, output_path=output_path)
        elapsed = time.time() - t0
        print(f"done ({elapsed:.1f}s)")

    print(f"\nAll done! {len(conversations)} files in {args.output_dir}/")


if __name__ == "__main__":
    main()
