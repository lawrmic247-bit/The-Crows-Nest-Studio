# THE CROW'S NEST STUDIO 3.0

## Studio 3.0 — Prompt Drafts & Personal Voice Studio

Read `STUDIO_3_0_GUIDE.md` first for updated Windows instructions, voice permission/consent, cleanup, optional Qwen model installation, and limits.

---

# THE CROW'S NEST STUDIO 2.1 — NATURAL NARRATION UPGRADE

This fixes the synthetic-sounding default voice. The app now defaults to **Kokoro Onyx** and offers Adam, Michael and Fenrir voices to audition. It retains Piper only for compatibility with existing projects.

1. Close the running Studio 2.0.
2. Extract the complete new ZIP to a NEW folder. Run `Install_Desktop_App.bat` from the extracted folder. It upgrades the existing installation and retains your existing footage, scripts, voice models and exports.
3. Open The Crow's Nest Studio using its desktop shortcut.
4. Choose **Kokoro Onyx** from the narrator list; click **Install selected voice** (downloads the Kokoro Python engine and official model assets, ~350 MB, once).
5. Click **HEAR THIS VOICE**. Try Onyx, Adam, Michael, Fenrir. Changing between Kokoro presets uses the same downloaded model, so further narrator auditions are offline.
6. Once you like a preset, click **1 GENERATE NARRATION**, then **Play full narration**, and finally **2 RENDER VIDEO** after completing the Fact Check review.

Voice model source: https://github.com/thewh1teagle/kokoro-onnx (MIT Python engine; Apache-2.0 model). Model downloads occur only when the user clicks Install selected voice. Voice quality is subjective; Kokoro is generally more natural than Piper but cannot promise exact HeyGen voice quality. High-end Qwen3-TTS remains an optional future integration depending on available GPU and performance.

Actual voice/audio generation still needs to be tested on your Windows PC. Python syntax, compatibility of the documented engine interface, and synthetic integration tests are verified in the packaged build; the 350 MB voice weights are not included.

## Previous installation notes

# THE CROW'S NEST STUDIO — WINDOWS DESKTOP EDITION v1.2

## Upgrade from an earlier Desktop Edition

Close the app, extract the **v1.2 ZIP** into its own new folder, and double-click **Install_Desktop_App.bat**. The installer updates the GUI and renderer without intentionally replacing your existing episodes, source footage, voice models or exports. Do not delete your old files until the upgraded app works.

## Install without having to type PowerShell commands

1. Extract **the entire ZIP** into a folder. Do not run the installer while it is still inside the ZIP.
2. Double-click **Install_Desktop_App.bat**. If Windows displays a security warning, review the scripts and choose to run only if you trust the package.
3. The installer detects your FFmpeg installation and installs Python 3.12 alongside your existing Python 3.14 if needed.
4. It installs the studio in `%LOCALAPPDATA%\Programs\TheCrowsNestStudio`, creates a separate virtual environment, and tries to install Piper narration and the default voice model.
5. It builds `CrowsNestStudio.exe` on your Windows machine using PyInstaller when available. If the build fails, it creates a functioning desktop shortcut targeting Pythonw and the same Tkinter GUI. Either way, no terminal is required to launch the editor after installation.
6. Use **The Crows Nest Studio** icon on your Desktop or Start menu.

**No paid API or HeyGen account is needed for local editing or for unlimited renders.** LTX AI video generation is **not included**, and quality depends on your own source visuals/footage and narration. This isn't a self-contained portable EXE: the Windows launcher uses the app's private Python environment and system FFmpeg.

## Inside the desktop app
- Enter a video title and narrated script.
- Select a narrator; click **Install selected voice** if the voice model is absent (one-time download).
- Click **1 GENERATE NARRATION** and listen with **Play narration**. These buttons are visible without any PowerShell commands.
- Click **2 RENDER VIDEO** to build a final MP4. It can generate missing narration automatically if your voice is installed.
- Separate scenes with a blank line.
- Add matching numbered clips `01.mp4`, `02.jpg`, etc. in a footage folder.
- Choose Shorts, 16:9 YouTube, or both.
- Review and confirm historical accuracy and footage rights.
- Click **RENDER VIDEO**. A watermark, captions and publishing manifest are generated.
- Use **Check setup** to see whether FFmpeg, Piper and voices are available.
- Use **Open exports folder** to access finished MP4/SRT files.

