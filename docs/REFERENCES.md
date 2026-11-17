# ESP32 voice edge references

Checked 2026-11-13 against official sources. Project inputs: ESP32-S3 N16R8, recorded ESP-IDF v6.1, INMP441 BCLK GPIO17, WS GPIO16, SD to ESP32 DIN GPIO18. These notes establish a design baseline, not a successful local build or hardware test.

## I2S capture and sample interpretation

The INMP441 produces signed, two's-complement, 24-bit Philips I2S data. It requires 64 bit clocks per stereo frame, with 32 clocks per slot, even when only one microphone is connected. The MSB follows the WS transition by one clock. Ground L/R for the left slot. SD becomes high impedance after the valid bits and during the unselected slot; the datasheet recommends a 100 kΩ SD pull-down. [TDK INMP441 datasheet, pin descriptions and I2S interface](https://invensense.tdk.com/wp-content/uploads/2015/02/INMP441.pdf)

Use the standard RX driver in `driver/i2s_std.h`, ESP32-S3 as master, and `I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG` with `I2S_DATA_BIT_WIDTH_32BIT` and `I2S_SLOT_MODE_STEREO`. Keep both slots enabled, 32-bit slot width, normal polarity, BCLK=17, WS=16, DIN=18, and MCLK/DOUT unused. Read interleaved left/right words and retain the left word of each frame. Do not average an undriven right slot into the audio. At a proposed 16 kHz sample rate, the required BCLK is 1.024 MHz. Use the channel allocation, standard-mode initialization, enable, and read APIs from the [ESP-IDF standard I2S guide, currently v6.1](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/i2s.html).

Derived from this framing: the meaningful sample occupies bits 31:8 of each captured 32-bit word. Discard the bottom eight bits and sign-extend the remaining 24 bits. For PCM16, arithmetic shifting the original signed word by 16 preserves the most significant 16 sample bits. Verify alignment and sign with raw captures before adding gain; saturate amplified samples rather than wrapping them.

## ESP-IDF version and component compatibility

ESP-IDF v6.1 is an actual release, dated August 27, 2026, and the stable I2S documentation currently identifies itself as v6.1. Do not describe it as unavailable or automatically replace it with 5.x. Espressif calls it mostly compatible with v6.0, which does not certify every third-party component. [Official v6.1 release](https://github.com/espressif/esp-idf/releases/tag/v6.1)

Record `idf.py --version` and the exact IDF Git revision, including any `-dev` suffix or local changes. Pin versioned documentation and dependency versions because `stable`, `latest`, and `master` move. The user's recorded version alone does not prove which checkout is active.

The registry currently offers `espressif/esp-tflite-micro` 1.4.3. Its support table includes IDF release/v6.0 and several 5.x branches but does not list v6.1. Absence is not proof of incompatibility. The upstream manifest declares IDF `>=5.1` and ESP-NN `>=1.4.2`; satisfying these constraints is not a verified v6.1 build. [Component installation and support table](https://components.espressif.com/components/espressif/esp-tflite-micro/versions/1.4.3/readme), [upstream manifest](https://raw.githubusercontent.com/espressif/esp-tflite-micro/master/idf_component.yml)

In an IDF project, select `esp32s3` and add a pinned dependency with `idf.py add-dependency "espressif/esp-tflite-micro==1.4.3"`. Preserve `idf_component.yml`, `dependencies.lock`, SDK configuration, and toolchain versions. Build a minimal inference example before integrating audio/networking. If v6.1 fails, reproduce on a specific released v6.0 version covered by the support table. Register the model's actual operators and measure tensor-arena use and latency on the board; N16R8 capacity alone does not establish feasibility.

## Small Keras CNN and full INT8 export

TensorFlow's audio tutorial demonstrates WAV decoding, spectrogram extraction, and a Keras CNN. Its illustrated network has about 1.6 million parameters, so it is a teaching reference, not an ESP32-sized guarantee. Suggested starting design: fixed-size features, two small Conv2D/ReLU blocks, pooling, and a small classifier. Match training and firmware windowing, scaling, feature extraction, and label order exactly. Test silence, unknown speech, and different speakers. [TensorFlow keyword-recognition tutorial](https://www.tensorflow.org/tutorials/audio/simple_audio)

For the documented TensorFlow converter workflow, create `tf.lite.TFLiteConverter.from_keras_model(model)`, set `optimizations` to `[tf.lite.Optimize.DEFAULT]`, and supply a representative dataset of preprocessed training inputs with the correct batch shape. Restrict `target_spec.supported_ops` to `[tf.lite.OpsSet.TFLITE_BUILTINS_INT8]`; set both `inference_input_type` and `inference_output_type` to `tf.int8`. Calibration alone can leave float I/O or float operators. Inspect exported tensor types, quantization scales, zero points, and operator versions, then compare desktop and device predictions. Integer-only inference can still use wider integer biases/accumulators.

Version caution: Google's current documentation marks quantization during conversion deprecated in favor of the separate LiteRT Quantizer. Pin the tested TensorFlow/Keras conversion environment; validate any newer export against the selected TFLite Micro runtime. [Google integer-quantization guide](https://developers.google.com/edge/litert/conversion/tensorflow/quantization/post_training_integer_quant)

## MQTT acknowledgment and HTTP

MQTT QoS 1 PUBACK confirms message ownership transfer to the receiving protocol peer. It does not prove subscriber delivery or physical actuation. QoS 1 permits duplicates; QoS 2 also does not prove physical state. Design recommendation: distinguish command acceptance from reported state, correlate command IDs, make retries idempotent, and require sensor feedback for physical confirmation. [OASIS MQTT 3.1.1, sections 4.3–4.5](https://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.html)

Since IDF v6.0, ESP-MQTT is separate; add `espressif/mqtt` through Component Manager and pin the resolved version. [IDF v6.1 MQTT migration note](https://docs.espressif.com/projects/esp-idf/en/v6.1/esp32s3/api-reference/protocols/mqtt.html)

For HTTP/S, initialize an `esp_http_client` handle, perform the request, inspect transport errors, HTTP status and application response, then clean up or reuse the handle. `esp_http_client_perform()` normally blocks, so keep requests outside the audio capture task. Configure timeouts and TLS server verification. An HTTP success response establishes only the endpoint's documented semantics, not measured actuator state. [ESP-IDF v6.1 HTTP client](https://docs.espressif.com/projects/esp-idf/en/v6.1/esp32s3/api-reference/protocols/esp_http_client.html)


## Bundle export implementation

The supplied script uses `model.export()` to create an inference SavedModel and
`TFLiteConverter.from_saved_model()` before applying integer conversion settings.
These are documented API paths; the package's proposed TensorFlow/Keras pins were
not executed here. See the [Keras export API](https://keras.io/api/models/model_saving_apis/export/)
and [TensorFlow Lite converter API](https://www.tensorflow.org/api_docs/python/tf/lite/TFLiteConverter).
Current web documentation can describe newer releases than the pinned environment.
