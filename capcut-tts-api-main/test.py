from capcut_tts_api import CapCutClient

client = CapCutClient(device="device.json")

result = client.generate_speech(
    texts="Xin chào, đây là thử nghiệm.",
    voice="BV421_vivn_streaming",
    rate="1.0",
    wait=True
)

print(result)
