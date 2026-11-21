#include <cstdio>
#include <cmath>
#include <cstring>
#include <cstdint>
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/schema/schema_generated.h"
#include "model_metadata.h"
#include "golden_input.h"
#include "mfcc.h"

#define TENSOR_ARENA_SIZE (256*1024)

static uint8_t *arena = nullptr;
extern const unsigned char command_model[];
// alignas(16) static unsigned char arena[TENSOR_ARENA_SIZE];
static tflite::MicroInterpreter *engine;

bool inference_init() {
    const auto *model=tflite::GetModel(command_model);
    if(model->version()!=TFLITE_SCHEMA_VERSION) return false;
    static tflite::MicroMutableOpResolver<6> ops;
    if(ops.AddConv2D()!=kTfLiteOk || ops.AddMaxPool2D()!=kTfLiteOk ||
       ops.AddReshape()!=kTfLiteOk || ops.AddFullyConnected()!=kTfLiteOk ||
       ops.AddSoftmax()!=kTfLiteOk || ops.AddMean()!=kTfLiteOk) return false;

    // static tflite::MicroInterpreter interpreter(model,ops,arena,sizeof(arena));
    // engine=&interpreter;

    // Allocate tensor arena from external PSRAM
    arena = static_cast<uint8_t*>(
        heap_caps_aligned_alloc(
            16,
            TENSOR_ARENA_SIZE,
            MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT
        )
    );

    if (arena == nullptr) {
        printf("ERROR: PSRAM tensor arena allocation failed\n");
        return false;
    }

    printf("Tensor arena allocated: %u bytes\n",
        (unsigned)TENSOR_ARENA_SIZE);

    static tflite::MicroInterpreter interpreter(
        model,
        ops,
        arena,
        TENSOR_ARENA_SIZE
    );

    engine = &interpreter;

    if(engine->AllocateTensors()!=kTfLiteOk) return false;
    auto *in=engine->input(0), *out=engine->output(0);
    if(in->type!=kTfLiteInt8 || out->type!=kTfLiteInt8 ||
       in->bytes!=AUDIO_FEATURE_N || out->bytes!=LABEL_COUNT ||
       in->dims->size!=4 || in->dims->data[1]!=AUDIO_FRAMES || in->dims->data[2]!=AUDIO_MFCC ||
       in->params.scale<=0 || out->params.scale<=0) return false;
    printf("arena_used=%u\n",(unsigned)engine->arena_used_bytes());
    memcpy(in->data.int8,GOLDEN_INPUT,AUDIO_FEATURE_N);
    if(engine->Invoke()!=kTfLiteOk) return false;
    int mismatches=0;
    for(int i=0;i<LABEL_COUNT;i++) {
        printf("golden class=%d expected=%d actual=%d\n",i,GOLDEN_OUTPUT[i],out->data.int8[i]);
        if(GOLDEN_OUTPUT[i]!=out->data.int8[i]) mismatches++;
    }
    if(mismatches) {printf("GOLDEN_MISMATCH: investigate kernel differences before live tests\n"); return false;}
    return true;
}
void inference_run(const float *features) {
    auto *in=engine->input(0);
    for(int i=0;i<AUDIO_FEATURE_N;i++) {
        float x=(features[i]-FEATURE_MEAN[i%AUDIO_MFCC])/FEATURE_STD[i%AUDIO_MFCC];
        int q=(int)roundf(x/in->params.scale)+in->params.zero_point;
        in->data.int8[i]=(int8_t)(q<-128?-128:(q>127?127:q));
    }
    auto start=esp_timer_get_time();
    if(engine->Invoke()!=kTfLiteOk) {printf("INFERENCE_FAILED\n"); return;}
    auto *out=engine->output(0);
    int best=0;
    for(int i=0;i<LABEL_COUNT;i++) if(out->data.int8[i]>out->data.int8[best]) best=i;
    float score=(out->data.int8[best]-out->params.zero_point)*out->params.scale;
    printf("prediction=%s score=%.4f invoke_us=%lld shadow_only=1\n",
           LABELS[best],score,(long long)(esp_timer_get_time()-start));
    // Deliberately no GPIO or network actuation in this bench build.
}
