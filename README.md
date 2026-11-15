# THE CROW'S NEST STUDIO 4.0

**Studio 4.0:** persistent prompt-to-documentary production queue, optional source-credited historical still images, fact-check review gate, voice library, local Ollama drafts, and verified GitHub Releases updater. See `STUDIO_4_0_GUIDE.md`. **To create your dedicated GitHub repository and connect releases:** run `Connect_GitHub_Once.bat` from the extracted source folder; the GitHub account owner and public/private visibility must be explicitly approved. The repository is not created until you authorize this action on your own computer.

---

# THE CROW'S NEST STUDIO 3.0

## Studio 3.0 — Prompt Drafts & Personal Voice Studio

Read `STUDIO_3_0_GUIDE.md` first for updated Windows instructions, voice permission/consent, cleanup, optional Qwen model installation, and limits.

---

# NEW IN 2.1.0: Kokoro natural narration and in-app voice auditioning

The default narrator is now Kokoro Onyx instead of Piper Lessac. Other US male Kokoro voices: Adam, Michael and Fenrir. Press Install selected voice once (~350 MB model download) then HEAR THIS VOICE to audition a short sample without rendering a video. Voice generation works offline after installation. Piper remains available as a legacy fallback. Full generation and MP4 export use the chosen voice, with a narration pace setting.

# THE CROW'S NEST | LOCAL PRODUCTION STUDIO

An independent, unofficial military history/news documentary production toolchain. Works for **9:16 Shorts** and **16:9 YouTube episodes**, with no built-in per-video rendering quotas.

## What is working

- Scripted episodes with multiple scenes (`episodes/*.json`)
- Automated scene rendering from image files, video files or generated title cards
- Local narration through Piper, or previously recorded/externally generated WAV narration
- Automated subtitles (.srt) and caption burn-in when FFmpeg includes libass
- Full-color transparent watermark automatically on every render
- Standard H.264/AAC MP4 output plus publishing manifest
- 1080×1920 Shorts and 1920×1080 long-form
- Optional local background music, no cloud API needed to render

**What isn't included:** a hosted LTX video model, free unlimited third-party stock clips, paid cloud AI generation, or automatic public social publishing. Local realistic AI footage requires compatible hardware, appropriate models and sufficient VRAM. No claim of HeyGen-equivalent quality is made for the Piper/basic visual fallback.

## Requirements

