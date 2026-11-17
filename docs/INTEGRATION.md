# HTTP, MQTT and the existing smart home system

## 1. Inspect before changing the existing backend

The referenced repository is `D:\AlphaKNX\smarthome-edge-poc`. It was unavailable during bundle preparation. Run these read-only commands in that repository and save the findings in an integration note:

```powershell
rg --files app
rg -n 'APIRouter|@.*post|include_router|BaseModel' app
rg -n 'def |publish|qos|retain|topic|technical' app/services/command_service.py app/mqtt app/config.py
```

Record the actual route/schema, command-service signature, MQTT client method, QoS, retained behavior, technical-office light topic/payload, broker address and LogicMachine state feedback mapping. Do not paste credentials into the note. Review environment variable names instead. If files moved, use the search results to find their replacements.

The current voice workflow selects:

```text
INMP441 -> ESP32 classifier -> local rejection/state policy
        -> bounded command queue -> HTTP POST of structured intent
        -> existing FastAPI command service -> existing topic/payload mapping
        -> existing MQTT client -> Mosquitto -> LogicMachine -> KNX/DALI
        <- separate reported-state path where available
```

This preserves the proposal's automation boundary. Arbitrary model text must not select topics, object addresses or bus writes. Camera occupancy and general ASR are separate workloads. Orange Pi 3 LTS is the recorded later deployment target, not a claim that it can run arbitrary Whisper/vision workloads at your required latency.

## 2. Test the shadow contract first

The included standalone API uses Pydantic validation, an API-key header, an allowlist for one device, explicit on/off values and SQLite request deduplication. It is intentionally disconnected from MQTT. Run from the bundle root:

```powershell
python -m pip install -r integration/requirements.txt
$env:VOICE_API_KEY = 'replace-with-a-long-random-local-test-secret'
$env:VOICE_DB = 'commands.sqlite3'
python -m uvicorn integration.api:app --host 127.0.0.1 --port 8000 --workers 1
```

In another PowerShell terminal, set the same test key and send:

```powershell
$headers = @{ 'X-API-Key' = $env:VOICE_API_KEY }
$body = Get-Content -Raw integration/request.example.json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/commands' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
```

Expected response status is `shadow`, with `confirmed=false`. No light should change. Send the identical request again: the stored result should return. Change the content while keeping the request ID: expect HTTP 409. Try an unsupported device, low confidence, wrong boolean value or missing key: expect rejection and no adapter call.

Use a single worker for this reference. Its lock is process-local; SQLite provides persistent records but the implementation does not provide a multi-worker job system, cleanup policy or deployment-grade concurrency. Do not reuse the reference database when moving from shadow to live execution: old IDs retain their shadow results by design. Use fresh IDs and an explicit environment migration.

## 3. Reuse the existing service and MQTT client

After identifying the real service method, transplant or adapt the schema and validation into your backend. Add a route only if none already fits. The route should call the command service; the service owns allowlisting, policy and deduplication; the existing mapping owns MQTT topics/payloads; the existing client owns connection and publish behavior.

The `CommandService` adapter parameter illustrates that seam. Its adapter must either wait for broker acknowledgment or raise. Do not return `published` just because a message was queued in a client library. If your existing method only queues work, use `accepted` and track later outcomes. For Paho, inspect the returned message-info object and its completion/timeout behavior against the installed version. Do not replace your existing client simply to match this example.

Before a live test, confirm manual override, device restrictions and current room policy. The supplied service is a transport/policy example for on/off only. It does not implement manual-override sensing, occupancy, time-of-day rules, stale-event expiry or interlocks from the wider proposal. Add those checks to your existing policy layer before unattended use.

Test with the known technical-office light and a fixed request. Observe the existing MQTT subscription, LogicMachine object and physical light. A separate state topic/object must establish physical state. Record its actual mapping and whether it reports measured actuator state or only echoes a command. Display `Command sent` for acceptance/publication; display `Light is on` only after trusted state feedback.

## 4. Add ESP32 Wi-Fi and HTTP after the fixed request works

The supplied firmware is deliberately offline. Add network transport to the existing project as a separate component after bench inference passes. Use the ESP-IDF station example matching your installed IDF version, including NVS initialization, event-loop/netif creation, Wi-Fi initialization, configuration and event-driven reconnect. Keep SSID, password, API URL and key in project configuration or provisioning storage; do not log them.

`integration/esp32_http_transport.c` and its header provide an optional transport implementation. They are not compiled into the offline bench project and have not been built against ESP-IDF here. Copy them into your existing network component and declare its `esp_http_client`, `json`, `esp_timer` and `esp_hw_support` dependencies. Call `voice_http_start()` once after station setup, with persistent configuration strings and a unique node ID containing only letters, digits, underscores or hyphens. Pass a trusted server CA for HTTPS. Call `voice_http_enqueue()` only after the wake/command decision policy accepts an action. This function applies an additional illustrative 0.85 score gate; keep it synchronized with the threshold selected from validation data.

