# STUDIO 4.7 — GUIDED DOCUMENTARY PRODUCTION

The main window is a five-stage guided production wizard with a **fixed Back / Continue bar**. Later steps remain locked until their prerequisites are complete. Every required task appears on the same page where it is needed.

1. **STEP 1 · BRIEF + MODEL FIRST.** Choose an installed **Ollama script-writing model first**. Studio checks the actual installed models; if none is available, use **Install / setup** right there. Then enter your topic, film length, visual treatment and Full/Shorts/TikTok outputs. **Continue** verifies that the exact model you selected still exists before any automatic research or writing starts. An animated-realism choice also verifies that a compatible local ComfyUI workflow is selected and running before research starts. A saved explicit model can be reused for later films.
2. **STEP 2 · RESEARCH + SCRIPT + SOURCE REVIEW.** Studio retrieves source leads and drafts the different scripts. Inspect the original research links, edit the text, and use the **embedded evidence desk on the SAME PAGE**. Clear every factual claim with supporting evidence or an appropriate documented editorial exemption before Continue unlocks narration. Source leads alone never count as verification.
3. **STEP 3 · NARRATION.** Pick a voice, generate the complete scene-by-scene narration, **play the generated audio**, and check the approval box. Continue refuses to advance when audio is absent, unplayed or unapproved. Changing the manuscript or voice invalidates earlier audio approvals.
4. **STEP 4 · MEDIA + RENDER.** The editor displays the selected visual assets and their provenance. If local AI reenactments were selected, Continue **first prepares those clips after factual clearance**, then displays them for rights and relevance review; it changes to **Render the Video** only after preparation. Generated AI scenes are labeled illustrative. Asset rights must be approved **after** all generated clips are present. Rendering will never secretly add new footage after rights approval, or secretly generate a missing narration track.
5. **STEP 5 · SCREEN + PUBLISH.** Preview the completed MP4. Confirm the final upload explicitly, then Studio opens the Buffer composer and export folder. **Nothing is automatically published.**

**Model selection is not buried in Settings.** The first production page shows the current locally installed Ollama choices. Imported ChatGPT inbox jobs and Advanced Create also require a previously explicitly chosen installed writing model before beginning automatic generation; unconfigured imports wait safely in Needs Work.

**Simple UI:** cinematic Crow's Nest sidebar, persistent Back / Continue, low-glare dark and soft-light themes, adjustable text scale, scrollable pages, project library with queue/review/archive stages, and one primary next action. Technical integrations live in Tools rather than interrupting the normal workflow. Only advanced operations or external media viewers may open separate windows.

**Verification limits:** automated GitHub regressions cover code, offline model preflight, app-window launch and simulated transitions. Real Windows speaker playback, chosen ComfyUI workflow and GPU performance, third-party Buffer publishing, and archival licensing still require validation in the target environment.

---

# THE CROW'S NEST STUDIO 4.6 — CLEAR PRODUCTION STAGES

Studio's film library now separates production states instead of dumping every job into the same queue:

- **Needs work:** Waiting, failed, or currently generating. The primary button starts or retries work, or opens the model setup if needed.
- **Ready for review:** Drafts move here automatically when researched and written. One **Continue in Main Studio** action opens the requested Full, YouTube Short or TikTok script. When one job finishes while its library is open, Studio opens it directly in the editor and closes the extra window.
- **Completed / Library:** Finished productions and drafts already handed off to the editor live here; they're no longer mixed with waiting work.

**One button and one menu:** The library now shows **Continue**, an output-version selector and **Manage ▾**. That menu contains **Delete selected queue entry**, **Clear waiting / failed queue**, **Clear completed productions from list**, archive/restore, **Move all review-ready drafts to library**, source credits, research leads and activity. Deletes are tracking-only: original research, script files, audio, image files and exported MP4s remain on disk. Running work cannot be deleted in the middle of processing. Removed requests from a synced ChatGPT inbox are remembered and won't reappear automatically.

There are still explicit fact-check and media-rights approvals before rendering, and Buffer publishing still requires manual approval. Queue cleanup does not bypass these controls or delete source evidence.

---

# STUDIO 4.5 — THE DOCUMENTARY PRODUCTION WORKSPACE

The Crow's Nest Studio is organized like a small documentary production house, rather than a collection of setup utilities.

**One straightforward path:**
1. **NEW PRODUCTION** — describe the subject, select film length, visual treatment, and Full / YouTube Short / TikTok. Click **RESEARCH & BUILD STORY**. Studio finds source leads and creates separate unverified scripts. No user-supplied research file is required.
2. **STORY & SOURCES** — review the discovered references and edit the narration. Switch formats without losing edits. Use **Fact checker** to review the evidence behind each version's claims.
3. **NARRATION** — choose a voice, hear a preview, and create the audio. The pronunciation dictionary remains separate from visible subtitles and historical wording.
4. **FACTS & RENDER** — approve factual claims and licensed footage. One active story is rendered at a time in the selected aspect ratio; switching aspect does not rewrite the script.
5. **SCREENING ROOM** — preview the completed MP4 and explicitly approve a Buffer composer handoff. **No video is uploaded automatically.**

