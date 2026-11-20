   
# Python Media Converter

A simple, local, offline **audio and video converter** created using Python and FFmpeg. To use it, run it in your terminal: select a file, choose a format, select your output location, and it will convert. No login, no uploads to the internet, and no conversion websites!

I built this as one simple script instead of a big media editor. It takes care of video-to-video, audio-to-audio conversions, and extracting audio from videos that contain an audio track.

## What it can do

- Convert between widely used video formats such as **MP4, MKV, MOV, WebM, and AVI**.
- Create an **animated GIF** from a video without sound.
- Grab an audio stream from a video in **MP3, WAV, FLAC, M4A, AAC, OGG, Opus, or WMA**.
- Check the input with `ffprobe` and list the supported output formats when available.
- Hide formats that require missing encoders from your FFmpeg build.
- Display a live progress bar during conversion if the file duration is known.
- Select an output folder and filename, with a prompt before overwriting an existing output file.
- Perform one more conversion without exiting the program.

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

The exact selections you get depend on the codecs supported by your FFmpeg installation and the audio/video streams in the source file. A video must contain an audio stream if you want to extract sound from it.

## Requirements

- **Python 3.8 or higher** (Recommended: Python 3.10+).
- **FFmpeg**, including the `ffmpeg` command available on your system's `PATH`.
- **FFprobe** is recommended for checking media streams and duration. It normally comes with FFmpeg.

You don't need to install any other third-party Python packages with pip. `converter.py` only uses Python's built-in modules, but FFmpeg is a separate program that you will have to install.

### Installing FFmpeg

- **Windows:** Download FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html), install a Windows build, and add its `bin` directory to your `PATH`.
- **macOS (Homebrew):** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`

Verify the installation in a new terminal:

```bash
ffmpeg -version
ffprobe -version
```

If the commands are not recognized, FFmpeg may not be installed or might not be on your `PATH` yet.

## How to use

1. Download this repository or clone it.
2. Open a terminal in your repository folder.
3. Run the converter:

   ```bash
   python converter.py
   ```

   On some systems, use `python3 converter.py` instead.

4. Paste or drag in the path of the audio or video file.
5. Select an output format from the list by **number** or **extension** (e.g., `mp3`).
6. Select an output folder. Hit **Enter** to save it in the same folder as the source file.
7. Specify a new filename. Hit **Enter** to keep the existing name and change only the extension.
8. Allow the conversion to complete. The script will show the path and size of the saved file. You can then proceed to convert another file.

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

*The prompts shown are just an example. The format menu and progress details depend on the file.*

## A few useful details

- **Offline:** After the initial installation of Python and FFmpeg, everything gets converted locally. The script never uploads your files.
- **Quality:** Converting to a lossy format (like MP3 or H.264 video) can reduce quality. Converting already compressed audio to FLAC or WAV will not recover whatever quality was already lost.
- **GIFs:** The GIF preset generates an animated image at about 12 frames per second, scales it to 480 pixels wide, and excludes the sound.
- **Input files:** The converter takes **one source file at a time**. It is not a video editor or a batch file merging tool.
- **Progress:** Shows a percentage if the file duration is available through FFprobe. Otherwise, it shows elapsed media time.
- **Output safety:** The script will never overwrite the source file. If the output file already exists, it asks before replacing it.
- **Encoder availability:** Not all FFmpeg builds include encoders like `libx264`, `libvpx-vp9`, or `libopus`. If they are missing, the formats that require them will not appear.

## Repository files

```text
Python-Media-Converter/
├── converter.py            # Audio/video conversion script
├── README.md               # Instructions and format information
├── requirements.txt        # Python dependency note
├── .gitignore              # Local and temporary files to ignore
└── GITHUB-DESCRIPTION.txt  # Brief description for the GitHub About field
```

## Project notes

It's a CLI program, not a GUI. It is meant for quick, day-to-day conversions and doesn't require an internet connection after installation.

When reporting format issues, include the source file type, chosen output format, and the FFmpeg error message. Just make sure not to share any private media files.
