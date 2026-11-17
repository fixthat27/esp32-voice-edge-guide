#include "esp32_http_transport.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "cJSON.h"
#include "esp_http_client.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
typedef struct { bool on; float confidence; int64_t created; } job_t;
typedef struct { char text[2048]; size_t used; bool overflow; } response_t;
static QueueHandle_t queue;
static const char *endpoint,*key,*node,*version,*certificate;
static esp_err_t event(esp_http_client_event_t *e) {
    response_t *r=e->user_data;
    if(e->event_id==HTTP_EVENT_ON_DATA && e->data_len>0) {
        if(r->used+(size_t)e->data_len>=sizeof(r->text)) {r->overflow=true; return ESP_FAIL;}
        memcpy(r->text+r->used,e->data,e->data_len); r->used+=e->data_len; r->text[r->used]=0;
    }
    return ESP_OK;
}
static void worker(void *unused) {
    (void)unused;
    uint32_t boot=esp_random(),sequence=0;
    job_t job;
    for(;;) {
        if(xQueueReceive(queue,&job,portMAX_DELAY)!=pdTRUE) continue;
        if(esp_timer_get_time()-job.created>2000000) {printf("VOICE_HTTP stale_drop\n"); continue;}
        char id[128];
        int len=snprintf(id,sizeof(id),"%s-%08lx-%08lx",node,(unsigned long)boot,(unsigned long)++sequence);
        if(len<0 || (size_t)len>=sizeof(id)) continue;
        cJSON *body=cJSON_CreateObject();
        if(!body) continue;
        bool valid=cJSON_AddStringToObject(body,"request_id",id) &&
            cJSON_AddStringToObject(body,"source","esp32_tinyml") &&
            cJSON_AddStringToObject(body,"device_id","technical-office-light") &&
            cJSON_AddStringToObject(body,"intent","device_control") &&
            cJSON_AddStringToObject(body,"action",job.on?"turn_on":"turn_off") &&
            cJSON_AddBoolToObject(body,"value",job.on) &&
            cJSON_AddNumberToObject(body,"confidence",job.confidence) &&
            cJSON_AddStringToObject(body,"model_version",version);
        char *json=valid?cJSON_PrintUnformatted(body):NULL;
        cJSON_Delete(body);
        if(!json) continue;
        response_t response={0};
        esp_http_client_config_t cfg={.url=endpoint,.timeout_ms=2000,
            .event_handler=event,.user_data=&response,.cert_pem=certificate,
            .disable_auto_redirect=true};
        esp_http_client_handle_t client=esp_http_client_init(&cfg);
        if(!client) {cJSON_free(json); continue;}
        esp_err_t err=esp_http_client_set_method(client,HTTP_METHOD_POST);
        if(err==ESP_OK) err=esp_http_client_set_header(client,"Content-Type","application/json");
        if(err==ESP_OK) err=esp_http_client_set_header(client,"X-API-Key",key);
        if(err==ESP_OK) err=esp_http_client_set_post_field(client,json,strlen(json));
        if(err==ESP_OK) err=esp_http_client_perform(client);
        int status=esp_http_client_get_status_code(client);
        printf("VOICE_HTTP id=%s transport=%d http=%d\n",id,err,status);
        if(err==ESP_OK && status>=200 && status<300 && !response.overflow) {
            cJSON *reply=cJSON_Parse(response.text);
            cJSON *rid=cJSON_GetObjectItemCaseSensitive(reply,"request_id");
            cJSON *state=cJSON_GetObjectItemCaseSensitive(reply,"status");
            if(cJSON_IsString(rid) && !strcmp(rid->valuestring,id) && cJSON_IsString(state)) {
                // Report the server's status only, never infer physical state.
                const char *s=state->valuestring;
                if(!strcmp(s,"accepted") || !strcmp(s,"published") || !strcmp(s,"shadow") ||
                   !strcmp(s,"indeterminate") || !strcmp(s,"rejected") || !strcmp(s,"failed"))
                    printf("VOICE_HTTP id=%s result=%s physical_state_unverified=1\n",id,s);
                else printf("VOICE_HTTP unexpected_status\n");
            } else printf("VOICE_HTTP malformed_or_uncorrelated_response\n");
            cJSON_Delete(reply);
        }
        esp_http_client_cleanup(client); cJSON_free(json);
        // No retry after uncertainty. Continue serving fresh commands only.
    }
}
bool voice_http_start(const char *url,const char *api_key,const char *device_node_id,
                      const char *model_version,const char *cert_pem) {
    if(queue || !url || !api_key || !device_node_id || !model_version) return false;
    endpoint=url; key=api_key; node=device_node_id; version=model_version; certificate=cert_pem;
    queue=xQueueCreate(4,sizeof(job_t));
    if(!queue) return false;
    if(xTaskCreate(worker,"voice_http",6144,NULL,3,NULL)!=pdPASS) {
        vQueueDelete(queue); queue=NULL; return false;
    }
    return true;
}
bool voice_http_enqueue(const char *label,float confidence) {
    if(!queue || !label || !isfinite(confidence) || confidence<.85f || confidence>1) return false;
    bool on=!strcmp(label,"light_on"),off=!strcmp(label,"light_off");
    if(!on && !off) return false;
    job_t job={.on=on,.confidence=confidence,.created=esp_timer_get_time()};
    return xQueueSend(queue,&job,0)==pdTRUE;
}