## Install location and update behavior
App: `%LOCALAPPDATA%\Programs\TheCrowsNestStudio`

Exports: `%LOCALAPPDATA%\Programs\TheCrowsNestStudio\exports`

Re-running the desktop installer will update the application files while keeping existing episodes, added footage, downloaded voices, and exported videos. Do not delete the app folder without backing up your projects and exports.

## Optional software
- Piper narration is downloaded during setup if available. Audio-only WAV files can be used instead.
- Windows desktop EXE is built locally by PyInstaller to match your PC. It is a launcher, not a bundled standalone AI model.
- For cinematic generated footage, add compatible external AI video generators and incorporate their MP4 clips in the footage folder.

## Troubleshooting
- If app starts but does not narrate: press **Check setup**, and rerun installer if the voice model is missing.
- If installation fails on Python: rerun installer after Python 3.12 installation; Python 3.14 remains untouched.
- If a render fails: open the log pane in the app and examine the first error.
- The original `setup_windows.ps1` is the older manual setup. For the desktop app, use `Install_Desktop_App.bat` instead.
- If the Windows EXE build is blocked by security software, the installer falls back to a desktop shortcut launching Pythonw rather than disabling the GUI.

The Crow's Nest is independent and unofficial. It is not a Department of Defense channel.

---

# Studio 2.0 — Verified releases and fact-checking

**Version 2.0.0** brings three main changes:

1. **FACT CHECK:** The studio scans every narration sentence, flags dates, quantities, causal and absolute statements, and opens an evidence register. Mark claims supported only after comparing the claim with a trustworthy source and recording its **HTTPS source URL and specific supporting excerpt**. Each row must have a human review confirmation. If a claim includes a numeric date or value, the cited excerpt must contain that same number. Claims without valid evidence, disputed claims, and claims edited after review prevent ordinary video rendering. Editorial statements can be exempted only with a reason and explicit confirmation. A source audit report can be exported from the checker.
2. **System / Updates:** The studio can look for a newer verified version in a **trusted GitHub Releases repository** when the app launches. The repo must be configured first. If a new release is available, the app asks permission to install it, verifies the SHA-256 digest, rejects unexpected files, stages the update, and restarts. It preserves episodes, source footage, narrator models, exported videos, and evidence ledgers. It rolls back changed code on failed validation.
3. **Health checks:** The studio checks FFmpeg, FFprobe, Python, Pillow, Piper, watermark, the fact-checking engine, and the updater. An online update source is optional.

**Accuracy limitations:** This is a **source-led editorial fact-checking workflow**, not a guarantee that a claim is true. It does not independently prove a quote is authentic, infer logical entailment, or automatically resolve contradictory or breaking news. Official evidence and independent corroboration should be reviewed by a person. Do not treat a search result snippet or AI answer as a verified citation. Historical interpretation should be distinguished from a demonstrable fact. Always check source dates and archive provenance.

**Upgrade:** Exit the old desktop app, extract the Studio 2.0 installer ZIP into a fresh folder, then double-click `Install_Desktop_App.bat`. It updates the existing installation in `%LOCALAPPDATA%\Programs\TheCrowsNestStudio` and keeps existing projects. Existing unreviewed episodes remain; they will require a fact-check report before the next final export. Silent demo renders can still be produced for software testing.

**Automatic updates require a trusted release source.** Until a dedicated Crow's Nest GitHub repository and matching releases are available, the updater is installed but cannot download future versions. To enable it, select **System / Updates**, enter the exact trusted `owner/repository`, and allow the first update check. Do not enter an untrusted third-party repository. When preparing releases, `build_release.py` creates a verified, code-only ZIP. Use the matching `vX.Y.Z` tag and release asset filename from the generated output. Never distribute unreviewed code using this mechanism.

**Local privacy:** Your scripts and research evidence stay in your installation folder. The fact checker opens a browser search only when you select **Find official sources** or **Find other sources**. The update checker contacts GitHub only after a trusted repo is configured. The program does not automatically transmit your scripts to an AI API or publish videos.
