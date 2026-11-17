#pragma once
#include <stdbool.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Call once after your existing Wi-Fi station setup. All strings must remain valid
   for the lifetime of the worker. URL includes /api/v1/commands. cert_pem may be
   NULL only for an isolated-LAN HTTP prototype. Never disable HTTPS verification. */
bool voice_http_start(const char *url,const char *api_key,const char *device_node_id,
                      const char *model_version,const char *cert_pem);
/* Nonblocking, no retries. Only the light mappings are implemented. False means
   rejected or queue full; callers must log/drop, not accumulate stale commands. */
bool voice_http_enqueue(const char *label,float confidence);
#ifdef __cplusplus
}
#endif
