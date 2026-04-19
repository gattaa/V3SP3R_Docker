class TextToSpeechMock:
    def speak(self, text: str) -> None:
        print(f"[tts mock] {text}")
