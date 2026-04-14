# 22_goose_agent — Goose + Ollama ローカルAIエージェント

## 概要

Block社のオープンソースAIエージェント「Goose」を、Ollamaバックエンドで完全ローカル実行する構成。
21_implement_multi_agentの自作エージェントとは異なり、MCP対応・Recipe自動化・3,000+ツール連携が特徴。

## アーキテクチャ

```
Goose (エージェントフレームワーク)
  ├── Ollama (推論バックエンド = llama.cpp ラッパー)
  │     └── Qwen3.5-9B Q4_K_M / gemma4 等
  ├── MCP Extensions (ツール連携)
  │     ├── ファイルシステム
  │     ├── シェル実行
  │     └── (拡張可能)
  └── Recipes (YAMLワークフロー定義)
        ├── basic_task.yaml
        └── planner_flow.yaml
```

## セットアップ

### 前提条件
- Ollama インストール済み・起動中
- **tools対応モデル**が必要（`ollama show <model>` で Capabilities に `tools` があること）
  - `qwen3.5:9b` — tools対応
  - `qwen3.5-home` — カスタムModelfileのためtools非対応（Gooseでは使用不可）

### 1. Goose インストール

**Windows**: GitHub Releases からダウンロード
- `goose-x86_64-pc-windows-msvc.exe` → `C:\Users\<username>\.goose\goose.exe` に配置
- PATHに `C:\Users\<username>\.goose` を追加

### 2. Goose 設定

設定ファイル: `%APPDATA%\Block\goose\config\config.yaml`
```yaml
GOOSE_PROVIDER: ollama
GOOSE_MODEL: qwen3.5:9b
```

### 3. 使い方

```bash
# 直接実行（--no-profile + --with-builtin developer が速度の鍵）
goose run --provider ollama --model "qwen3.5:9b" \
  --text "タスクの説明" --no-session --quiet \
  --no-profile --with-builtin developer

# Recipe経由（basic_task）
bash run.sh "Create a hello.py script"

# Recipe経由（planner_flow: Plan→Generate→Evaluate）
bash run.sh --recipe planner "Create a Python script with docstring"

# インタラクティブ（--no-profile + developer のみ）
goose session --no-profile --with-builtin developer
```

### 速度に関する重要事項

config.yamlのextensionは `enabled: false` にしてもGooseが全件ロードするため、
**必ず `--no-profile --with-builtin developer` を指定すること。**

| 構成 | 応答時間 |
|------|---------|
| デフォルト（全extension） | 83-136s |
| `--no-profile --with-builtin developer` | **26s** |
| `--no-profile`（extensionなし） | **3s** |

## ハードウェア別設定

| 環境 | GPU | 推奨モデル | Ollama設定 |
|------|-----|-----------|-----------|
| 家PC | VRAM 12GB | qwen3.5-home (9B Q4) | デフォルト |
| 会社PC | VRAM 2GB / RAM 128GB | qwen3.5 (CPU推論) | `OLLAMA_NUM_GPU=0` |

## 21_multi_agent との比較

| 観点 | 21 (自作) | 22 (Goose) |
|------|----------|------------|
| エージェントループ | 自作 (agent.py) | Goose内蔵 |
| ツール | 6種 (自作) | MCP経由で拡張可 |
| ロール分離 | Planner/Generator/Evaluator | Recipe で再現 |
| 安全機構 | CircuitBreaker/Escalation | Goose内蔵 + カスタム可 |
| カスタマイズ | 完全制御 | Recipe/Extension |
