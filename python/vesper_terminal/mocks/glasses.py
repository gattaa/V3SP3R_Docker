class GlassesMock:
    def request_photo(self, prompt: str) -> str:
        return f"[glasses mock photo response for: {prompt}]"