The implementation uses a four-entry queue, a two-second queue-age check, a two-second HTTP timeout, a bounded response buffer, request-ID correlation and no retries. The age check applies before the request starts; it is not a backend execution deadline. Add a schema-supported expiry and backend enforcement before relying on end-to-end freshness. Wi-Fi reconnect remains the responsibility of your existing station component. Startup, queue-full and network errors must be reflected in your UI/logging. It never claims physical state from an API result.

The network task design should be concrete:

- The audio task emits a small immutable accepted-command record with label, confidence, monotonic timestamp and model version. Give the queue a small fixed capacity, such as four records; log full-queue drops.
- Map only `light_on` and `light_off` to the known light for the first integration. Reject the two music labels until the backend has verified mappings for them.
- Build a request ID from device identity, a random boot nonce and a monotonic counter. A counter alone repeats after reboot. Retain the same ID and body for any retry.
- The network worker checks connection state and record age before sending. An initial two-second expiry is a design choice to validate, not a measured requirement. Discard stale queued actions after reconnect.
- Configure `esp_http_client` with finite timeouts, POST, `Content-Type: application/json` and the authentication header. Use cJSON or bounded serialization rather than unbounded string formatting.
- Inspect the transport result, HTTP status and bounded JSON response. A 2xx response with `shadow` or `indeterminate` is not success at the actuator. Limit response buffers and reject malformed or oversized bodies.
- Do not retry ambiguous timeouts automatically until the real backend provides durable deduplication/reconciliation. If enabled, bound retries and keep the same ID. Never generate a new ID merely to retry the same physical action.
- Keep the classifier operating during network loss. Clear stale commands and report remote execution unavailable. Do not block I2S capture on `esp_http_client_perform()`.

The exact ESP-IDF client lifecycle is initialize, set headers/method/body, perform, inspect, cleanup or reuse. See the versioned [HTTP client documentation](https://docs.espressif.com/projects/esp-idf/en/v6.1/esp32s3/api-reference/protocols/esp_http_client.html) and [Wi-Fi guide](https://docs.espressif.com/projects/esp-idf/en/v6.1/esp32s3/api-guides/wifi.html). Match your project's reconnect ownership rather than creating a second station service.

During Windows LAN testing, bind the backend to `0.0.0.0` and call the Windows host's actual LAN IP from ESP32. `localhost` on ESP32 is not Windows. Permit only the required inbound API traffic in Windows Firewall. Keep the broker separately configured; `localhost` inside Docker is the container itself. Temporary plain HTTP is suitable only for an isolated prototype network; use verified TLS and authenticated endpoints for deployment.

## 5. Failure tests and expected behavior

| Test | Expected observation |
|---|---|
| Valid fixed on/off request | One mapped command, correlated logs, separate state confirmation |
| Low confidence/unknown audio | No queued request or MQTT publication |
| Unsupported device/action | API rejection, zero publish calls |
| Wi-Fi or API down | Audio continues; finite timeout and visible unavailable status |
| Broker down | Failed/indeterminate result, no claim of physical success |
| LogicMachine disconnected | Publication may succeed; physical confirmation remains absent |
| HTTP reply lost after adapter call | Same request ID does not replay the adapter automatically |
| Backend restart during delivery | Persistent indeterminate record, then reconcile state |
| Duplicate MQTT client ID | Detect session takeover; assign unique IDs to each client |
| Retained control message | Verify no stale command executes on reconnect; normally avoid retaining commands |
| Manual override | Existing controller/policy wins; AI does not immediately undo it |
| Queue full or old command | Drop and log; no burst of stale actions on reconnect |

QoS is not an exactly-once physical-action guarantee. Keep command topics and state topics separate. Broker credentials and ACLs should constrain the backend and LogicMachine to their required topics. Do not expose the control broker/API directly to the public internet.

## 6. Move the proven API contract to Orange Pi

First inspect the installed OS and architecture, available RAM/storage and container support. Do not assume an x86 image will run on the board. Deploy the same backend source, pinned Python dependencies, Mosquitto configuration and persistent state directory. Keep deployment secrets outside the source archive. Configure service startup/restart using the operating system's supported service manager or the project's existing Compose setup.

Reserve stable LAN addresses or hostnames. Update the ESP32 API URL and LogicMachine broker endpoint; API and broker need not share a host. Preserve device/action meanings, request schema and topic mapping. Back up the deduplication store before migration and define how in-flight/indeterminate commands are reconciled.

Repeat the full fixed-request, live-voice and failure matrix. Restart the API, broker, LogicMachine connection and entire gateway independently. Disconnect WAN while keeping LAN up to demonstrate local operation. Stop the gateway and confirm that manual controls and existing automation still work. Log latency and memory on the Orange Pi instead of borrowing figures from Windows or unrelated benchmark tables.