**Where everything else went:** **Open films and queue** in the sidebar is the project library. Advanced controls for Ollama, custom research notes, ComfyUI/Wan workflows, and private ChatGPT file handoff are behind the library's Integrations/Advanced Create pages. If a language model is missing, the new production flow opens the model picker automatically rather than failing with an unexplained HTTP 404.

**Display and navigation:** a calm low-glare documentary palette, fixed production-sidebar, clear stage markers, vertical page scrolling, dedicated script scrolling, mouse-wheel support, 90–140% font scaling, and a soft-light alternative. Use the main **+ NEW FILM** button to start clean; it offers to save any unsaved current script.

**Reliability:** source checks and media-rights gates still apply independently to each derived documentary. Model downloads require user approval and available disk space. Generative reenactments need a separately configured compatible GPU and ComfyUI workflow; the app can use archival stills if not configured. Windows playback, third-party uploads and GPU inference still require confirmation on the user's PC; GitHub's Linux GUI and regression tests do not prove those physical-device integrations.

---

# CROW'S NEST STUDIO 4.4 — RESEARCH FIRST, THEN FACT CHECK

**Quick AI no longer asks you to provide a TXT research file.**

1. In **1 · STORY**, select **Quick AI: research & draft**. Enter your subject and the full-length duration.
2. Studio searches Wikipedia's public REST search/overview API and the Library of Congress's public catalog API for relevant records. It saves the source URLs, retrieved descriptions and warnings locally. **Your topic is transmitted to these public search services**; other scripts and voice files remain local.
3. Ollama drafts a full documentary and two punchy variants (YouTube Short and TikTok). It uses retrieved context where available and labels the result **unverified**. If research services are inaccessible, the unverified draft route is available; Studio never fabricates a source link to appear researched.
4. Review the written script and select **View discovered research sources**, or choose **Review factual claims and sources** under **3 · VERIFY & RENDER**. The Fact Checker has a **Discovered sources** button listing real URLs and source excerpts.
5. Open the original research pages, compare each claim with the evidence and record an accurate supporting excerpt. **Discovered source leads are not fact-check clearance.** Complete the claim-by-claim check and explicitly confirm footage rights.
6. Only after that review and your explicit Render command does Studio invoke the optional local ComfyUI/Wan engine for illustrative reenactment footage. AI-generated scenes are watermarked **AI REENACTMENT**, and you must inspect the finished video before entering Buffer's upload composer.

You never need to create a research file yourself. A local Ollama model is still required for the automatically drafted narration. Studio cannot guarantee sufficient trustworthy evidence for obscure topics; if the evidence is insufficient, revise or defer the story rather than inventing details. Automated source discovery is **not** autonomous historical fact verification.

---
# CROW'S NEST STUDIO 4.3 — ONE TOPIC / THREE VIDEOS

## The simple workflow

Open **1 · STORY → Create from one topic**. Give Studio the subject and select:
- **Full YouTube documentary:** your selected length (1–30 minutes), 16:9.
- **YouTube Short:** punchy condensed hook → stakes → payoff, 9:16; aimed at roughly 50–60 seconds.
- **TikTok:** a second independently editable vertical story, 9:16; aimed at roughly 65–85 seconds.

All three are grounded in the SAME long-form source script. With local Ollama available, Studio asks it for audience-specific rewrites while explicitly prohibiting invented facts, quotations, dates and events. If Ollama is unavailable for adaptation, Studio extracts original source sentences instead. Both routes remain UNVERIFIED. **Each output gets its own source/fact review**, narration audio and preview; nothing publishes automatically.

### Visual styles

| UI choice | How it actually works |
|---|---|
| Archival photographs | Searches candidate Creative Commons / public-domain photos via Wikimedia; rights and relevance still need human verification |
| Cinematic photo motion | Subtle Ken Burns movement on authentic stills |
| Hybrid documentary | Archival imagery plus restrained branded title cards |
| Animated realism (local AI) | ComfyUI + user-supplied Wan 2.2 (or compatible) workflow generates a few clearly labeled illustrative short clips; falls back to archival without the model |

**Do not misrepresent AI reenactments as real archival footage.** Generated shots receive an on-screen AI REENACTMENT label and separate media credits. The app does not claim that synthetic scenes depict actual persons or exact events.

### Free, local, no subscription, no per-video cap

