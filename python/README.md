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
cd python
python3 main.py
```

## Config (`~/.vesper_terminal/config.env`)

Supported keys:

- `OPENROUTER_API_KEY=sk-or-...`
- `OPENROUTER_MODELS=anthropic/claude-sonnet-4,openai/gpt-4o-mini`
- `OPENROUTER_RETRIES=2`
- `TRANSPORT_MODE=mock` or `TRANSPORT_MODE=usb`
- `USB_DEVICE_PATH=/dev/ttyACM0`
- `USB_BAUD_RATE=230400`
- `ALLOW_MOCK_FALLBACK=true`

## Confirmation flow

When a command needs approval, type:

- `YES` to approve
- `no` or `reject` to deny

## Example tool command

```text
tool {"action":"list_directory","args":{"path":"/ext"}}
```

## Local command mode (no API key)

When `OPENROUTER_API_KEY` is not set, the CLI supports direct local commands:

```text
ls /ext
cat /ext/readme.txt
mkdir /ext/new_dir
mv /ext/a.txt /ext/b.txt
cp /ext/a.txt /ext/c.txt
rm /ext/c.txt
cli storage info
```
