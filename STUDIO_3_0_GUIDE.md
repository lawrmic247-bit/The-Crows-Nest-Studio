# The Crow's Nest Studio 3.0 — Prompt Drafts & Voice Studio

## What's new
- **VOICE STUDIO:** Record microphone audio or import a reference; save any number of authorized voice profiles with separate names, reference transcripts, and acting notes.
- **Non-destructive cleanup:** Choose Off / Light / Balanced / Strong. Cleaned WAV is a separate file; original voice recording is never overwritten. A/B preview buttons make it easy to reject overprocessed audio. Cleanup does not deliberately shift pitch, change formants, or change your accent.
- **Natural delivery:** Use your own cleaned voice recording directly for a scene by exporting WAV as `01.wav`, `02.wav` etc into the footage folder. This preserves all of your personal timing, emotion, and acting choices.
- **Optional AI voice cloning:** Select your voice profile as the narrator and use Qwen3-TTS Base to generate new narration from a short reference recording and its *exact spoken transcript*. Requires `Install selected voice`, model weights downloading on first use, and sufficient computer resources. GPU recommended; not benchmarked on your PC.
- **Other voices:** Import additional voice profiles only if you own the voice or have the speaker's express permission. Fictional voice design from a text prompt uses the **separate** Qwen3-TTS VoiceDesign model, optional and several GB, and creates an original AI-generated reference voice.
- **Prompt draft:** Click `DRAFT SCRIPT FROM PROMPT`. It calls local Ollama (`qwen3:8b` by default). You may provide a TXT file with research notes. Without real sources, it generates an *unverified draft only*, and fact-check clearance is still required before publication-quality rendering.
- **Verified update checker:** Included from 2.0, but it still needs a Crow's Nest GitHub Releases repository to automatically download verified future releases. Until configured, upgrade manually with the one-time installer.

## One-time upgrade
1. Close Studio 2.1.
2. Extract this complete ZIP into a **new folder**. Run `Install_Desktop_App.bat`.
3. Open the desktop shortcut. Your current project folders, local voice models, and exports are kept in the installation directory. New Voice Studio profiles are stored **outside the program folder** at `%LOCALAPPDATA%\TheCrowsNestStudioData\voice_profiles` so future upgrades do not overwrite them.
4. Use **VOICE STUDIO — RECORD / CLEAN / CLONE**. Import a clean 10–30 second reference recording or use Record microphone (requires optional microphone support).
5. Add the *exact* reference transcript if you want Qwen's best reference-audio conditioning. Save the acting guide, but understand: **Qwen Base cloning uses the reference audio and transcript; the guide is saved metadata, not a separate prompt argument supported by that model**. To capture acting style, read the reference in that style or record the actual performance.
6. To generate new words in your own voice, click **Use as AI narrator**, then **Install selected voice** and **HEAR THIS VOICE**. If you want just cleanup, export the cleaned recording to a WAV and do not install Qwen.
7. For local prompt-to-script, install Ollama separately, then run `ollama pull qwen3:8b`; drafts are unverified until sources are checked in the FACT CHECK dialog.

## Audio privacy and permissions
- Voice files remain in your local PC profile directory unless you manually share or upload them. Qwen local inference downloads model weights from Hugging Face but does not send your voice recordings to a hosted TTS API in this integration.
- Other speakers' voices require express permission. Do not use this tool to impersonate anyone deceptively. Label realistic synthetic performances appropriately.
- Original files are preserved. Avoid aggressive noise cleanup: it can leave artifacts. Test Light first, and always A/B preview before using a profile.

## Technical limits
- These are locally installed features with no *per-render credits*, not a promise of unlimited compute or identical HeyGen quality.
- Full original-video generation from a text-only prompt is **not** implemented in this package. Prompt-to-script and narrated, watermarked video assembly are implemented; actual scenes use your footage or branded title cards.
- Voice cloning needs separately installed Qwen3 dependencies and model weights. Hardware compatibility and final cloned voice realism have **not** been verified on your Windows machine.
- Automatic online publishing and a hosted auto-update release repository are **not configured** yet.
