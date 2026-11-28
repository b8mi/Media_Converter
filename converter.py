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
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3600000)
    minutes, remainder = divmod(remainder, 60000)
    seconds, milliseconds = divmod(remainder, 1000)

    result = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    if milliseconds:
        result += f".{milliseconds:03d}"

    return result


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

    has_audio = any(
        stream.get("codec_type") == "audio"
        for stream in streams
    )

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
    parts = raw.strip().split(":")

    if not 1 <= len(parts) <= 3:
        raise ValueError("Use seconds, MM:SS or HH:MM:SS.")

    if any(not part.strip() for part in parts):
        raise ValueError("Invalid timestamp.")

    try:
        values = [float(part) for part in parts]

    except ValueError:
        raise ValueError("Timestamp must contain numbers.")

    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Invalid timestamp.")

    if len(values) > 1:
        if any(not value.is_integer() for value in values[:-1]):
            raise ValueError("Only seconds can contain decimals.")

        if any(value >= 60 for value in values[1:]):
            raise ValueError("Minutes and seconds must be below 60.")

    seconds = sum(
        value * 60 ** index
        for index, value in enumerate(reversed(values))
    )

    if not math.isfinite(seconds):
        raise ValueError("Timestamp is too large.")

    return seconds


def validate_trim(start, end, duration=None):
    if not math.isfinite(start) or start < 0:
        raise ValueError("Start time must be nonnegative.")

    if end is not None:
        if not math.isfinite(end) or end <= start:
            raise ValueError("End time must be after start time.")

    if duration is not None:
        if start >= duration:
            raise ValueError("Start time exceeds the file duration.")

        if end is not None and end > duration:
            raise ValueError("End time exceeds the file duration.")

    return start, end


def trimmed_duration(info, start, end):
    duration = info.get("duration") if info else None

    if end is not None:
        return end - start

    if duration is not None:
        return max(0, duration - start)

    return None


def show_trim_preview(start, end, duration=None):
    actual_end = end if end is not None else duration

    print("\nTRIM PREVIEW")
    print(f"Start: {format_time(start)}")

    if actual_end is not None:
        print(f"End: {format_time(actual_end)}")
        print(f"Selected duration: {format_time(actual_end - start)}")

    else:
        print("End: End of file")

    if duration is not None and actual_end is not None:
        width = 40
        left = min(width - 1, int(start / duration * width))
        right = min(width, math.ceil(actual_end / duration * width))
        right = max(left + 1, right)

        bar = "".join(
            "=" if left <= index < right else "-"
            for index in range(width)
        )

        percentage = (actual_end - start) / duration * 100

        print(f"[{bar}]")
        print(f"Selected: {percentage:.1f}% of the file")


def step_trim(info, batch=False, filename=None):
    duration = info.get("duration") if info else None

    print("\nTRIMMING")

    if filename:
        print(f"File: {filename}")

    if duration is not None:
        print(f"Original duration: {format_time(duration)}")

    if not yes_no("Convert only a selected time range?"):
        return 0, None

    print("Accepted formats: seconds, MM:SS, HH:MM:SS")
    print("Decimal seconds are supported.")
    print("Example: 00:01:30.500")

    while True:
        try:
            raw_start = ask("Start time [0]: ") or "0"
            start = parse_timestamp(raw_start)

            raw_end = ask("End time [Enter = end of file]: ")
            end = parse_timestamp(raw_end) if raw_end else None

            validate_trim(start, end, duration)

            preview_duration = duration

            if batch and end is None:
                preview_duration = None

            show_trim_preview(start, end, preview_duration)

            if yes_no("Use this time range?", True):
                return start, end

            if not yes_no("Enter another time range?", True):
                return 0, None

        except ValueError as error:
            print(f"Invalid range: {error}")


def step_batch_trim(files):
    print("\nBATCH TRIMMING")
    print("1) Convert entire files")
    print("2) Apply the same time range to every file")
    print("3) Choose a separate range for each file")

    while True:
        choice = ask("Trimming mode [1]: ") or "1"

        if choice == "1":
            return {src: (0, None) for src, info in files}

        if choice == "2":
            durations = [
                info["duration"]
                for src, info in files
                if info and info.get("duration")
            ]

            shortest = min(durations) if durations else None
            trim_info = {"duration": shortest}

            if shortest is not None:
                print(f"Shortest file: {format_time(shortest)}")

            start, end = step_trim(trim_info, batch=True)

            return {
                src: (start, end)
                for src, info in files
            }

        if choice == "3":
            selections = {}

            for index, (src, info) in enumerate(files, 1):
                print(f"\nFile {index}/{len(files)}")

                selections[src] = step_trim(
                    info, filename=src.name
                )

            return selections

        print("Invalid trimming mode.")


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


