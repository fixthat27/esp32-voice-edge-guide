#include "mfcc.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static double re[AUDIO_FFT], im[AUDIO_FFT], power_bins[AUDIO_FREQ_BINS];
static float mel[AUDIO_MEL_BINS];
static double win[AUDIO_WINDOW];
static float weights[AUDIO_MEL_BINS][AUDIO_FREQ_BINS], dct[AUDIO_MFCC][AUDIO_MEL_BINS];
static int ready;
static void init(void) {
    float edges[AUDIO_MEL_BINS+2];
    float lo=2595*log10f(1+(float)AUDIO_FMIN/700.0f), hi=2595*log10f(1+(float)AUDIO_FMAX/700.0f);
    for(int i=0;i<AUDIO_WINDOW;i++) win[i]=0.5-0.5*cos(2*PI*i/AUDIO_WINDOW);
    for(int i=0;i<AUDIO_MEL_BINS+2;i++) edges[i]=700*(powf(10,(lo+(hi-lo)*i/(AUDIO_MEL_BINS+1))/2595)-1);
    for(int m=0;m<AUDIO_MEL_BINS;m++) for(int k=0;k<AUDIO_FREQ_BINS;k++) {
        float hz=k*(float)AUDIO_SAMPLE_RATE/(float)AUDIO_FFT;
        float a=(hz-edges[m])/(edges[m+1]-edges[m]);
        float b=(edges[m+2]-hz)/(edges[m+2]-edges[m+1]);
        weights[m][k]=fmaxf(0,fminf(a,b));
    }
    for(int c=0;c<AUDIO_MFCC;c++) for(int m=0;m<AUDIO_MEL_BINS;m++)
        dct[c][m]=sqrtf((c?2.0f:1.0f)/AUDIO_MEL_BINS)*cosf(PI*c*(m+0.5f)/AUDIO_MEL_BINS);
    ready=1;
}
static void fft(void) {
    for(int i=1,j=0;i<AUDIO_FFT;i++) {
        int bit=AUDIO_FFT/2;
        for(;j&bit;bit>>=1) j^=bit;
        j^=bit;
        if(i<j) {double t=re[i]; re[i]=re[j]; re[j]=t;}
    }
    for(int len=2;len<=AUDIO_FFT;len*=2) {
        double cr=cos(-2*PI/len), ci=sin(-2*PI/len);
        for(int b=0;b<AUDIO_FFT;b+=len) {
            double wr=1,wi=0;
            for(int j=0;j<len/2;j++) {
                int u=b+j,v=u+len/2;
                double vr=re[v]*wr-im[v]*wi, vi=re[v]*wi+im[v]*wr;
                re[v]=re[u]-vr; im[v]=im[u]-vi; re[u]+=vr; im[u]+=vi;
                double next=wr*cr-wi*ci; wi=wr*ci+wi*cr; wr=next;
            }
        }
    }
}
void mfcc_compute(const int16_t *pcm,float *out) {
    if(!ready) init();
    for(int f=0;f<AUDIO_FRAMES;f++) {
        memset(re,0,sizeof(re)); memset(im,0,sizeof(im));
        for(int n=0;n<AUDIO_WINDOW;n++) re[n]=(pcm[f*AUDIO_HOP+n]/32768.0f)*win[n];
        fft();
        for(int k=0;k<AUDIO_FREQ_BINS;k++) power_bins[k]=(re[k]*re[k]+im[k]*im[k])/(double)AUDIO_FFT;
        for(int m=0;m<AUDIO_MEL_BINS;m++) {
            float sum=0;
            for(int k=0;k<AUDIO_FREQ_BINS;k++) sum+=weights[m][k]*power_bins[k];
            mel[m]=logf(fmaxf(sum,1e-10f));
        }
        for(int c=0;c<AUDIO_MFCC;c++) {
            float sum=0;
            for(int m=0;m<AUDIO_MEL_BINS;m++) sum+=dct[c][m]*mel[m];
            out[f*AUDIO_MFCC+c]=sum;
        }
    }
}
