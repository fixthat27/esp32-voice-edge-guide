# Troubleshooting by layer

Work upward from capture. Change one variable per test and save the failing example.

| Symptom | First checks | Evidence before moving on |
|---|---|---|
| Port cannot open | Close serial monitor; identify the correct USB interface/COM port | One program owns the port and receives READY |
| No valid PCM clip | Correct capture build, baud rate, reset/startup output, missing lines | 16000 samples with every offset present |
| All zeros | Mic power, common ground, L/R=GND, DIN vs DOUT, GPIO map | Intelligible speech WAV |
| Loud digital noise | Stereo extraction, 32-bit slots, Philips delay, signed shift | Raw left sample words and scope/logic-analyzer timing |
| Quiet but intelligible | Distance, breakout orientation, original PCM amplitude | RMS/peak/clipping comparison before any gain |
| Repeated speaker tone | Playback loop, re-enqueue, TX drain and disable | A finite tone followed by silence |
| Wrong WAV duration | Actual sample clock and capture count | WS frequency plus sample count |
| Model predicts one label | Label balance, normalization, tensor order, clipping | Confusion matrix and sample features |
| Excellent train, poor validation | Session/speaker split, cut-off phrases, duplicates | Reviewed recordings and leakage audit |
| Float good, INT8 poor | Representative set, tensor scales, normalization, saturation | Same held-out vectors on both runtimes |
| PC INT8 good, board bad | Golden vector, model byte hash, resolver/operator versions | Raw input/output byte comparison |
| Golden vector good, live bad | MFCC parity, microphone format, domain shift, window alignment | Same PCM through both preprocessing paths |
| AllocateTensors fails | Missing operators, arena capacity, incompatible model/runtime | Runtime error and actual dependency lock |
| Linker RAM overflow | Internal RAM allocations, arena size, table placement, verified PSRAM | Link map and memory report |
| Resets during MFCC | Watchdog, task stack, CPU time, double FFT cost | Reset reason, stack watermark, feature latency |
| Wake repeatedly fires | Hard negatives, overlapping windows, playback, cooldown | Event-based false accepts/hour |
| API unreachable from ESP32 | Host LAN IP, bind interface, firewall, Wi-Fi subnet | Fixed request from another LAN client |
| HTTP 200 but no action | Shadow status, service result, broker, LM and state semantics | Correlated command/publication/state logs |
| MQTT client disconnects | Duplicate client ID, credentials, ACL and broker logs | Unique IDs and successful reconnect |
| Commands replay after reconnect | Retain flag, persistent session, stale queue and request IDs | Failure test without duplicate physical action |

If TensorFlow conversion aborts inside MLIR, keep the full log and environment freeze. Reproduce with the small supplied architecture, then test the documented SavedModel converter path in the same environment. Do not claim the `.tflite` file is valid unless the desktop interpreter allocates it and evaluates held-out examples. If changing TensorFlow/Keras, rerun both INT8 and TFLM checks.

If GCC is absent, ordinary host tests skip C parity. Install a native compiler or build `mfcc.c` as a shared library on another host. On Linux, an equivalent command is `gcc -O2 -Wall -Wextra -shared -fPIC firmware/shared/mfcc.c -o build/libmfcc.so -lm`; set `MFCC_LIB` to its absolute path. Cross-compiling for ESP32 is a separate check.