def step_filename(src, folder, ext, trimmed=False):
    default = src.stem + "_trimmed" if trimmed else src.stem

    while True:
        name = ask(f"Output filename [{default}]: ") or default

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
    validate_trim(start, end)

    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-nostdin", "-progress", "pipe:1", "-nostats", "-y"
    ]

    if start > 0:
        command += ["-ss", f"{start:.6f}"]

    if end is not None:
        command += ["-t", f"{end - start:.6f}"]

    command += ["-i", str(src)]

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

        print(
            f"\r[{bar}] {fraction * 100:5.1f}% "
            f"{format_time(seconds)} / {format_time(duration)}",
            end="", flush=True
        )

    else:
        print(
            f"\rProcessed: {format_time(seconds)}",
            end="", flush=True
        )


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
                        show_progress(int(value) / 1000000, duration)

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

        if process.returncode == 0:
            if duration:
                show_progress(duration, duration)

            print()
            return True, ""

        print()
        errors.seek(0)

        return False, errors.read().decode(errors="replace")


def convert_safely(src, dest, ext, info, start, end, quality, batch=False):
    work = None

    try:
        original_duration = info.get("duration") if info else None
        validate_trim(start, end, original_duration)

        if dest.resolve() == src.resolve():
            raise ValueError("Cannot overwrite the source file.")

        if dest.exists() and dest.samefile(src):
            raise ValueError("Cannot overwrite the source file.")

        with tempfile.NamedTemporaryFile(
            prefix=".converting-",
            suffix=dest.suffix,
            dir=dest.parent,
            delete=False
        ) as temporary:
            work = Path(temporary.name)

        duration = trimmed_duration(info, start, end)

        command = build_command(
            src, work, ext, start, end, quality
        )

        success, error = run_ffmpeg(command, duration)

        if not success:
            print(f"Conversion failed:\n{error}")
            return False

        if not work.exists() or work.stat().st_size == 0:
            print("Conversion produced an empty file.")
            return False

        work.replace(dest)

        print(f"Done! Saved to: {dest}")
        print(f"Output size: {format_size(dest.stat().st_size)}")

        output_info = probe(dest)

        if output_info and output_info.get("duration"):
            print(f"Output duration: {format_time(output_info['duration'])}")

        remember_output(dest.parent)

        return True

    except KeyboardInterrupt:
        print("\nConversion cancelled.")

        if batch:
            raise

        return False

    except (OSError, ValueError) as error:
        print(f"Conversion error: {error}")
        return False

    finally:
        if work is not None:
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
    start, end = step_trim(info, filename=src.name)
    quality = step_quality(ext)

    folder = step_output_dir(src)
    trimmed = start > 0 or end is not None

    destination = step_filename(
        src, folder, ext, trimmed=trimmed
    )

    print(f"\nConverting to {ext.upper()}...")

    convert_safely(
        src, destination, ext, info,
        start, end, quality
    )

    return True


def batch_input():
    files = []
    seen = set()

    extensions = set(FORMATS) | {
        "m4v", "mpeg", "mpg", "wmv", "flv", "ts",
        "mts", "m2ts", "3gp", "aiff", "aif", "mka",
        "oga", "ogv", "amr", "ac3"
    }

    print("\nEnter file or folder paths separated by semicolons.")
    print("Press Enter on an empty line when done.")
    print("Type q to cancel.")

    while True:
        raw = ask("Add files: ")

        if raw.lower() in ("q", "quit", "exit"):
            return []

        if not raw:
            if files:
                return files

            print("Add at least one media file.")
            continue

        whole = clean_path(raw)

        if whole.exists():
            paths = [whole]

        else:
            paths = [
                clean_path(part)
                for part in raw.split(";")
                if part.strip()
            ]

        for path in paths:
            if path.is_dir():
                candidates = sorted(
                    p for p in path.iterdir()
                    if p.is_file()
                    and p.suffix.lower().lstrip(".") in extensions
                )

            elif path.is_file():
                candidates = [path]

            else:
                print(f"Path not found: {path}")
                continue

            for candidate in candidates:
                src = candidate.resolve()

                if src in seen:
                    print(f"Already added: {src.name}")
                    continue

                info = probe(src)

                if info is not None and not info["ok"]:
                    print(f"Skipped invalid media: {src.name}")
                    continue

                seen.add(src)
                files.append((src, info))

                print(f"Added: {src.name}")

        print(f"{len(files)} files queued.")


