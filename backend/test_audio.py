import json
with open("response.json") as f:
    data = json.load(f)
audio_data = bytes.fromhex(data["audio"])
with open("output.wav", "wb") as f:
    f.write(audio_data)