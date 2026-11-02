# Lumira Operational Completion Checklist

This checklist closes the gap between a verified codebase and a fully operational personal AI. Record the date, environment, and pass/fail evidence for each item. Do not record secrets, API keys, tokens, or private recordings in this document.

## 1. Baseline startup

- [ ] Start Lumira with the documented launcher.
- [ ] Confirm the backend responds through its local health/status path.
- [ ] Confirm the desktop opens and can reach the backend.
- [ ] Restart both services and confirm saved sessions, memory, and artifacts remain available.

## 2. Provider validation

Only test providers you intend to use. A provider is complete only after a real successful operation and a safe unavailable/failure check.

### Transcription and voice
- [ ] Configure a supported transcription provider or local model.
- [ ] Record or upload a permitted test recording.
- [ ] Produce a transcript and verify it is stored only through the intended artifact/memory path.
- [ ] Disable or misconfigure the provider and confirm Lumira reports unavailable rather than fabricating a transcript.

### Image generation and understanding
- [ ] Configure the selected provider/model.
- [ ] Complete one real generation request.
- [ ] Complete one real image-analysis request.
- [ ] Verify provider failure reports an explicit error without creating a fake result.

### Research
- [ ] Configure the selected research provider.
- [ ] Run one bounded research request.
- [ ] Verify returned findings include the expected source references.
- [ ] Remove the provider configuration and confirm the feature becomes unavailable.

### Wake word and devices
- [ ] Configure the wake-word provider and keyword model if this feature is in use.
- [ ] Test microphone start, detection, stop, and unavailable-device behavior.
- [ ] Test each physical device integration separately.

## 3. Tamil and mixed-language acceptance

Use real commands representative of normal use:

- [ ] Tamil Unicode command.
- [ ] Romanized Tamil command.
- [ ] Tamil-English mixed command.
- [ ] Project/idea command containing mixed language.
- [ ] Verify language detection and capability routing.
- [ ] Record any misunderstood commands as regression cases instead of silently changing behavior.

Language classification alone is not proof of complete semantic understanding.

## 4. End-to-end personal AI workflows

- [ ] Capture an idea.
- [ ] Validate and plan it.
- [ ] Save relevant memory/artifacts.
- [ ] Restart Lumira.
- [ ] Retrieve the saved context.
- [ ] Continue the workflow.
- [ ] Interrupt a workflow and verify guarded recovery.
- [ ] Confirm an unsafe or rejected pipeline does not continue downstream.

## 5. Reliability run

Run this on the real target environment:

- [ ] Repeated startup/shutdown cycles.
- [ ] Restart during normal persisted-state use.
- [ ] Interrupted workflow recovery.
- [ ] Repeated provider failure and recovery.
- [ ] Verify no duplicate side-effect execution.
- [ ] Check memory/artifact/workflow persistence after extended use.
- [ ] Record any crashes, corruption, or uncontrolled retry loops.

## 6. Secure project execution

The default fail-closed behavior is correct.

Do not enable execution with a flag or UI change. If terminal execution is part of Lumira's final scope:

- [ ] Install a concrete OS-level isolation provider.
- [ ] Explicitly supply that provider to the terminal runtime.
- [ ] Verify filesystem boundaries.
- [ ] Verify network isolation.
- [ ] Verify CPU, memory, process, and timeout limits.
- [ ] Verify cleanup after success, failure, and timeout.
- [ ] Execute only a trusted test project inside the verified sandbox.

If these checks cannot be completed, keep project execution disabled and do not claim this capability is operational.

## 7. Direct web fetch

Before treating web fetch as operational:

- [ ] Verify it in an isolated runtime.
- [ ] Confirm private/local targets are rejected.
- [ ] Confirm redirects are revalidated.
- [ ] Confirm DNS rebinding protection behaves correctly.
- [ ] Confirm proxy environment settings are not inherited.
- [ ] Keep the feature local and do not expose arbitrary URL fetching to untrusted callers without a separate production security review.

## Completion rule

Lumira is operationally complete only when every capability in its promised scope is either:

1. Proven working in its real target environment, or
2. Intentionally excluded from the promised scope and honestly reported as unavailable.

Automated CI is necessary evidence, but it cannot replace real provider, microphone, hardware, sandbox, or personal-use validation.
