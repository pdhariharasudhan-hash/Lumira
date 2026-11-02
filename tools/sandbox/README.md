# Lumira validation sandbox

This Windows Sandbox profile is for manual verification of generated-project validation commands.

Security properties:
- Networking disabled.
- Host source mounted read-only.
- Clipboard, printer, microphone, camera and vGPU disabled.
- Source copied into a guest-local writable workspace before commands are run.

Run `tools/sandbox/lumira_validation.wsb` to open the isolated environment.

The Lumira backend deliberately remains fail-closed for project terminal execution. A Windows Sandbox profile alone does not prove that host-side API execution is isolated. Do not change the backend execution gate until an execution bridge can launch each run inside a verified guest boundary and collect results without granting host command execution.
