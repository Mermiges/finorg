from __future__ import annotations

import argparse

from huggingface_hub import snapshot_download


def main():
    parser = argparse.ArgumentParser(description="Download LightOnOCR-2 weights into a chosen cache directory.")
    parser.add_argument("--model", default="lightonai/LightOnOCR-2-1B")
    parser.add_argument("--cache-dir", default=None)
    args = parser.parse_args()

    path = snapshot_download(repo_id=args.model, cache_dir=args.cache_dir)
    print(path)


if __name__ == "__main__":
    main()
