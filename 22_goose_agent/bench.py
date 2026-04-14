"""Ollama ベンチマーク: token/s を計測"""
import requests
import sys
import time

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:9b"


def bench(model: str, prompt: str, use_tools: bool = False) -> dict:
    """Ollama API を叩いて速度計測"""
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if use_tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": "Run a shell command",
                    "parameters": {
                        "type": "object",
                        "properties": {"command": {"type": "string"}},
                        "required": ["command"],
                    },
                },
            }
        ]

    start = time.time()
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload)
    wall = time.time() - start
    data = r.json()

    eval_count = data.get("eval_count", 0)
    eval_dur = data.get("eval_duration", 1) / 1e9
    prompt_count = data.get("prompt_eval_count", 0)
    prompt_dur = data.get("prompt_eval_duration", 1) / 1e9
    load_dur = data.get("load_duration", 0) / 1e9

    return {
        "model": model,
        "prompt_tokens": prompt_count,
        "prompt_tok_s": prompt_count / prompt_dur if prompt_dur > 0 else 0,
        "eval_tokens": eval_count,
        "eval_tok_s": eval_count / eval_dur if eval_dur > 0 else 0,
        "load_s": load_dur,
        "wall_s": wall,
        "response": data.get("message", {}).get("content", "")[:80],
    }


def main() -> None:
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"=== Ollama Benchmark: {model} ===\n")

    tests = [
        ("Simple chat", "Say just OK", False),
        ("Chat + tools", "Say just OK", True),
        ("Long output", "Write a 5-line Python fizzbuzz function", True),
    ]

    for name, prompt, tools in tests:
        print(f"[{name}]")
        r = bench(model, prompt, tools)
        print(f"  Prompt:    {r['prompt_tokens']} tok @ {r['prompt_tok_s']:.1f} tok/s")
        print(f"  Generate:  {r['eval_tokens']} tok @ {r['eval_tok_s']:.1f} tok/s")
        print(f"  Load:      {r['load_s']:.2f}s")
        print(f"  Wall:      {r['wall_s']:.2f}s")
        print(f"  Response:  {r['response']}")
        print()


if __name__ == "__main__":
    main()
