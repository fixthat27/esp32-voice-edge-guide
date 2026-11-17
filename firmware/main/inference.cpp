#include <cstdio>
#include <cmath>
#include <cstring>
#include "esp_timer.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "model_metadata.h"
#include "golden_input.h"
#include "mfcc.h"
extern const unsigned char command_model[];
alignas(16) static unsigned char arena[256*1024];
static tflite::MicroInterpreter *engine;
bool inference_init() {
    const auto *model=tflite::GetModel(command_model);
    if(model->version()!=TFLITE_SCHEMA_VERSION) return false;
    static tflite::MicroMutableOpResolver<6> ops;
    if(ops.AddConv2D()!=kTfLiteOk || ops.AddMaxPool2D()!=kTfLiteOk ||
       ops.AddReshape()!=kTfLiteOk || ops.AddFullyConnected()!=kTfLiteOk ||
       ops.AddSoftmax()!=kTfLiteOk || ops.AddMean()!=kTfLiteOk) return false;
    static tflite::MicroInterpreter interpreter(model,ops,arena,sizeof(arena));
    engine=&interpreter;
    if(engine->AllocateTensors()!=kTfLiteOk) return false;
    auto *in=engine->input(0), *out=engine->output(0);
    if(in->type!=kTfLiteInt8 || out->type!=kTfLiteInt8 ||
       in->bytes!=FEATURE_N || out->bytes!=LABEL_COUNT ||
       in->dims->size!=4 || in->dims->data[1]!=98 || in->dims->data[2]!=13 ||
       in->params.scale<=0 || out->params.scale<=0) return false;
    printf("arena_used=%u\n",(unsigned)engine->arena_used_bytes());
    memcpy(in->data.int8,GOLDEN_INPUT,FEATURE_N);
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
    for(int i=0;i<FEATURE_N;i++) {
        float x=(features[i]-FEATURE_MEAN[i%13])/FEATURE_STD[i%13];
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
