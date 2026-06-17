# Local Voice I/O

CLIT Controller IDE should support optional local speech input and local spoken
summaries without sending audio to a hosted service. The near-term path is:

- STT: MLX Parakeet for local speech-to-text on Apple/MLX-capable machines.
- TTS: `mlx-swift-dots-tts` for local text-to-speech on Apple/MLX-capable
  machines.

This feature is a local convenience layer over the existing controller, task,
queue, approval, and event systems. It should never become a hidden automation
path.

## Product Decision

Voice is an optional local interface for:

- dictating prompts into the Agent Dock
- starting task briefs
- adding user responses to approval or clarification prompts
- reading concise run summaries aloud
- reading scheduler/overflow notifications aloud
- hands-free status checks while long CLI work runs

Voice does not replace the written transcript. Every transcript, generated task,
approval, command, and spoken summary must remain visible in the UI.

## Target UX

- Push-to-talk is the default input mode.
- Always-on listening is off by default and out of scope for the first pass.
- The mic state is obvious: idle, listening, transcribing, failed, disabled.
- Transcribed text lands in the prompt box for review before sending.
- User can edit transcribed text before it becomes a task or command.
- TTS reads short summaries, not raw logs by default.
- TTS controls are compact: play, stop, voice/model selector, speed if supported.
- Voice features degrade cleanly when MLX Parakeet or `mlx-swift-dots-tts` is not
  installed.

## Architecture

Add local voice adapters rather than embedding voice logic directly into React
components or task services.

Suggested backend areas:

- `voice_service.py` for STT/TTS orchestration.
- `voice_adapters/` for MLX Parakeet and `mlx-swift-dots-tts` command rendering,
  detection, and failure classification.
- Temporary audio workspace under `.agentflow/voice/`.
- Redacted voice events in the durable event stream.

Suggested frontend areas:

- Right-hand dock voice controls.
- Prompt-box dictation button.
- Task summary read-aloud control.
- Status/footer voice availability indicator.
- Settings controls for provider paths, model names, and local-only policy.

## Backend Contract

Potential additive endpoints:

- `GET /api/voice`
  - reports STT/TTS availability, selected models, and local-only policy.
- `POST /api/voice/stt`
  - accepts a short local audio upload or references a captured audio file and
    returns a transcript.
- `POST /api/voice/tts`
  - accepts short text and returns an audio file or stream reference.
- `POST /api/voice/stop`
  - stops active local playback or synthesis.

Event types:

- `voice.stt_started`
- `voice.stt_finished`
- `voice.stt_failed`
- `voice.tts_started`
- `voice.tts_finished`
- `voice.tts_failed`
- `voice.playback_started`
- `voice.playback_stopped`

Important fields:

- provider: `mlx-parakeet` or `mlx-swift-dots-tts`
- task ID when reading a task summary
- run ID when reading a run summary
- transcript text for STT result events
- audio file reference for TTS result events
- duration
- failure kind
- local-only flag

## Safety And Privacy

- No cloud STT/TTS provider in the first pass.
- No background microphone capture.
- No auto-send after transcription.
- No voice command executes without the same policy and approval rules as typed
  input.
- Temporary audio files should be deleted by default after transcription/playback,
  unless the user enables retention for debugging.
- Logs should include metadata and errors, not raw audio.
- Transcripts are normal user-visible text and become part of task history only
  after the user sends them.

## UI Rules

- Voice controls should be icon-first and compact.
- Use familiar symbols: mic, stop, speaker, volume.
- Place dictation controls near prompt inputs, not in unrelated page headers.
- Place read-aloud controls on summaries, final reports, and selected task cards.
- Never add a large voice dashboard to the main canvas in the first pass.
- Show provider availability with small status badges, not banners.
- Do not hide typed input when voice is enabled.

## Non-Goals

- No cloud speech providers.
- No always-on wake word.
- No autonomous voice command execution.
- No raw log readout by default.
- No storing raw microphone audio by default.
- No replacing typed prompts, written summaries, or visible approvals.

## Acceptance Criteria

- If MLX Parakeet is available, the user can dictate into a prompt box, review the
  transcript, edit it, and send it normally.
- If `mlx-swift-dots-tts` is available, the user can play and stop a concise task
  or run summary locally.
- Missing STT/TTS providers show clear local setup/availability state.
- Voice actions produce durable events without leaking raw audio.
- Voice-generated text follows the same task, approval, queue, and policy rules
  as typed text.
- No audio or transcript is sent to a hosted service.
