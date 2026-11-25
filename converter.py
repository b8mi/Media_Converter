
#!/usr/bin/env python3

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_H264 = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264",
         "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p"]

FORMATS = [
    {"ext": "mp4", "kind": "video", "label": "MP4 video (H.264 + AAC)",
     "needs": ["libx264", "aac"],
     "args": _H264 + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]},

    {"ext": "mkv", "kind": "video", "label": "MKV video (H.264 + AAC)",
     "needs": ["libx264", "aac"],
     "args": _H264 + ["-c:a", "aac", "-b:a", "192k"]},

    {"ext": "mov", "kind": "video", "label": "MOV video (H.264 + AAC)",
     "needs": ["libx264", "aac"],
     "args": _H264 + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]},

    {"ext": "webm", "kind": "video", "label": "WebM video (VP9 + Opus)",
     "needs": ["libvpx-vp9", "libopus"],
     "args": ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1",
              "-cpu-used", "4", "-c:a", "libopus", "-b:a", "128k"]},

    {"ext": "avi", "kind": "video", "label": "AVI video (MPEG-4 + MP3)",
     "needs": ["mpeg4", "libmp3lame"],
     "args": ["-c:v", "mpeg4", "-q:v", "4", "-c:a", "libmp3lame", "-b:a", "192k"]},

    {"ext": "gif", "kind": "video", "label": "Animated GIF (no sound)",
     "needs": ["gif"], "no_audio": True,
     "args": ["-vf", "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];"
              "[s0]palettegen[p];[s1][p]paletteuse", "-loop", "0"]},

    {"ext": "mp3", "kind": "audio", "label": "MP3 audio",
     "needs": ["libmp3lame"], "args": ["-c:a", "libmp3lame", "-b:a", "192k"]},

    {"ext": "wav", "kind": "audio", "label": "WAV audio (uncompressed)",
     "needs": ["pcm_s16le"], "args": ["-c:a", "pcm_s16le"]},

    {"ext": "flac", "kind": "audio", "label": "FLAC audio (lossless)",
     "needs": ["flac"], "args": ["-c:a", "flac"]},

    {"ext": "m4a", "kind": "audio", "label": "M4A audio (AAC)",
     "needs": ["aac"], "args": ["-c:a", "aac", "-b:a", "192k"]},

    {"ext": "aac", "kind": "audio", "label": "AAC audio (raw)",
     "needs": ["aac"], "args": ["-c:a", "aac", "-b:a", "192k"]},

    {"ext": "ogg", "kind": "audio", "label": "OGG audio (Vorbis)",
     "needs": ["libvorbis"], "args": ["-c:a", "libvorbis", "-q:a", "5"]},

    {"ext": "opus", "kind": "audio", "label": "Opus audio",
     "needs": ["libopus"], "args": ["-c:a", "libopus", "-b:a", "128k"]},

    {"ext": "wma", "kind": "audio", "label": "WMA audio",
     "needs": ["wmav2"], "args": ["-c:a", "wmav2", "-b:a", "192k"]}
]

QUALITY_PRESETS = {
    "small": {"h264": "29", "vp9": "39", "mpeg4": "7", "audio": "96k",
              "vorbis": "3", "gif_fps": 8, "gif_width": 320},

    "high": {"h264": "18", "vp9": "24", "mpeg4": "2", "audio": "256k",
             "vorbis": "7", "gif_fps": 20, "gif_width": 720}
}


def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        print()
        sys.exit(0)


def yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        answer = ask(f"{prompt} [{hint}]: ").strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def clean_path(raw: str) -> Path:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()

    p = Path(os.path.expanduser(s))

    if not p.exists() and os.name != "nt":
        alt = Path(os.path.expanduser(s.replace("\\ ", " ")))
        if alt.exists():
            return alt
    return p


def fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def check_tools() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit("Error: ffmpeg was not found on your PATH.\n"
                 "Install it using brew install ffmpeg, sudo apt install ffmpeg, "
                 "or winget install ffmpeg.")


