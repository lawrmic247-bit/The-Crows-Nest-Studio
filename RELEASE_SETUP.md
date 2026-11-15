# The Crow's Nest Studio — verified auto-update releases

The included Windows installer is the last manual ZIP installation **only after** you set up the following GitHub release pipeline. The application itself cannot create or publish GitHub releases until a repository is configured and reachable.

1. Extract the complete Studio 4.0 ZIP, then double-click `Connect_GitHub_Once.bat` on Windows. It can install GitHub CLI, authenticate through your browser, and ask you to approve the GitHub account and PUBLIC/PRIVATE visibility. Public repositories make the owner name visible. It initializes the repository, pushes the source and `v4.0.0` tag, and starts the release workflow. **For desktop automatic update downloads, choose PUBLIC; private releases require separate authenticated access that the current updater does not implement.**
2. Commit the source files and the `.github/workflows/release.yml` file from this package to that repository. Keep voice recordings, custom references, downloaded model files, API tokens and exported videos out of Git.
3. Confirm `VERSION` matches the release tag, e.g. `4.0.0` and `v4.0.0`. Push the tag. The workflow runs tests, assembles a code-only update ZIP and a Windows starter ZIP, and creates a GitHub Release.
4. Confirm that the release includes exactly `Crows_Nest_Studio_Update_v4.0.0.zip` and that GitHub reports a `sha256` digest for the asset.
5. In Studio, open **System / Updates** and enter the repo's exact `owner/repository` slug. The updater will check releases on launch, download over HTTPS from the configured repo, verify the GitHub SHA-256 digest, reject unrecognized paths, and stage the changes. It then offers to restart the app.
6. Later code changes can be delivered via a new tag and verified release automatically. The updater does **not** silently install dependencies or download huge models; those require separate user actions.

This pipeline is supplied, but it is not activated until the repository and release source are confirmed. A push without a release tag does not distribute updates.

Security: The SHA-256 digest verifies the downloaded bytes against GitHub's release metadata; it is not an independent developer signature. Only trust repositories you control. Avoid checking in user records or voice samples. Use branch protections and restrict release access.
