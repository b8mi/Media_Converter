
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CONFIG_FILE = Path.home() / ".media_converter_config.json"

H264 = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v", "libx264", "-preset", "medium",
        "-crf", "23", "-pix_fmt", "yuv420p"]

FORMATS = {
    "mp4": ("video", ["libx264", "aac"],
            H264 + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),

    "mkv": ("video", ["libx264", "aac"],
            H264 + ["-c:a", "aac", "-b:a", "192k"]),

    "mov": ("video", ["libx264", "aac"],
            H264 + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"]),

    "webm": ("video", ["libvpx-vp9", "libopus"],
             ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0",
              "-row-mt", "1", "-cpu-used", "4",
              "-c:a", "libopus", "-b:a", "128k"]),

    "avi": ("video", ["mpeg4", "libmp3lame"],
            ["-c:v", "mpeg4", "-q:v", "4",
             "-c:a", "libmp3lame", "-b:a", "192k"]),

    "gif": ("video", ["gif"], []),

    "mp3": ("audio", ["libmp3lame"], ["-c:a", "libmp3lame", "-b:a", "192k"]),
    "wav": ("audio", ["pcm_s16le"], ["-c:a", "pcm_s16le"]),
    "flac": ("audio", ["flac"], ["-c:a", "flac"]),
    "m4a": ("audio", ["aac"], ["-c:a", "aac", "-b:a", "192k"]),
    "aac": ("audio", ["aac"], ["-c:a", "aac", "-b:a", "192k"]),
    "ogg": ("audio", ["libvorbis"], ["-c:a", "libvorbis", "-q:a", "5"]),
    "opus": ("audio", ["libopus"], ["-c:a", "libopus", "-b:a", "128k"]),
    "wma": ("audio", ["wmav2"], ["-c:a", "wmav2", "-b:a", "192k"])
}

QUALITY = {
    "standard": {"h264": "23", "vp9": "32", "mpeg4": "4",
                 "audio": "192k", "vorbis": "5", "fps": 12, "width": 480},

    "small": {"h264": "29", "vp9": "39", "mpeg4": "7",
              "audio": "96k", "vorbis": "3", "fps": 8, "width": 320},

    "high": {"h264": "18", "vp9": "24", "mpeg4": "2",
             "audio": "256k", "vorbis": "7", "fps": 20, "width": 720}
}


def ask(prompt):
    return input(prompt).strip()


def yes_no(prompt, default=False):
    hint = "Y/n" if default else "y/N"

    while True:
        answer = ask(f"{prompt} [{hint}]: ").lower()

        if not answer:
            return default

        if answer in ("y", "yes"):
            return True

        if answer in ("n", "no"):
            return False

        print("Please enter y or n.")


def clean_path(raw):
    raw = raw.strip()

    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()

    path = Path(raw).expanduser()

    if not path.exists() and os.name != "nt":
        alternative = Path(raw.replace("\\ ", " ")).expanduser()

        if alternative.exists():
            return alternative

    return path


def load_config():
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            return data

    except (OSError, ValueError):
        pass

    return {}


def save_config(data):
    try:
        temporary = CONFIG_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(CONFIG_FILE)

    except OSError as error:
        print(f"Could not save preferences: {error}")


def get_last_output():
    saved = load_config().get("last_output_folder")

    if not isinstance(saved, str) or not saved:
        return None

    try:
        folder = Path(saved).expanduser()

        if folder.is_dir():
            return folder.resolve()

    except (OSError, ValueError):
        pass

    return None


def remember_output(folder):
    data = load_config()
    data["last_output_folder"] = str(folder.resolve())
    save_config(data)


def format_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"

    return f"{minutes}:{seconds:02d}"


def format_size(size):
    size = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.2f} {unit}"

        size /= 1024


def check_tools():
    if shutil.which("ffmpeg") is None:
        raise SystemExit("FFmpeg was not found on PATH.")


def available_encoders():
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, check=True
        )

        encoders = set()

        for line in result.stdout.splitlines():
            parts = line.split()

            if len(parts) >= 2 and len(parts[0]) == 6 and parts[0][0] in "VAS":
                encoders.add(parts[1])

        return encoders or None

    except (OSError, subprocess.SubprocessError):
        return None


def probe(path):
    if shutil.which("ffprobe") is None:
        return None

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams",
         "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return {"ok": False}

    try:
        data = json.loads(result.stdout)
    except ValueError:
        return {"ok": False}

    streams = data.get("streams", [])

    has_video = any(
        stream.get("codec_type") == "video"
        and not stream.get("disposition", {}).get("attached_pic")
        for stream in streams
    )

    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)

    try:
        duration = float(data.get("format", {}).get("duration"))

        if not math.isfinite(duration) or duration <= 0:
            duration = None

    except (ValueError, TypeError):
        duration = None

    return {
        "ok": has_video or has_audio,
        "has_video": has_video,
        "has_audio": has_audio,
        "duration": duration
    }


