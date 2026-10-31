# Python Media Converter

A small, offline **audio and video converter** built with Python and FFmpeg. It runs in your terminal: choose a file, pick a format, set the output location, and let it convert. No account, cloud upload, or online conversion website needed.

I made this as one straightforward script instead of a large media editor. It handles video-to-video conversions, audio-to-audio conversions, and extracting audio from videos that have an audio track.

## What it can do

- Convert video between popular formats, including **MP4, MKV, MOV, WebM, and AVI**.
- Turn a video into an **animated GIF** (without sound).
- Extract an audio track from video as **MP3, WAV, FLAC, M4A, AAC, OGG, Opus, or WMA**.
- Inspect the input with `ffprobe` and list relevant output formats when available.
- Hide formats whose required encoders are missing from your FFmpeg build.
- Show a live conversion progress bar when the file duration can be detected.
- Choose an output folder and filename, with prompts before replacing an existing output.
- Run another conversion without restarting the program.

## Supported output formats

| Video / animation | Audio only |
| --- | --- |
| MP4 (H.264 + AAC) | MP3 |
| MKV (H.264 + AAC) | WAV |
| MOV (H.264 + AAC) | FLAC |
| WebM (VP9 + Opus) | M4A (AAC) |
| AVI (MPEG-4 + MP3) | AAC |
| Animated GIF | OGG (Vorbis) |
| | Opus |
| | WMA |

The exact choices you see depend on the codecs supported by your FFmpeg installation and the audio/video streams present in your source file. A video must contain audio if you want to extract sound from it.

## Requirements

- **Python 3.8 or newer** (Python 3.10+ recommended).
- **FFmpeg**, including the `ffmpeg` command available on your system's `PATH`.
- **FFprobe** is recommended for detecting media streams and duration. It normally comes with FFmpeg.

There are **no third-party Python packages** to install with pip. `converter.py` uses only Python's standard library, but FFmpeg itself is a separate program that you need to install.

### Installing FFmpeg

- **Windows:** Get FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html), install a Windows build, and add its `bin` folder to your `PATH`.
- **macOS (Homebrew):** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

Check the installation in a new terminal:

```bash
ffmpeg -version
ffprobe -version
```

If the commands are not recognized, FFmpeg may not be installed or may not be on your `PATH` yet.

## How to use

1. Download this repository or clone it.
2. Open a terminal in the repository folder.
3. Run the converter:

   ```bash
   python converter.py
   ```

   On some systems, use `python3 converter.py` instead.

4. Paste or drag in the path of an audio or video file.
5. Choose an output format from the menu by **number** or **extension** (for example, `mp3`).
6. Choose an output folder. Press **Enter** to use the source file's folder.
7. Enter a new filename. Press **Enter** to keep the original name with the new extension.
8. Let the conversion finish; the script prints the saved file's path and size. You can then convert another file.

### Example

```text
Path of the file to convert (or 'q' to quit): C:\Videos\clip.mp4
  Found: clip.mp4 (video + audio, 1:24 long)

What format do you want?
  ...

Type the number: mp3
Output folder [Enter = C:\Videos]:
File name [Enter = clip]: voice-only

Converting to MP3...
  [##############################] 100.0%
Done! Saved to: C:\Videos\voice-only.mp3
```

*This is an illustrative example of the prompts; the format menu and progress details vary by file.*

## A few useful details

- **Offline:** Once Python and FFmpeg are installed, the conversion happens locally. The script does not upload your files.
- **Quality:** Converting to a lossy format (such as MP3 or H.264 video) can reduce quality. Converting a previously compressed file to FLAC or WAV cannot restore quality already lost.
- **GIFs:** The GIF preset creates an animated image at about 12 frames per second, scales it to 480 pixels wide, and removes audio.
- **Input files:** The converter processes **one source file at a time**. It is not a video editor or a batch merging tool.
- **Progress:** A percentage is shown when FFprobe can determine the duration; otherwise, elapsed media time is displayed.
- **Output safety:** The script refuses to overwrite the *source* file. If another output file already exists, it asks for confirmation before replacing it.
- **Encoder availability:** Some FFmpeg builds lack codecs such as `libx264`, `libvpx-vp9`, or `libopus`, so the corresponding formats may not appear.

## Repository files

```text
Python-Media-Converter/
├── converter.py            # Audio/video conversion script
├── README.md               # Instructions and format information
├── requirements.txt        # Python dependency note
├── .gitignore              # Local and temporary files to exclude
└── GITHUB-DESCRIPTION.txt  # Short description for the GitHub About field
```

## Project notes

This is a command-line tool, not a graphical application. It is designed for quick, everyday conversions without an internet connection after setup. If you find a format that fails, include the source type, selected output format, and FFmpeg error message when reporting the issue (avoid sharing private media files).