**Recommended:** [ComfyUI](https://www.comfy.org/download) with [Wan 2.2 TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B) (Apache 2.0). ComfyUI has official AMD ROCm support on Windows for supported AMD GPUs. Your PC still needs adequate compatible GPU/VRAM, storage, and time. The app cannot confirm your hardware until you run it there. No remote paid fallback is enabled.

One-time setup:
1. Install official ComfyUI Desktop for your GPU, select AMD ROCm on compatible Radeon or NVIDIA CUDA as appropriate, and download a compatible local Wan model.
2. In ComfyUI, load a text-to-video or image-to-video workflow; set the **positive prompt** node's text to include `__CROWS_PROMPT__` exactly once. Export **API Format JSON** (not the ordinary UI workflow).
3. Start ComfyUI's local server on `http://127.0.0.1:8188`. Do not expose its service to the internet.
4. In **Create from one topic → 3. INTEGRATIONS**, choose your API-format workflow and click **Check local AI engine**.
5. Select **Animated realism (local AI)** before starting a topic. Studio queues a few illustrative clips only when rendering AFTER source review. Missing dependencies or failed scenes use archival/title-card fallbacks with clear messages.

Generation is **not unlimited in duration per clip**; model checkpoints have GPU memory and duration limits. The app uses only a few short AI scenes per documentary, rather than promising a 10-minute fully AI-generated film.

### Preview, pronunciation and upload

Narration year/date correction, `corpsman` and `Marine Corps` corrections, and the editable private foreign-name dictionary remain enabled. Select each output from the production queue, review the written script, listen in **2 · VOICE**, check evidence in **3 · VERIFY & RENDER**, and inspect the final MP4 in **4 · WATCH & PUBLISH**.

The **Continue to Buffer upload** button opens Buffer's web composer and your local export folder; it **does not directly upload files or post**. Select a channel, attach the MP4, and confirm publishing in Buffer yourself. This safeguards against accidental public posts.

### Readability

Open **5 · SETTINGS → Display comfort** to choose **Low-glare dark** or **Soft light**, plus 90–140% text scaling. Restart Studio to apply the preference throughout the main editor, voice tools, production queue and fact checker.

### Update integrity

Updates still come from SHA-256-verified GitHub Releases, and keep personal voices, source files, exports, projects and credentials private. The GitHub Actions workflow runs offline unit tests, headless dark/light UI checks and FFmpeg sample rendering. A green CI run establishes that those checks passed; it does **not** establish that voice output or local GPU video generation works on your particular Windows machine.

---

# THE CROW'S NEST STUDIO 4.2 — CHATGPT INBOX AND GUIDED DOCUMENTARY PRODUCTION

## Easy workflow

1. Open **Write → Open prompt production queue**. Type the subject, choose **Length**, **Video shape**, and **Visual style**. Click **Create episode**. Auto-draft is enabled by default, and source review is still required.
2. Or use **3. ChatGPT inbox** in the production window. Install **Google Drive for desktop** and sync the private `07 - Studio Job Inbox` folder in The Crow's Nest Drive. Click **Choose folder** once and select its local Windows path. Studio scans that folder every 30–45 seconds **while Studio is open**, imports new `crowsnest.job.v1` JSON jobs, and can draft them automatically. When the production window is closed, the main editor shows **Review ChatGPT draft** once a script is ready, without replacing your current edits. Your personal Google sign-in is handled by Drive desktop; Studio itself never asks for or stores a Google password/token.
3. ChatGPT can submit either a topic-only request or a prepared narration/scene script in the job JSON. Prepared scripts bypass Ollama but still require all normal fact checks. Topic-only requests require a running local Ollama model. The production window lists completed drafts; select **Open selected draft in editor** to review or edit.
4. In **Narrate**, choose a voice. Preview it, install the model once if needed, generate narration, and use Play/Stop. **Edit pronunciation guide** sets private word-by-word corrections for difficult names. Years such as 1967 and month-name dates are spoken naturally; subtitles keep the original written dates.
5. In **Review & render**, verify the historical claims and media licenses, choose 9:16 or 16:9, then render. In **Preview & publish**, play the complete MP4 and explicitly approve the finished video.
6. **Continue to Buffer upload** opens your export folder and Buffer's browser composer. You manually attach the final MP4, select TikTok/YouTube and click publish there. **The desktop app does not upload or post on your behalf.** Buffer's API requires a stable publicly hosted media URL and is not used by this local-only workflow.

**Visual style choices:** `archival` uses reusable historical photos where found; `motion` gives those real still photos restrained cinematic movement; `hybrid` mixes motion-treated photos with branded title cards. **These settings do not generate photorealistic AI battle footage.** Actual photographs are discovered from Wikimedia Commons only when available, and they remain unverified until the user checks relevance, provenance, and license. For generative reenactments, footage must currently be produced in another tool and imported as video files.

**Private ChatGPT inbox:** The repository is public code, but job requests and voice models should stay in private Google Drive/local folders. Do not commit personal clips or scripts to GitHub. The private Drive inbox used by ChatGPT is: https://drive.google.com/drive/folders/1X_-ZSLRTvOt4KFFSEoS_ml-9t4O8p05H

**Limitations:** The video preview launches FFplay or the system's MP4 player, not an embedded timeline editor. TTS pronunciations remain voice/model-dependent; the guide is a correction tool rather than a universal multilingual phoneme engine. Media searches can miss images. Automated tests verify Python behavior and headless GUI opening, not real Windows audio outputs or third-party publishing success.

---

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
