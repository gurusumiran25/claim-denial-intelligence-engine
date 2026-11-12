"""Optional LLM polish for a drafted letter. OFF by default; the project never needs it.

Set LLM_BACKEND=anthropic, ANTHROPIC_API_KEY and ANTHROPIC_MODEL (and install the `anthropic`
package) to turn it on. The polished text is accepted only if every citation marker and every
number from the original letter is still present; otherwise the original letter is returned
unchanged.
"""

from __future__ import annotations

import os
import re

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
MARKER = re.compile(r"\[\d+\]")


def _preserved(original: str, polished: str) -> bool:
    return set(MARKER.findall(original)) <= set(MARKER.findall(polished)) and set(
        NUMBER.findall(original)
    ) <= set(NUMBER.findall(polished))


def polish_letter(text: str, backend: str | None = None, client=None) -> str:
    backend = backend or os.getenv("LLM_BACKEND", "none")
    if backend != "anthropic":
        return text
    try:
        if client is None:
            import anthropic  # optional dependency

            model = os.environ["ANTHROPIC_MODEL"]
            client = anthropic.Anthropic()
        else:
            model = os.getenv("ANTHROPIC_MODEL", "test-model")
        reply = client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Improve the readability of this appeal letter. Do not add facts, "
                        "do not change any number, and keep every [n] citation marker. "
                        "Return only the letter.\n\n" + text
                    ),
                }
            ],
        )
        polished = reply.content[0].text.strip()
    except Exception:
        return text
    return polished if polished and _preserved(text, polished) else text