def step_input():
    while True:
        raw = ask("\nPath of file to convert (q to quit): ")

        if raw.lower() in ("q", "quit", "exit"):
            return None, None

        if not raw:
            continue

        path = clean_path(raw).resolve()

        if not path.is_file():
            print("File not found.")
            continue

        info = probe(path)

        if info is not None and not info["ok"]:
            print("Invalid audio or video file.")
            continue

        return path, info


def menu_formats(info, encoders):
    formats = []

    for ext, (kind, required, args) in FORMATS.items():
        if info is not None:
            if kind == "video" and not info["has_video"]:
                continue

            if kind == "audio" and not info["has_audio"]:
                continue

        if encoders is not None and not all(e in encoders for e in required):
            continue

        formats.append(ext)

    return formats


def step_format(formats):
    print("\nAVAILABLE FORMATS")

    for index, ext in enumerate(formats, 1):
        kind = FORMATS[ext][0]
        print(f"  {index:>2}) {ext.upper():<5} - {kind}")

    while True:
        choice = ask("Select format: ").lower().lstrip(".")

        if choice in formats:
            return choice

        if choice.isdigit() and 1 <= int(choice) <= len(formats):
            return formats[int(choice) - 1]

        print("Invalid format.")


def parse_timestamp(raw):
    parts = raw.split(":")

    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, MM:SS or HH:MM:SS.")

    values = [float(part) for part in parts]

    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Invalid timestamp.")

    if len(values) > 1:
        if any(not v.is_integer() for v in values[:-1]) or any(v >= 60 for v in values[1:]):
            raise ValueError("Invalid timestamp.")

    return sum(value * 60 ** index for index, value in enumerate(reversed(values)))


def step_trim(info):
    duration = info.get("duration") if info else None

    if not yes_no("Convert only a selected time range?"):
        return 0, None

    while True:
        try:
            start = parse_timestamp(ask("Start [0]: ") or "0")
            raw = ask("End [Enter = end of file]: ")
            end = parse_timestamp(raw) if raw else duration

            if duration is not None and start >= duration:
                raise ValueError("Start must be before the end.")

            if end is not None and end <= start:
                raise ValueError("End must be after start.")

            if duration is not None and end is not None and end > duration:
                raise ValueError("End exceeds file duration.")

            return start, end

        except ValueError as error:
            print(error)


def step_quality(ext):
    if ext in ("wav", "flac"):
        return "standard"

    choices = {
        "1": "standard",
        "2": "small",
        "3": "high"
    }

    print("\n1) Standard")
    print("2) Smaller file")
    print("3) Higher quality")

    while True:
        choice = ask("Quality [1]: ") or "1"

        if choice in choices:
            return choices[choice]

        if choice in QUALITY:
            return choice

        print("Invalid quality.")


def step_output_dir(src):
    previous = get_last_output()
    default = previous or src.parent

    while True:
        print(f"\nDefault output folder: {default}")

        if previous:
            print("Press Enter to reuse the previous output folder.")
            print("Type 'source' to use the input file's directory.")

        raw = ask("Output folder [Enter = default]: ")

        if raw.lower() == "source":
            folder = src.parent
        elif raw:
            folder = clean_path(raw).resolve()
        else:
            folder = default

        if folder.is_file():
            print("That path is a file.")
            continue

        if not folder.exists():
            if not yes_no("Folder does not exist. Create it?", True):
                continue

            try:
                folder.mkdir(parents=True, exist_ok=True)

            except OSError as error:
                print(f"Could not create folder: {error}")
                continue

        if folder.is_dir():
            return folder


def step_filename(src, folder, ext):
    while True:
        name = ask(f"Output filename [{src.stem}]: ") or src.stem

        if len(name) >= 2 and name[0] == name[-1] and name[0] in "\"'":
            name = name[1:-1].strip()

        if not name or name in (".", "..") or any(
            char in '<>:"/\\|?*' or ord(char) < 32 for char in name
        ):
            print("Invalid filename.")
            continue

        if not name.lower().endswith("." + ext):
            name += "." + ext

        destination = folder / name

        if destination.resolve() == src:
            print("Cannot overwrite the source file.")
            continue

        if destination.exists():
            if not destination.is_file():
                print("Destination is not a file.")
                continue

            if destination.samefile(src):
                print("Cannot overwrite the source file.")
                continue

            if not yes_no("File exists. Overwrite?"):
                continue

        return destination