def available_encoders():
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                           capture_output=True, text=True, check=True)
    except (subprocess.SubprocessError, OSError):
        return None

    names = set()
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
            names.add(parts[1])
    return names or None


def probe(path: Path):
    if shutil.which("ffprobe") is None:
        return None

    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_streams", "-show_format", str(path)],
                       capture_output=True, text=True)

    info = {"ok": False, "has_video": False, "has_audio": False, "duration": None}

    if r.returncode != 0:
        return info

    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return info

    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and not stream.get("disposition", {}).get("attached_pic"):
            info["has_video"] = True
        elif kind == "audio":
            info["has_audio"] = True

    try:
        duration = float(data.get("format", {}).get("duration"))
        if math.isfinite(duration) and duration > 0:
            info["duration"] = duration
    except (TypeError, ValueError):
        pass

    info["ok"] = info["has_video"] or info["has_audio"]
    return info


def menu_formats(info, encoders):
    fmts = FORMATS
    if info:
        if info["has_video"] and not info["has_audio"]:
            fmts = [f for f in fmts if f["kind"] == "video"]
        elif info["has_audio"] and not info["has_video"]:
            fmts = [f for f in fmts if f["kind"] == "audio"]

    if encoders:
        fmts = [f for f in fmts if all(n in encoders for n in f["needs"])]
    return fmts


def replace_option(args, flag, value):
    if flag in args:
        args[args.index(flag) + 1] = str(value)


def build_gif_filter(fps, width):
    return (f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];"
            "[s0]palettegen[p];[s1][p]paletteuse")


def quality_args(fmt, quality="standard"):
    args = list(fmt["args"])
    ext = fmt["ext"]

    if quality == "standard" or ext in ("wav", "flac"):
        return args

    preset = QUALITY_PRESETS[quality]

    if ext in ("mp4", "mkv", "mov"):
        replace_option(args, "-crf", preset["h264"])
    elif ext == "webm":
        replace_option(args, "-crf", preset["vp9"])
    elif ext == "avi":
        replace_option(args, "-q:v", preset["mpeg4"])
    elif ext == "ogg":
        replace_option(args, "-q:a", preset["vorbis"])
    elif ext == "gif":
        gif_filter = build_gif_filter(preset["gif_fps"], preset["gif_width"])
        replace_option(args, "-vf", gif_filter)

    if "-b:a" in args:
        bitrate = preset["audio"]
        if ext in ("webm", "opus") and quality == "high":
            bitrate = "192k"
        replace_option(args, "-b:a", bitrate)

    return args


def parse_timestamp(raw):
    parts = raw.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, MM:SS or HH:MM:SS.")

    values = [float(part) for part in parts]

    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("Time must be finite and non-negative.")

    if len(values) > 1:
        if any(not v.is_integer() for v in values[:-1]) or any(v >= 60 for v in values[1:]):
            raise ValueError("Invalid timestamp format.")

    return sum(v * 60 ** p for p, v in enumerate(reversed(values)))


def validate_trim(start, end, duration):
    if duration is not None and start >= duration:
        raise ValueError("Start must be before the end of the file.")

    if end is not None and end <= start:
        raise ValueError("End must be after start.")

    if duration is not None and end is not None and end > duration:
        raise ValueError("End is beyond the file duration.")


def step_trim(info):
    duration = info.get("duration") if info else None

    if not yes_no("\nConvert only a selected time range?"):
        return 0.0, None

    print("  Times: seconds, MM:SS, or HH:MM:SS.")

    while True:
        try:
            start = parse_timestamp(ask("  Start [0]: ").strip() or "0")
            raw = ask("  End [Enter = end of file]: ").strip()
            end = parse_timestamp(raw) if raw else duration

            validate_trim(start, end, duration)
            return start, end

        except ValueError as exc:
            print(f"  {exc}")


