#!/usr/bin/env bash
# ============================================================================
# Embedding モデルを Hugging Face から DL して Ollama に登録するスクリプト
#
# 使い方:
#   bash models/setup_embedding.sh                  # nomic-embed-text（デフォルト）
#   bash models/setup_embedding.sh nomic-embed-text # 英語＋多言語、768次元、軽量
#   bash models/setup_embedding.sh bge-m3           # 日本語に強い、1024次元
#
# 前提: Ollama と Python/pip がインストール済み
# ============================================================================

set -euo pipefail

MODEL_NAME="${1:-nomic-embed-text}"
cd "$(dirname "$0")"

case "$MODEL_NAME" in
  nomic-embed-text)
    REPO="nomic-ai/nomic-embed-text-v1.5-GGUF"
    FILE="nomic-embed-text-v1.5.Q4_K_M.gguf"
    ;;
  bge-m3)
    REPO="ChristianAzinn/bge-m3-gguf"
    FILE="bge-m3.Q4_K_M.gguf"
    ;;
  *)
    echo "不明なモデル: $MODEL_NAME"
    echo "対応: nomic-embed-text / bge-m3"
    exit 1
    ;;
esac

echo "=== Embedding モデルセットアップ: $MODEL_NAME ==="

# 1. Hugging Face CLI
if ! command -v huggingface-cli &>/dev/null; then
  echo "[1/4] huggingface_hub をインストール..."
  pip install -U "huggingface_hub[cli]"
else
  echo "[1/4] huggingface-cli 既にインストール済み"
fi

# 2. GGUF ダウンロード
if [ -f "$FILE" ]; then
  echo "[2/4] $FILE 既にあります（スキップ）"
else
  echo "[2/4] $REPO から $FILE をDL..."
  huggingface-cli download "$REPO" "$FILE" --local-dir .
fi

# 3. Modelfile 生成
MODELFILE="Modelfile.$MODEL_NAME"
echo "[3/4] $MODELFILE を生成..."
cat > "$MODELFILE" <<EOF
FROM ./$FILE
EOF

# 4. Ollama に登録
echo "[4/4] Ollama に $MODEL_NAME を登録..."
ollama create "$MODEL_NAME" -f "$MODELFILE"

echo ""
echo "=== 完了 ==="
echo "確認: ollama list | grep $MODEL_NAME"
echo "config.toml の embedding_model = \"$MODEL_NAME\" を確認してください"
