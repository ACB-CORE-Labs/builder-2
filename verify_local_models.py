import os
import sys
import json
from pathlib import Path
from openai import OpenAI

# The local MLX LM server usually runs on port 8080 or 8000 depending on how you launch it.
# Assuming standard mlx_lm.server which binds to 8080 by default:
MLX_ENDPOINT = "http://127.0.0.1:8080/v1"

# Ollama default endpoint
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/v1"

MLX_MODELS = [
    "mlx-community/Phi-4-mini-reasoning-4bit",
    "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
    "mlx-community/gemma-4-e4b-it-4bit",
    "mlx-community/gemma-4-12B-it-4bit",
    "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
    "mlx-community/codegeex4-all-9b-4bit",
    "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
    "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
    "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
]

OLLAMA_MODELS = [
    "gemma4:e4b",
    "gemma4:e2b",
    "qwen3.5:2b",
    "qwen3.5:0.8b",
    "ibm/granite4.1:3b"
]

def test_model(client: OpenAI, model_name: str, provider: str):
    print(f"\n--- Testing {provider} Model: {model_name} ---")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Hello! Please reply with exactly the words 'Test passed' and nothing else."}],
            max_tokens=20,
            timeout=15.0
        )
        content = response.choices[0].message.content.strip()
        print(f"✅ SUCCESS! Response received:")
        print(f"   \"{content}\"")
        return True
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Builder-II Local Model API Verification Utility")
    print("=" * 60)
    print("\nThis script tests if the local endpoints are accepting requests and returning outputs properly.")
    
    # Test Ollama
    print("\n[1] Testing Ollama Models (ensure 'ollama serve' is running)")
    try:
        ollama_client = OpenAI(base_url=OLLAMA_ENDPOINT, api_key="ollama")
        for model in OLLAMA_MODELS:
            test_model(ollama_client, model, "Ollama")
    except Exception as e:
        print(f"Could not connect to Ollama: {e}")

    # Test MLX
    print("\n[2] Testing MLX Models (ensure 'mlx_lm.server' is running on port 8080)")
    try:
        mlx_client = OpenAI(base_url=MLX_ENDPOINT, api_key="mlx")
        for model in MLX_MODELS:
            test_model(mlx_client, model, "MLX")
    except Exception as e:
        print(f"Could not connect to MLX server: {e}")

    print("\n" + "=" * 60)
    print("Verification complete.")
    print("Note: To run an MLX model locally via its server, use:")
    print("   python -m mlx_lm.server --model <model_id>")
    print("=" * 60)

if __name__ == "__main__":
    main()
