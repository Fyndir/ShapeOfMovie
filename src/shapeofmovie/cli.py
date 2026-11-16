"""Command line interface.

shapeofmovie analyze ~/Movies -o shapes/ --method linear
shapeofmovie render shapes/*.json -o images/ --style ring
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Iterable
from pathlib import Path

from shapeofmovie.analyze import analyze
from shapeofmovie.colors import METHODS
from shapeofmovie.extract import VIDEO_EXTENSIONS, FFmpegError
from shapeofmovie.logs import setup_logging
from shapeofmovie.models import MovieShape
from shapeofmovie.render import STYLES, render

log = logging.getLogger("shapeofmovie")


def _expand(paths: Iterable[Path], extensions: set[str]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if p.is_dir():
            found += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in extensions)
        elif p.is_file():
            found.append(p)
        else:
            print(f"warning: {p} does not exist, skipped", file=sys.stderr)
    return found


def _progress(done: int, total: int | None) -> None:
    if not total or not sys.stderr.isatty():
        return
    pct = min(100, done * 100 // total)
    end = "\n" if done >= total else ""
    print(f"\r  {pct:3d}% ({done}/{total})", end=end, file=sys.stderr, flush=True)


def cmd_analyze(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    videos = _expand(args.paths, VIDEO_EXTENSIONS)
    if not videos:
        print("no video found", file=sys.stderr)
        return 1
    failures = 0
    for video in videos:
        target = args.output / f"{video.stem}.{args.method}.json"
        if target.exists() and not args.force:
            print(f"skip   {video.name} (already analysed, use --force)")
            continue
        try:
            shape = analyze(video, method=args.method, step=args.step, progress=_progress)
        except (FFmpegError, ValueError) as exc:
            log.error("%s: %s", video.name, exc)
            failures += 1
            continue
        tmp = target.with_suffix(".json.part")  # never leave a half-written file behind
        shape.save(tmp)
        tmp.replace(target)
        print(f"{video.name} -> {target} ({len(shape)} samples)")
    return 1 if failures else 0


def cmd_render(args: argparse.Namespace) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    files = _expand(args.paths, {".json"})
    for file in files:
        shape = MovieShape.load(file)
        img = render(shape, style=args.style, width=args.width, height=args.height, smooth=args.smooth)
        target = args.output / f"{file.stem}.{args.style}.png"
        img.save(target)
        print(f"{file.name} -> {target}")
    return 0 if files else 1


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from shapeofmovie.web import Settings, create_app
    except ImportError:
        print("the web interface needs: pip install shapeofmovie[web]", file=sys.stderr)
        return 1
    base = Settings.from_env()
    settings = Settings(**{**base.__dict__, "data_dir": args.data or base.data_dir})
    print(f"Shape Of Movie on http://{args.host}:{args.port} (data: {settings.data_dir.resolve()})")
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_config=None)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shapeofmovie", description=__doc__.split("\n")[0])
    parser.add_argument("--log-level", help="DEBUG, INFO, WARNING, ERROR (default: $SOM_LOG_LEVEL or INFO)")
    parser.add_argument("--log-file", type=Path, help="also write logs to this file (default: $SOM_LOG_FILE)")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="extract the colour signature of videos into JSON files")
    a.add_argument("paths", nargs="+", type=Path, help="video files or folders (searched recursively)")
    a.add_argument("-o", "--output", type=Path, default=Path("shapes"))
    a.add_argument("-m", "--method", choices=METHODS, default="mean")
    a.add_argument("-s", "--step", type=float, default=1.0, help="seconds between samples (default 1)")
    a.add_argument("-f", "--force", action="store_true", help="re-analyse even if the JSON exists")
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("render", help="draw images from JSON files")
    r.add_argument("paths", nargs="+", type=Path, help="JSON files or folders")
    r.add_argument("-o", "--output", type=Path, default=Path("images"))
    r.add_argument("--style", choices=STYLES, default="barcode")
    r.add_argument("--width", type=int, default=1920)
    r.add_argument("--height", type=int, default=1080)
    r.add_argument("--smooth", type=int, default=0, help="moving-average window, in samples")
    r.set_defaults(func=cmd_render)

    w = sub.add_parser("serve", help="start the web interface")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8000)
    w.add_argument("--data", type=Path, help="data folder (default: $SOM_DATA_DIR or ./data)")
    w.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level, args.log_file)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
