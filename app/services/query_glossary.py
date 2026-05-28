"""PT → EN para termos comuns em buscas de figurinha (sem LLM)."""

GLOSSARY: dict[str, str] = {
    "raiva": "angry",
    "bravo": "angry",
    "brava": "angry",
    "irritado": "angry",
    "irritada": "angry",
    "feliz": "happy",
    "alegre": "happy",
    "triste": "sad",
    "tristeza": "sad",
    "chorando": "crying",
    "choro": "crying",
    "amor": "love",
    "beijo": "kiss",
    "joinha": "thumbs up",
    "joia": "thumbs up",
    "jóia": "thumbs up",
    "ok": "thumbs up",
    "medo": "scared",
    "assustado": "scared",
    "surpreso": "surprised",
    "surpresa": "surprised",
    "sono": "sleepy",
    "dormindo": "sleeping",
    "cansado": "tired",
    "cansada": "tired",
    "risada": "laughing",
    "rindo": "laughing",
    "kkk": "laughing",
    "socorro": "help me",
    "oi": "hello",
    "olá": "hello",
    "tchau": "goodbye",
    "obrigado": "thank you",
    "obrigada": "thank you",
}


def expand_to_english(query: str) -> str | None:
    key = query.strip().lower()
    return GLOSSARY.get(key)