def replace_option(args, option, value):
    if option in args:
        args[args.index(option) + 1] = str(value)


def quality_args(ext, quality):
    args = FORMATS[ext][2].copy()
    preset = QUALITY[quality]

    if ext == "gif":
        fps = preset["fps"]
        width = preset["width"]

        return [
            "-vf",
            f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
            "[a]palettegen[p];[b][p]paletteuse",
            "-loop", "0"
        ]

    if quality == "standard":
        return args

    if ext in ("mp4", "mkv", "mov"):
        replace_option(args, "-crf", preset["h264"])

    elif ext == "webm":
        replace_option(args, "-crf", preset["vp9"])

    elif ext == "avi":
        replace_option(args, "-q:v", preset["mpeg4"])

    elif ext == "ogg":
        replace_option(args, "-q:a", preset["vorbis"])

    bitrate = preset["audio"]

    if ext in ("opus", "webm") and quality == "high":
        bitrate = "192k"

    replace_option(args, "-b:a", bitrate)

    return args


def build_command(src, dest, ext, start, end, quality):
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-nostdin", "-progress", "pipe:1", "-nostats", "-y"
    ]

    if start:
        command += ["-ss", str(start)]

    command += ["-i", str(src)]

    if end is not None:
        command += ["-t", str(end - start)]

    if FORMATS[ext][0] == "audio":
        command += ["-vn", "-map", "0:a:0"]
    else:
        command += ["-map", "0:V:0"]

        if ext == "gif":
            command += ["-an"]
        else:
            command += ["-map", "0:a:0?"]

    command += quality_args(ext, quality)
    command.append(str(dest))

    return command


def show_progress(seconds, duration):
    if duration:
        fraction = max(0, min(seconds / duration, 1))
        filled = int(fraction * 30)

        bar = "#" * filled + "-" * (30 - filled)

        print(f"\r[{bar}] {fraction * 100:5.1f}%", end="", flush=True)

    else:
        print(f"\rProcessed: {format_time(seconds)}", end="", flush=True)


def run_ffmpeg(command, duration):
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=errors,
            text=True
        )

        try:
            for line in process.stdout:
                key, _, value = line.strip().partition("=")

                if key in ("out_time_us", "out_time_ms"):
                    try:
                        show_progress(int(value) / 1_000_000, duration)
                    except ValueError:
                        pass

            process.wait()

        except KeyboardInterrupt:
            process.terminate()

            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

            raise

        finally:
            process.stdout.close()

        print()

        if process.returncode == 0:
            return True, ""

        errors.seek(0)
        return False, errors.read().decode(errors="replace")


def convert_safely(src, dest, ext, info, start, end, quality):
    with tempfile.NamedTemporaryFile(
        prefix=".converting-",
        suffix=dest.suffix,
        dir=dest.parent,
        delete=False
    ) as temporary:
        work = Path(temporary.name)

    try:
        duration = info.get("duration") if info else None

        if end is not None:
            duration = end - start
        elif duration is not None:
            duration = max(0, duration - start)

        command = build_command(src, work, ext, start, end, quality)
        success, error = run_ffmpeg(command, duration)

        if not success:
            print(f"Conversion failed:\n{error}")
            return False

        work.replace(dest)

        print(f"Done! Saved to: {dest}")
        print(f"Output size: {format_size(dest.stat().st_size)}")

        remember_output(dest.parent)

        return True

    except KeyboardInterrupt:
        print("\nConversion cancelled.")
        return False

    except OSError as error:
        print(f"Conversion error: {error}")
        return False

    finally:
        work.unlink(missing_ok=True)


def convert_once(encoders):
    src, info = step_input()

    if src is None:
        return False

    print(f"\nFound: {src.name}")

    if info and info.get("duration"):
        print(f"Duration: {format_time(info['duration'])}")

    formats = menu_formats(info, encoders)

    if not formats:
        print("No compatible formats available.")
        return True

    ext = step_format(formats)
    start, end = step_trim(info)
    quality = step_quality(ext)

    folder = step_output_dir(src)
    destination = step_filename(src, folder, ext)

    print(f"\nConverting to {ext.upper()}...")

    convert_safely(
        src, destination, ext, info,
        start, end, quality
    )

    return True


def main():
    check_tools()
    encoders = available_encoders()

    print("=" * 48)
    print("      UNIVERSAL MEDIA CONVERTER")
    print("=" * 48)

    previous = get_last_output()

    if previous:
        print(f"Last output folder: {previous}")

    try:
        while True:
            if not convert_once(encoders):
                break

            if not yes_no("\nConvert another file?"):
                break

    except (KeyboardInterrupt, EOFError):
        print()

    print("Goodbye!")


if __name__ == "__main__":
    main()
