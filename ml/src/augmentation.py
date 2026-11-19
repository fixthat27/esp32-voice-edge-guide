
import numpy as np
import soundfile as sf
import librosa
from pathlib import Path

SAMPLE_RATE = 16000


def load_audio(path):
    audio, sr = sf.read(path)

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sr != SAMPLE_RATE:
        audio = librosa.resample(
            audio,
            orig_sr=sr,
            target_sr=SAMPLE_RATE
        )

    return audio.astype(np.float32)


def time_shift(audio, max_shift_ms=150):
    max_shift = int(SAMPLE_RATE * max_shift_ms / 1000)
    shift = np.random.randint(-max_shift, max_shift + 1)

    result = np.zeros_like(audio)

    if shift > 0:
        result[shift:] = audio[:-shift]
    elif shift < 0:
        result[:shift] = audio[-shift:]
    else:
        result = audio.copy()

    return result

def fit_length(audio, target_length):
    if len(audio) > target_length:
        start = (len(audio) - target_length) // 2
        return audio[start:start + target_length]

    if len(audio) < target_length:
        padding = target_length - len(audio)
        return np.pad(audio, (0, padding))

    return audio

def random_gain(audio, min_gain=0.7, max_gain=1.3):
    gain = np.random.uniform(min_gain, max_gain)
    return audio * gain


def add_noise(audio, noise, min_snr=15, max_snr=30):
    # Randomly select a section of background noise
    if len(noise) < len(audio):
        noise = np.tile(
            noise,
            int(np.ceil(len(audio) / len(noise)))
        )

    start = np.random.randint(0, len(noise) - len(audio) + 1)
    noise = noise[start:start + len(audio)]

    signal_power = np.mean(audio ** 2)
    noise_power = np.mean(noise ** 2)

    if signal_power < 1e-10 or noise_power < 1e-10:
        return audio.copy()

    snr_db = np.random.uniform(min_snr, max_snr)

    scale = np.sqrt(
        signal_power /
        (noise_power * (10 ** (snr_db / 10)))
    )

    return audio + noise * scale


def time_stretch(audio, min_rate=0.9, max_rate=1.1):
    rate = np.random.uniform(min_rate, max_rate)

    return librosa.effects.time_stretch(
        audio,
        rate=rate
    )


def pitch_shift(audio, max_semitones=1):
    steps = np.random.uniform(
        -max_semitones,
        max_semitones
    )

    return librosa.effects.pitch_shift(
        audio,
        sr=SAMPLE_RATE,
        n_steps=steps
    )


def augment(audio, noise=None):
    result = audio.copy()

    operations = [
        lambda x: random_gain(x, 0.7, 1.3),
        lambda x: time_shift(x, 150),
    ]

    if noise is not None:
        operations.append(
            lambda x: add_noise(x, noise)
        )

    # Always execute at least one operations
    selected = np.random.choice(
        len(operations),
        size=np.random.randint(1, len(operations) + 1),
        replace=False
    )

    for idx in selected:
        result = operations[idx](result)

    return fit_length(result, len(audio)).astype(np.float32)


def generate_augmented(
    input_path,
    output_dir,
    noise_path=None,
    count=5
):
    audio = load_audio(input_path)

    noise = load_audio(noise_path) if noise_path else None

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(1, count + 1):
        augmented = augment(audio, noise)

        # Reject samples that clip
        if np.max(np.abs(augmented)) >= 1.0:
            print(f"Skipped sample {i}: clipping")
            continue

        output_path = output_dir / f"aug_{i:03d}.wav"

        sf.write(
            output_path,
            augmented,
            SAMPLE_RATE,
            subtype="PCM_16"
        )

        print(f"Saved: {output_path}")
