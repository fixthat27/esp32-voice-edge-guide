# ESP32 voice edge: guided implementation bundle

Start with [the workflow](docs/WORKFLOW.md). It follows milestones 1 through 7 in your hardware-progress document, then its section 11 HTTP/MQTT handoff. Read [the theory](docs/THEORY.md) alongside each exercise. The original documents are preserved unchanged in `originals/`.

Your documented position is **hardware bring-up reported complete; dataset, model, MFCC parity and on-device recognition still pending**. Begin with a clean microphone recording, not MQTT or a wake word.

This is a new reference codebase based on your attachments, not a copy of the existing repositories. Neither `D:\Alpha CCI Home\esp32_voice_edge` nor `D:\AlphaKNX\smarthome-edge-poc` was available in this workspace. GPIO assignments follow the progress document. Actual source files and wiring take priority if they have changed.

## Contents

| Location | Purpose |
|---|---|
| `docs/WORKFLOW.md` | Detailed instructions, commands and acceptance gates |
| `docs/THEORY.md` | Audio, MFCC, CNN, quantization, streaming and messaging explanations |
| `docs/INTEGRATION.md` | Existing backend inspection, transport, MQTT and Orange Pi deployment |
| `docs/REFERENCES.md` | Official sources and compatibility findings |
| `docs/VALIDATION.md` | What was actually checked while making this bundle |
| `docs/EXPERIMENT_LOG.md` | Reusable evidence record |
| `docs/TROUBLESHOOTING.md` | Symptom-to-test diagnostic guide |
| `firmware/` | ESP-IDF one-second capture and optional TFLM bench inference |
| `firmware/shared/` | Portable C MFCC implementation used by firmware and host parity tests |
| `ml/src/` | NumPy features; manifest preparation, Keras training, INT8 export, evaluation |
| `tools/` | Serial WAV capture, WAV inspection and host-test commands |
| `integration/` | Tested Python decision policy and authenticated shadow API with durable deduplication |
| `test/` | Host tests for DSP parity, decision policy and backend behavior |
| `originals/` | Both user-supplied Markdown documents |

## Scope of the supplied code

Capture mode needs no trained model or TFLM dependency. Optional inference mode needs generated model files and the pinned TFLM component. It logs predictions and performs no actuation. The one-second capture loop deliberately pauses between clips; it is a bench instrument, not a continuous wake-word product.

The shared DSP and host integration logic are testable without the board. A real trained model is not supplied because your labeled recordings were not attached. Training, ESP-IDF compilation, live audio, memory limits, Wi-Fi, broker delivery and physical state must be validated on your equipment. See `docs/VALIDATION.md` for exact results.

The backend example runs independently in shadow mode. Its route is a proposed contract, not a claim about your existing FastAPI routes. Adapt the existing command service after inspecting it. No invented LogicMachine topics or group addresses are supplied.

## Quick start on Windows

Extract this folder to a short path such as `D:\voice-guide`. Run all host commands from that folder unless a step says otherwise.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r ml/requirements.txt
python -m pip install -r integration/requirements.txt
python -m unittest discover -s test -v
```

The C parity test requires GCC and `MFCC_LIB`; `tools/test_host.ps1` compiles and enables it. A skipped C test is not parity evidence. Use Python 3.11 for the proposed TensorFlow environment rather than assuming the installed Python 3.14 can use those wheels. Training and integration dependency sets have different purposes; freeze the versions that actually pass your tests with `python -m pip freeze`.

Open an ESP-IDF terminal separately for firmware commands. The project record says v6.1. Keep that environment until you have a concrete incompatibility; the official TFLM support table does not explicitly certify v6.1.

## Document precedence

The hardware-progress document controls the current voice workflow. The proposal provides system boundaries: local inference, backend policy, existing automation retained, shadow tests before physical control, and state feedback. Its broader occupancy/camera/HVAC research is future context, not extra work required to classify your first command. Section 11's structured-intent HTTP path is the selected first integration route; general ASR on Orange Pi remains optional.