def step_quality(fmt):
    if fmt["ext"] in ("wav", "flac"):
        return "standard"

    choices = {"1": "standard", "2": "small", "3": "high",
               "standard": "standard", "small": "small", "high": "high"}

    print("\nQUALITY SETTINGS")
    print("  1) Standard (original settings)")
    print("  2) Smaller file")
    print("  3) Higher quality")

    while True:
        choice = ask("Select quality [1]: ").strip().lower() or "1"
        if choice in choices:
            return choices[choice]
        print("  Choose 1, 2 or 3.")


def conversion_duration(info, start, end):
    duration = info.get("duration") if info else None
    if end is not None:
        return end - start
    return max(0, duration - start) if duration else None


def build_command(src: Path, dest: Path, fmt: dict, start=0.0, end=None, quality="standard"):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
           "-progress", "pipe:1", "-nostats", "-y"]

    if start:
        cmd += ["-ss", str(start)]

    cmd += ["-i", str(src)]

    if end is not None:
        cmd += ["-t", str(end - start)]

    if fmt["kind"] == "audio":
        cmd += ["-vn", "-map", "0:a:0"]
    else:
        cmd += ["-map", "0:V:0"]
        if not fmt.get("no_audio"):
            cmd += ["-map", "0:a:0?"]
        else:
            cmd += ["-an"]

    cmd += quality_args(fmt, quality)
    cmd.append(str(dest))
    return cmd


def show_progress(done_seconds: float, duration) -> None:
    if duration:
        frac = max(0.0, min(done_seconds / duration, 1.0))
        filled = int(frac * 30)
        bar = "#" * filled + "-" * (30 - filled)
        sys.stdout.write(f"\r  [{bar}] {frac * 100:5.1f}%")
    else:
        sys.stdout.write(f"\r  Processed {fmt_time(done_seconds)}")
    sys.stdout.flush()


def process_progress(line, duration):
    key, _, value = line.strip().partition("=")
    if key in ("out_time_us", "out_time_ms"):
        try:
            show_progress(int(value) / 1_000_000, duration)
        except ValueError:
            pass


def run_ffmpeg(cmd: list, duration) -> tuple:
    with tempfile.TemporaryFile() as err_file:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, text=True)

        try:
            for line in proc.stdout:
                process_progress(line, duration)
            proc.wait()

        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
            raise

        finally:
            proc.stdout.close()

        if proc.returncode == 0:
            if duration:
                show_progress(duration, duration)
            print()
            return True, ""

        err_file.seek(0)
        print()
        return False, err_file.read().decode(errors="replace").strip()


def step_input():
    while True:
        raw = ask("\nPath of the file to convert (or 'q' to quit): ").strip()

        if raw.lower() in ("q", "quit", "exit"):
            sys.exit(0)
        if not raw:
            continue

        path = clean_path(raw)

        if not path.is_file():
            print(f"  Can't find a file at: {path}")
            continue

        info = probe(path)
        if info is not None and not info["ok"]:
            print("  That doesn't look like an audio or video file.")
            continue

        return path.resolve(), info


def describe(info) -> str:
    if not info:
        return ""

    parts = []
    if info["has_video"]:
        parts.append("video")
    if info["has_audio"]:
        parts.append("audio")

    text = " + ".join(parts)

    if info["duration"]:
        text += f", {fmt_time(info['duration'])} long"

    return text


def step_format(formats: list) -> dict:
    print("\nWhat format do you want?\n")
    ordered = []

    for kind, title in (("video", "VIDEO"), ("audio", "AUDIO ONLY")):
        group = [f for f in formats if f["kind"] == kind]

        if not group:
            continue

        print(f"  {title}")

        for f in group:
            ordered.append(f)
            print(f"   {len(ordered):>2}) {f['ext']:<5} - {f['label']}")

    while True:
        choice = ask("\nType the number: ").strip().lower().lstrip(".")

        if choice.isdigit() and 1 <= int(choice) <= len(ordered):
            return ordered[int(choice) - 1]

        match = [f for f in ordered if f["ext"] == choice]
        if match:
            return match[0]

        print(f"  Please enter a number from 1 to {len(ordered)}.")


