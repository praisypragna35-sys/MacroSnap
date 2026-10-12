
from pathlib import Path
import tomllib
from google import genai

secrets_path = Path(".streamlit/secrets.toml")
secrets = tomllib.loads(secrets_path.read_text(encoding="utf-8"))

client = genai.Client(api_key=secrets["GEMINI_API_KEY"])

print("Models available for text generation:")

for model in client.models.list():
    if "generateContent" in (model.supported_actions or []):
        print(model.name)