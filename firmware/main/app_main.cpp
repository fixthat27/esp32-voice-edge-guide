#include <cstdio>
#include <cstdint>
#include <cmath>
#include "sdkconfig.h"
#include "driver/i2s_std.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "board_config.h"
#include "mfcc.h"
#if CONFIG_VOICE_INFERENCE
extern bool inference_init();
extern void inference_run(const float *features);
#endif
static int16_t pcm[AUDIO_SAMPLES];
static float features[AUDIO_FEATURE_N];
static int32_t stereo[AUDIO_READ_FRAMES*2];
extern "C" void app_main(void) {
    i2s_chan_handle_t rx;
    i2s_chan_config_t chan=I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0,I2S_ROLE_MASTER);
    ESP_ERROR_CHECK(i2s_new_channel(&chan,nullptr,&rx));
    i2s_std_config_t cfg={};
    cfg.clk_cfg=I2S_STD_CLK_DEFAULT_CONFIG(SAMPLE_RATE);
    cfg.slot_cfg=I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT,I2S_SLOT_MODE_STEREO);
    cfg.gpio_cfg.mclk=I2S_GPIO_UNUSED;
    cfg.gpio_cfg.bclk=(gpio_num_t)MIC_BCLK;
    cfg.gpio_cfg.ws=(gpio_num_t)MIC_WS;
    cfg.gpio_cfg.dout=I2S_GPIO_UNUSED;
    cfg.gpio_cfg.din=(gpio_num_t)MIC_DATA;
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx,&cfg));

    ESP_ERROR_CHECK(i2s_channel_enable(rx)); // Added, change for line 41, enable once
#if CONFIG_VOICE_INFERENCE
    if(!inference_init()) return;
#endif
    unsigned clip=0;
    for(;;) {
        printf("READY clip=%u capture starts in 2 seconds\n",clip); fflush(stdout);
        vTaskDelay(pdMS_TO_TICKS(2000));

        // ESP_ERROR_CHECK(i2s_channel_enable(rx));

        // Discard startup data. Capture in stereo to preserve 64 BCLKs/frame.
        size_t got;
        for(int i=0;i<4;i++) ESP_ERROR_CHECK(i2s_channel_read(rx,stereo,sizeof(stereo),&got,1000));
        size_t n=0;
        while(n<AUDIO_SAMPLES) {
            ESP_ERROR_CHECK(i2s_channel_read(rx,stereo,sizeof(stereo),&got,1000));
            if(got%8 || got==0) {ESP_ERROR_CHECK(ESP_FAIL);}
            for(size_t j=0;j<got/8 && n<AUDIO_SAMPLES;j++)
                pcm[n++]=(int16_t)(stereo[j*2]>>16);
        }

        // Suggested never disable
        // ESP_ERROR_CHECK(i2s_channel_disable(rx));
        
#if CONFIG_VOICE_INFERENCE
        int64_t start=esp_timer_get_time();
        mfcc_compute(pcm,features);
        printf("MFCC us=%lld\n",(long long)(esp_timer_get_time()-start));
        inference_run(features);
#else
        // Dump only after capture, so a slow serial link cannot lose I2S samples.
        printf("PCM_BEGIN %u %u\n",clip,AUDIO_SAMPLES);
        for(int i=0;i<AUDIO_SAMPLES;i+=32) {
            printf("PCM %05d ",i);
            for(int j=0;j<32;j++) printf("%04x",(unsigned)(uint16_t)pcm[i+j]);
            printf("\n");
            if(i%512==0) vTaskDelay(1);
        }
        printf("PCM_END %u\n",clip);
#endif
        fflush(stdout); clip++;
    }
}