- Windows 10/11 or Linux
- Python 3.11+ (Pillow + Piper TTS installed by setup scripts)
- FFmpeg and FFprobe in PATH (a build with `libass` for burned captions)
- Internet only for initial installation/voice model download
- Optional NVIDIA GPU and [LTX Desktop](https://github.com/Lightricks/LTX-Desktop) for local AI visuals; CPU is enough for the basic production pipeline

## Desktop app v2.0 — Fact Check + Generate Narration + Render Video

The graphical app has **FACT CHECK**, **1 GENERATE NARRATION**, **Play narration**, **Install selected voice**, **2 RENDER VIDEO**, **System / Updates**, **Open exports**, and **Check setup**. Narration is saved and reused in `assets/narration/`; no new cloud video credits are consumed. The voice model must be installed on the computer. The new installer upgrades the old desktop app while preserving existing media and exports.

## Easy desktop interface

After setup, double-click `Launch_Studio_Windows.bat` (Windows), or run `./Launch_Studio_Linux.sh` (Linux). Paste a script with blank lines between scenes. Optionally supply footage files named `01.mp4`, `02.jpg`, etc., in a folder. Open **FACT CHECK** to review source evidence for each claim, then check the footage-rights box and click **RENDER VIDEO**. Choose Shorts, long-form, or both. The fact-check window can open official historical source searches, but does not automatically guarantee factual correctness. A storyboard with only background cards will not look like HeyGen.

## Windows desktop application

**2.0 source-led verification:** Final exports are blocked while any scripted claim is unreviewed, contradicted, or changed after review. Claims need an HTTPS citation, supporting excerpt and confirmed human comparison. Search result leads are not proof; see README_DESKTOP.md for details.


**Recommended:** double-click `Install_Desktop_App.bat` after extracting. It creates a proper desktop shortcut, Start-menu entry, application icon, and (when supported) `CrowsNestStudio.exe` launcher. See `README_DESKTOP.md`.

## Windows: first run

1. Extract the ZIP.
2. Install Python and FFmpeg (add FFmpeg to PATH).
3. Open PowerShell in the extracted folder and execute `powershell -ExecutionPolicy Bypass -File .\setup_windows.ps1`.
4. Run:
   ```powershell
   .\.venv\Scripts\python.exe studio.py render episodes\01_lookout_intro.json --format short
   ```
5. Find the MP4, SRT and publish metadata in `exports/`.

For a 16:9 upload, use `--format wide`. For high-quality narration, create per-scene WAVs externally (for example with Qwen3-TTS) and add each WAV file path as `"audio": "your/file.wav"` in the scene; the video renderer will use it instead of Piper.

## Linux

```bash
sudo apt install ffmpeg python3-venv
./setup_linux.sh
.venv/bin/python studio.py render episodes/01_lookout_intro.json --format short
```

## Fast test (does not need a TTS voice)

```bash
python studio.py doctor
python studio.py render episodes/01_lookout_intro.json --format short --silent-demo
```

**Silent demo outputs are only for render testing; do not upload them as finished videos.**

## Create an episode

Copy the JSON example, edit `slug`, `title`, `description`, and `scenes`.

- `narration`: exact words spoken.
- `heading`: fallback card headline.
- `visual`: optional local footage path (relative to the studio root), e.g. `assets/footage/archival_ship.mp4` or `assets/footage/ship.jpg`.
- `audio`: optional recorded narration path. If omitted, Piper is used.
- `sources`: research citations. Check ownership and licenses separately.
- `approved`: must be true for normal rendering; a complete per-claim fact-check ledger is also mandatory for non-demo exports.

For 8–15-minute videos, write 1,100–2,200 spoken words and divide them into **short scenes**. Don't just repeat 5 title cards for 10 minutes; use authentic footage, maps, and illustrative animations. Generate optional LTX clips and point scenes' `visual` paths to them.

## Quality & publishing

- Check factual claims against primary documents; never identify AI reenactment as actual historical footage.
- Keep a per-asset license log (DVIDS material sometimes has usage restrictions). Avoid implying DoD endorsement.
- Upload AI-altered/synthetic-content disclosures where applicable.
- Use **Buffer** for TikTok/YouTube Shorts if platform capabilities permit, and **YouTube Studio** for long-form documentaries.
- Google Drive archive: `voiceofthefleet@gmail.com` → `The Crow's Nest` → `02 - Ready to Publish` until posting, then `01 - Published`.
- The editing workflow is independent of cloud platforms. The exports are local files; Drive and Buffer integration still requires authorization and media transfer.

## Optional future upgrades

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) for more expressive local narration; generated WAVs drop straight in.
- [LTX Desktop](https://github.com/Lightricks/LTX-Desktop) for generated video clips on supported NVIDIA GPUs. Unsupported cards may trigger a paid API path; **disable API generation to avoid charges**.
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) for advanced pipelines (confirm model and GPU requirements).
- [DVIDS](https://www.dvidshub.net/) and U.S. National Archives for historical footage, with rights and attribution checks.

## Configuration

The watermark is `assets/branding/The_Crows_Nest_Watermark_512.png` and is applied automatically. To replace it, swap that file with another transparent PNG of the same name.

This package does **not** contain copyrighted third-party footage, downloaded models, or voice clones.

## Optional unlimited local script drafting with Ollama

Install [Ollama](https://ollama.com/) and pull a compatible local model (for example `ollama pull qwen3:8b`). Put reviewed primary-source notes in `research_notes.txt` and run:

```bash
python draft_with_ollama.py --topic "Why military lookouts mattered" --notes research_notes.txt --minutes 8
```

The tool uses only the locally running Ollama endpoint and outputs `approved: false`; factual review is mandatory. Source notes and research must be provided by you or another verified research process. Never automatically publish unverified AI news scripts.

## Important limitations

- This local editing engine has **no video-count quota**, but the output quality depends heavily on your source footage and narrator. A title-card-only video is not HeyGen-equivalent.
- Realistic AI video generation itself is **not installed**; LTX Desktop is an optional separate app with major NVIDIA hardware requirements and potentially paid API fallback on unsupported hardware.
- Professional local voice generation such as Qwen3-TTS is a separate optional setup; this package defaults to Piper for the easiest offline experience.
- Source videos and license records need human review. This is not a fully autonomous news agency.
