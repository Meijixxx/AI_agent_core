#!/bin/bash
# Goose + Ollama セットアップスクリプト
# 前提: Ollama が起動済み、Goose がPATHに存在

set -e

echo "=== Goose + Ollama Setup ==="

# 1. Goose バージョン確認
echo "[1/4] Goose バージョン確認..."
if ! command -v goose &> /dev/null; then
    echo "ERROR: goose が見つかりません。インストールしてPATHに追加してください。"
    echo "  Download: https://github.com/block/goose/releases/latest"
    exit 1
fi
goose --version

# 2. Ollama 接続確認
echo "[2/4] Ollama 接続確認..."
if ! ollama list &> /dev/null; then
    echo "ERROR: Ollama に接続できません。'ollama serve' を実行してください。"
    exit 1
fi
echo "利用可能モデル:"
ollama list

# 3. Goose プロバイダー設定案内
echo "[3/4] Goose プロバイダー設定..."
echo "  以下を実行してOllamaプロバイダーを設定してください:"
echo "    goose configure"
echo "  Provider: Ollama"
echo "  Model: qwen3.5-home (推奨)"

# 4. 動作テスト
echo "[4/4] 動作テスト..."
echo "  以下を実行して動作確認してください:"
echo "    goose session"
echo "  プロンプトで 'hello, tell me a joke' と入力"

echo ""
echo "=== Setup Complete ==="
