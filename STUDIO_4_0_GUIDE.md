# The Crow's Nest Studio 4.0 — Windows Setup & Operating Guide

## What is new

- **PROMPT → VIDEO QUEUE**: Write a topic, choose estimated minutes, Shorts/widescreen/both, an Ollama model, and the narrator. Generate immediately or queue multiple episodes.
- **Persistent production jobs**: Jobs live in `%LOCALAPPDATA%\TheCrowsNestStudio\production_queue`. They survive restarts and software updates.
- **Ollama script drafts**: Calls only the local endpoint (`127.0.0.1:11434`) to create outline and narrated sections. Nothing requires per-video cloud generation credits. Install Ollama and download a compatible model separately.
- **Archival stills**: Optionally discovers appropriately licensed Wikimedia Commons images, records their source page, author, and license, and saves optimized local files. Material is **not automatically cleared for publication**; review attribution and any share-alike requirements. This is not automatic cinematic motion generation.
- **Source-led fact checking**: Generates a per-claim ledger and official-source *search leads*. Search results are not automatically counted as proof. The normal narration-to-video path requires personal review of facts and media rights.
- **Voice library**: Keeps all Studio 3.0 recording, A/B cleanup, multiple voice profiles, Qwen Base cloning, and prompt-designed fictional voices. Voice recognition and clone performance depend on the model and GPU.
- **Verified updater**: The existing GitHub release checker can download and stage trusted, hash-verified code updates. It only works after you configure a repository *containing a release archive*. A source-code push by itself does not create a downloadable release.

## One-time installation

1. Close any running Crow's Nest Studio windows.
2. Download the Studio 4.0 ZIP and choose **Extract All**.
3. Open the folder containing `Install_Desktop_App.bat` and double-click it. This upgrades `%LOCALAPPDATA%\Programs\TheCrowsNestStudio` while keeping projects, voice data, footage, and exports.
4. Start **The Crows Nest Studio** from your desktop shortcut. Select **PROMPT → VIDEO QUEUE**.
5. Install [Ollama](https://ollama.com/download/windows) if you don't already have it. In PowerShell run `ollama pull qwen3:8b` once. If your machine is low on memory, select a smaller compatible Ollama model and change the model name in the queue window. Audio models are installed separately through Voice Studio.
6. Enter a production prompt, choose duration and format, and select **ADD PROMPT TO QUEUE**. By default, it immediately starts generating. The script generation requires Ollama running on your computer. All work remains local except optional Wikimedia image retrieval.
7. When job status becomes **awaiting_review**, select **OPEN DRAFT IN EDITOR**. Use **FACT CHECK** to review individual claims against trustworthy original sources, and **VIEW MEDIA CREDITS** to inspect license obligations.
8. Install your chosen narrator from the main editor, click **HEAR THIS VOICE**, then **GENERATE NARRATION**. Once the factual ledger is cleared and you confirm media rights, click **RENDER VIDEO**. Output appears in `exports`.

## Automatic releases — GitHub

A push to GitHub is not the same as a GitHub Release. The extracted package contains `Connect_GitHub_Once.bat` for a one-time repository setup, including browser authorization, safe Git staging, and initial release tag. It runs only with your explicit approval. Public repositories expose your GitHub account as owner; private repositories cannot serve unauthenticated auto-updates. Future code versions are published by pushing new version tags. In the desktop app open **System / Updates** and enter the owner/repository of this release source. After a release exists, new code updates can be downloaded and applied on restart without downloading separate ZIP files manually. The GitHub connector must have access to the correct repository for automated publishing from ChatGPT; the app itself can check public GitHub Releases when configured.

## Data/privacy and review

- Never publish AI-generated factual claims as verified without source review.
- Do not clone voices without the speaker's explicit authorization. Store voice recordings privately.
- Do not present the channel as an official DoD or military publication; avoid sensitive, unpublished, or operational information.
- The queue does **not** automatically upload or publish to Buffer/YouTube. Final MP4s require review and authorized account connections.
- No cloud-based HeyGen-equivalent generative video engine is bundled. For motion-generative scenes, use a compatible locally installed model and supply resulting clips to the scene assets, or continue using properly licensed archival footage.
- 'Unlimited' refers to rendering without app-imposed count/credit quotas. Local computing resources, model performance, download bandwidth, licenses, and service quotas still apply.

## Troubleshooting

- **Ollama not available**: install and run Ollama, then `ollama pull qwen3:8b`. Try `ollama list` to check models.
- **Jobs stuck**: open the queue and inspect the activity log. Failed jobs can be retried after repairing the underlying cause.
- **Narration poor**: use **VOICE STUDIO** to record your own voice, apply light cleanup, and compare original/processed. For custom clone narration install Qwen through the application. Hardware performance varies.
- **Source review blocks**: this is expected; approve only claims with real evidence, not plausible model output or source *search leads*.
- **Missing updater repository**: entering a nonexisting or inaccessible GitHub repository will not activate updates. Configure the repository when it exists and has releases.
