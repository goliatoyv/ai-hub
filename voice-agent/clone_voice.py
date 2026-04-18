"""
Run this ONCE to clone your friend's voice and get a Voice ID.
Usage:
    python clone_voice.py sample1.mp3 sample2.mp3 ...

It will print the ELEVENLABS_VOICE_ID to put in your .env
"""
import os
import sys
from elevenlabs import ElevenLabs

def clone_voice(sample_paths: list[str]) -> str:
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

    files = []
    for path in sample_paths:
        files.append(open(path, "rb"))

    try:
        voice = client.voices.ivc.create(
            name="Friend_Cloned",
            files=files,
            description="Cloned voice for voice agent",
        )
        voice_id = voice.voice_id
        print(f"\nVoice cloned successfully!")
        print(f"ELEVENLABS_VOICE_ID={voice_id}")
        print(f"\nAdd this to your .env file.")
        return voice_id
    finally:
        for f in files:
            f.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clone_voice.py sample1.mp3 [sample2.mp3 ...]")
        print("Recommended: provide 3-5 minutes of clean audio total")
        sys.exit(1)

    clone_voice(sys.argv[1:])
