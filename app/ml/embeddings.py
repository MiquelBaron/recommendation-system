def embed_text(text: str) -> list[float]:
    # Lightweight deterministic placeholder embedding.
    base = [0.0, 0.0, 0.0]
    for idx, char in enumerate(text):
        base[idx % 3] += ord(char) / 255.0
    return base
