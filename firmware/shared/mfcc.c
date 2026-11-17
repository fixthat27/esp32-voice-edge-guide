#include "mfcc.h"
#include <math.h>
#include <string.h>
#define PI 3.14159265358979323846f
static double re[512], im[512], power_bins[257];
static float mel[40];
static double win[400];
static float weights[40][257], dct[13][40];
static int ready;
static void init(void) {
    float edges[42];
    float lo=2595*log10f(1+20.0f/700), hi=2595*log10f(1+7600.0f/700);
    for(int i=0;i<400;i++) win[i]=0.5-0.5*cos(2*3.14159265358979323846*i/400);
    for(int i=0;i<42;i++) edges[i]=700*(powf(10,(lo+(hi-lo)*i/41)/2595)-1);
    for(int m=0;m<40;m++) for(int k=0;k<257;k++) {
        float hz=k*16000.0f/512;
        float a=(hz-edges[m])/(edges[m+1]-edges[m]);
        float b=(edges[m+2]-hz)/(edges[m+2]-edges[m+1]);
        weights[m][k]=fmaxf(0,fminf(a,b));
    }
    for(int c=0;c<13;c++) for(int m=0;m<40;m++)
        dct[c][m]=sqrtf((c?2.0f:1.0f)/40)*cosf(PI*c*(m+0.5f)/40);
    ready=1;
}
static void fft(void) {
    for(int i=1,j=0;i<512;i++) {
        int bit=256;
        for(;j&bit;bit>>=1) j^=bit;
        j^=bit;
        if(i<j) {double t=re[i]; re[i]=re[j]; re[j]=t;}
    }
    for(int len=2;len<=512;len*=2) {
        double cr=cos(-2*3.14159265358979323846/len), ci=sin(-2*3.14159265358979323846/len);
        for(int b=0;b<512;b+=len) {
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
    for(int f=0;f<98;f++) {
        memset(re,0,sizeof(re)); memset(im,0,sizeof(im));
        for(int n=0;n<400;n++) re[n]=(pcm[f*160+n]/32768.0f)*win[n];
        fft();
        for(int k=0;k<257;k++) power_bins[k]=(re[k]*re[k]+im[k]*im[k])/512;
        for(int m=0;m<40;m++) {
            float sum=0;
            for(int k=0;k<257;k++) sum+=weights[m][k]*power_bins[k];
            mel[m]=logf(fmaxf(sum,1e-10f));
        }
        for(int c=0;c<13;c++) {
            float sum=0;
            for(int m=0;m<40;m++) sum+=dct[c][m]*mel[m];
            out[f*13+c]=sum;
        }
    }
}

