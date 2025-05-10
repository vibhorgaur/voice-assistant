import sounddevice as sd
import soundfile as sf
import numpy as np

duration = 6  # seconds
sample_rate = 44100

print("Recording... Speak now.")
audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
sd.wait()
print("Recording complete.")

# Ensure audio is 2D (samples, channels) for mono
audio = np.array(audio, dtype='float32')
if audio.ndim == 1:
    audio = audio[:, np.newaxis]  # Reshape (samples,) to (samples, 1)
elif audio.shape[1] != 1:
    audio = audio[:, :1]  # Ensure single channel

print(f"Audio shape: {audio.shape}")  # Debug shape

# Write using soundfile with explicit parameters
with sf.SoundFile("reference.wav", mode='w', samplerate=sample_rate, channels=1, format='WAV') as file:
    file.write(audio)