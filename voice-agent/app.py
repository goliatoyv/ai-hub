import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse
import anthropic
from elevenlabs import ElevenLabs, VoiceSettings
from twilio.twiml.voice_response import VoiceResponse, Gather

from config import build_system_prompt

app = FastAPI()

AUDIO_DIR = Path("audio")
AUDIO_DIR.mkdir(exist_ok=True)

anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
elevenlabs_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])

VOICE_ID = os.environ["ELEVENLABS_VOICE_ID"]
BASE_URL = os.environ["BASE_URL"].rstrip("/")  # e.g. https://xxxx.ngrok.io

# In-memory conversation history per call
conversations: dict[str, list[dict]] = {}


def twiml_gather(action: str) -> Gather:
    return Gather(
        input="speech",
        language="ru-RU",
        action=action,
        speech_timeout="auto",
        timeout=6,
    )


def generate_audio(text: str) -> str:
    """Generate TTS with cloned voice, return public URL."""
    audio_id = str(uuid.uuid4())
    audio_path = AUDIO_DIR / f"{audio_id}.mp3"

    stream = elevenlabs_client.text_to_speech.convert(
        voice_id=VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
        voice_settings=VoiceSettings(
            stability=0.45,
            similarity_boost=0.85,
            style=0.0,
            use_speaker_boost=True,
        ),
    )

    with open(audio_path, "wb") as f:
        for chunk in stream:
            if chunk:
                f.write(chunk)

    return f"{BASE_URL}/audio/{audio_id}"


def ask_claude(call_sid: str, user_text: str) -> str:
    history = conversations.setdefault(call_sid, [])
    history.append({"role": "user", "content": user_text})

    result = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        system=build_system_prompt(),
        messages=history,
    )

    reply = result.content[0].text
    history.append({"role": "assistant", "content": reply})
    return reply


@app.post("/incoming-call")
async def incoming_call(request: Request):
    form = await request.form()
    call_sid = form.get("CallSid", str(uuid.uuid4()))
    conversations[call_sid] = []

    # Generate opening greeting
    greeting_url = generate_audio("Алло?")

    response = VoiceResponse()
    gather = twiml_gather(action=f"/handle-speech?call_sid={call_sid}")
    gather.play(greeting_url)
    response.append(gather)
    # If no speech detected, hang up politely
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@app.post("/handle-speech")
async def handle_speech(request: Request, call_sid: str = ""):
    form = await request.form()
    speech_result = form.get("SpeechResult", "").strip()
    call_sid = call_sid or form.get("CallSid", str(uuid.uuid4()))

    response = VoiceResponse()

    if not speech_result:
        silence_url = generate_audio("Алло, ты здесь?")
        gather = twiml_gather(action=f"/handle-speech?call_sid={call_sid}")
        gather.play(silence_url)
        response.append(gather)
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    reply_text = ask_claude(call_sid, speech_result)
    audio_url = generate_audio(reply_text)

    gather = twiml_gather(action=f"/handle-speech?call_sid={call_sid}")
    gather.play(audio_url)
    response.append(gather)
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    audio_path = AUDIO_DIR / f"{audio_id}.mp3"
    if not audio_path.exists():
        return Response(status_code=404)
    return FileResponse(audio_path, media_type="audio/mpeg")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