def batch_destination(src, folder, ext, sources, trimmed=False):
    name = src.stem + "_trimmed" if trimmed else src.stem
    destination = folder / f"{name}.{ext}"
    number = 1

    while (
        destination.exists()
        or destination.is_symlink()
        or destination.resolve() in sources
    ):
        destination = folder / f"{name}_{number}.{ext}"
        number += 1

    return destination


def show_batch_summary(files, selections, ext, quality, folder):
    print("\nBATCH SETTINGS")
    print(f"Files: {len(files)}")
    print(f"Format: {ext.upper()}")
    print(f"Quality: {quality}")
    print(f"Output folder: {folder}")

    total_duration = 0
    known_duration = True

    for index, (src, info) in enumerate(files, 1):
        start, end = selections[src]
        duration = trimmed_duration(info, start, end)

        print(f"\n{index}. {src.name}")
        print(f"   Start: {format_time(start)}")

        if end is not None:
            print(f"   End: {format_time(end)}")

        else:
            print("   End: End of file")

        if duration is not None:
            print(f"   Selected duration: {format_time(duration)}")
            total_duration += duration

        else:
            known_duration = False

    if known_duration:
        print(f"\nTotal selected duration: {format_time(total_duration)}")


def convert_batch(encoders):
    files = batch_input()

    if not files:
        return True

    print("\nBATCH CONVERSION")
    print(f"Total files: {len(files)}")

    for index, (src, info) in enumerate(files, 1):
        size = format_size(src.stat().st_size)

        if info and info.get("duration"):
            duration = format_time(info["duration"])
            print(f"{index}. {src.name} | {size} | {duration}")

        else:
            print(f"{index}. {src.name} | {size}")

    formats = list(FORMATS)

    for src, info in files:
        supported = menu_formats(info, encoders)
        formats = [ext for ext in formats if ext in supported]

    if not formats:
        print("No single output format is compatible with every file.")
        return True

    ext = step_format(formats)
    quality = step_quality(ext)
    selections = step_batch_trim(files)

    print("\nChoose one output folder for the entire batch.")

    folder = step_output_dir(files[0][0])
    sources = {src for src, info in files}

    failed = []
    successful = 0

    show_batch_summary(
        files, selections, ext, quality, folder
    )

    if not yes_no("\nStart batch conversion?", True):
        return True

    for index, (src, info) in enumerate(files, 1):
        start, end = selections[src]
        trimmed = start > 0 or end is not None

        print(
            f"\n[{index}/{len(files)}] "
            f"Converting {src.name} to {ext.upper()}..."
        )

        try:
            destination = batch_destination(
                src, folder, ext, sources, trimmed
            )

            if convert_safely(
                src, destination, ext, info,
                start, end, quality, batch=True
            ):
                successful += 1

            else:
                failed.append(src)

        except OSError as error:
            print(f"Conversion error: {error}")
            failed.append(src)

        except KeyboardInterrupt:
            print(f"\nBatch stopped. {successful}/{len(files)} files converted.")
            return False

        completed = index / len(files)
        filled = int(completed * 30)
        bar = "#" * filled + "-" * (30 - filled)

        print(f"Batch progress: [{bar}] {completed * 100:.1f}%")

    print("\n" + "=" * 48)
    print("BATCH CONVERSION COMPLETE")
    print("=" * 48)

    print(f"Total files: {len(files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {len(failed)}")
    print(f"Output folder: {folder}")

    if failed:
        print("\nFailed files:")

        for src in failed:
            print(f"  {src}")

    return True


def step_mode():
    print("\n1) Convert a single file")
    print("2) Convert multiple files")
    print("q) Quit")

    while True:
        choice = ask("Mode [1]: ").lower() or "1"

        if choice in ("1", "2", "q", "quit", "exit"):
            return choice

        print("Invalid mode.")


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
            mode = step_mode()

            if mode in ("q", "quit", "exit"):
                break

            if mode == "1" and not convert_once(encoders):
                break

            if mode == "2" and not convert_batch(encoders):
                break

            if not yes_no("\nStart another conversion?"):
                break

    except (KeyboardInterrupt, EOFError):
        print()

    print("Goodbye!")


if __name__ == "__main__":
    main()
