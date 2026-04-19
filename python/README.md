# V3SP3R Python Terminal (Phase A)

This directory contains the initial Python terminal migration scaffold that mirrors the original Android layering:

- `vesper_terminal/ai` - AI orchestration/client shim
- `vesper_terminal/domain` - command models, risk, permission, executor
- `vesper_terminal/transport` - Momentum-first transport adapter (mock for now)
- `vesper_terminal/data` - plaintext config + SQLite persistence
- `vesper_terminal/ui_cli` - interactive terminal UI
- `vesper_terminal/mocks` - voice/TTS/glasses placeholders

## Run

```bash
cd /home/runner/work/V3SP3R_Docker/V3SP3R_Docker/python
python3 main.py
```

## Confirmation flow

When a command needs approval, type:

- `YES` to approve
- `no` or `reject` to deny

## Example tool command

```text
tool {"action":"list_directory","args":{"path":"/ext"}}
```