def step_output_dir(src: Path) -> Path:
    while True:
        raw = ask(f"\nOutput folder [Enter = {src.parent}]: ").strip()
        folder = clean_path(raw).resolve() if raw else src.parent

        if folder.is_file():
            print("  That's a file, not a folder.")
            continue

        if not folder.exists():
            if not yes_no(f"  '{folder}' doesn't exist. Create it?", default=True):
                continue
            try:
                folder.mkdir(parents=True)
            except OSError as exc:
                print(f"  Couldn't create it: {exc}")
                continue

        return folder


def validate_filename(name):
    if name in (".", "..") or any(c in name for c in "/\\"):
        raise ValueError("The name can't contain slashes.")

    bad = sorted({c for c in name if c in '<>:"|?*' or ord(c) < 32})

    if bad:
        raise ValueError(f"The name can't contain: {' '.join(bad)}")


def step_filename(src: Path, folder: Path, fmt: dict) -> Path:
    ext = "." + fmt["ext"]

    while True:
        name = ask(f"\nFile name [Enter = {src.stem}]: ").strip()

        if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
            name = name[1:-1].strip()

        name = name or src.stem

        try:
            validate_filename(name)
        except ValueError as exc:
            print(f"  {exc}")
            continue

        if not name.lower().endswith(ext):
            name += ext

        dest = folder / name

        if dest.resolve() == src:
            print("  That would overwrite the original file. Choose a different name.")
            continue

        if dest.exists() and not yes_no(f"  '{dest.name}' already exists. Overwrite?"):
            continue

        return dest


def report_conversion(src, dest):
    print(f"Done! Saved to: {dest} ({fmt_size(dest.stat().st_size)})")


def create_temporary_output(dest):
    with tempfile.NamedTemporaryFile(prefix=".converting-", suffix=dest.suffix,
                                     dir=dest.parent, delete=False) as temporary:
        return Path(temporary.name)


def convert_safely(src, dest, fmt, info, start, end, quality):
    work = create_temporary_output(dest)

    try:
        command = build_command(src, work, fmt, start, end, quality)
        duration = conversion_duration(info, start, end)
        ok, error = run_ffmpeg(command, duration)

        if ok:
            work.replace(dest)
            report_conversion(src, dest)
        else:
            print("Conversion failed.")
            if error:
                print("  ffmpeg said:\n    " + error.replace("\n", "\n    "))

    except KeyboardInterrupt:
        print("\n  Cancelled. Partial file removed.")

    finally:
        work.unlink(missing_ok=True)


def convert_once() -> None:
    src, info = step_input()
    summary = describe(info)
    print(f"  Found: {src.name}" + (f"  ({summary})" if summary else ""))

    formats = menu_formats(info, ENCODERS)

    if not formats:
        print("  Your ffmpeg build has no compatible encoders.")
        return

    fmt = step_format(formats)
    start, end = step_trim(info)
    quality = step_quality(fmt)
    folder = step_output_dir(src)
    dest = step_filename(src, folder, fmt)

    if start or end is not None:
        end_text = f"{end:g}s" if end is not None else "end"
        print(f"  Time range: {start:g}s to {end_text}")

    print(f"\nConverting to {fmt['ext'].upper()} ({quality} quality)...")

    try:
        convert_safely(src, dest, fmt, info, start, end, quality)
    except OSError as exc:
        print(f"  Could not complete conversion: {exc}")


def main() -> None:
    global ENCODERS
    check_tools()
    ENCODERS = available_encoders()

    print("=" * 46)
    print("   Universal Audio / Video Converter")
    print("=" * 46)

    try:
        while True:
            convert_once()
            if not yes_no("\nConvert another file?", default=False):
                break
    except KeyboardInterrupt:
        print()

    print("Bye!")


ENCODERS = None

if __name__ == "__main__":
    main()
