
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from scipy.signal import spectrogram

files = {
    "ON": "test/audio_samples/on_001.wav",
    "QUIET": "test/audio_samples/quiet_001.wav",
    "NOISE": "test/audio_samples/noise_001.wav",
}

fig, axes = plt.subplots(3, 2, figsize=(14, 10))

for row, (name, path) in enumerate(files.items()):
    audio, sr = sf.read(path)

    # Remove DC offset for analysis
    clean = audio - np.mean(audio)

    time = np.arange(len(audio)) / sr

    # Waveform
    axes[row, 0].plot(time, clean)
    axes[row, 0].set_title(f"{name} - Waveform")
    axes[row, 0].set_xlabel("Time (s)")
    axes[row, 0].set_ylabel("Amplitude")

    # Spectrogram
    f, t, Sxx = spectrogram(
        clean,
        fs=sr,
        nperseg=512,
        noverlap=384
    )

    axes[row, 1].pcolormesh(
        t, f, 10 * np.log10(Sxx + 1e-12),
        shading="auto"
    )
    axes[row, 1].set_ylim(0, 8000)
    axes[row, 1].set_title(f"{name} - Spectrogram")
    axes[row, 1].set_xlabel("Time (s)")
    axes[row, 1].set_ylabel("Frequency (Hz)")

plt.tight_layout()
plt.show()
