# Goose + Ollama セットアップガイド（会社PC向け）

家PCで構築済みの環境を会社PCに再現する手順。

## 前提

- 会社PC: VRAM 2GB / RAM 128GB → CPU推論で動作
- Ollama インストール済み（未導入なら先にインストール）

---

## Step 1: Goose バイナリ配置

家PCから `goose.exe` をコピーし、以下に配置:

```
C:\Users\<ユーザー名>\.goose\goose.exe
```

---

## Step 2: PATH に追加

PowerShellを通常権限で実行:

```powershell
[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path', 'User') + ';C:\Users\<ユーザー名>\.goose', 'User')
```

確認（新しいターミナルを開いて）:
```bash
goose --version
# → 1.30.0 が出ればOK
```

---

## Step 3: Goose プロバイダー設定

```bash
goose configure
```

対話メニューで:
1. **Configure Providers** を選択
2. **Ollama** を選択
3. モデル名: **qwen3.5:9b**

---

## Step 4: 安全設定（重要）

### 4a. config.yaml に安全パラメータ追加

ファイル: `%APPDATA%\Block\goose\config\config.yaml`

`goose configure` で作成されたファイルの先頭付近に以下を追加:
```yaml
GOOSE_MODE: smart_approve
GOOSE_MAX_TURNS: 50
```

| 設定 | 意味 |
|------|------|
| `smart_approve` | 低リスク操作は自動、ファイル削除やシェル実行は確認を求める |
| `MAX_TURNS: 50` | エージェント暴走防止（デフォルト1000は危険） |

### 4b. .goosehints（破壊操作のソフトガードレール）

ファイル作成: `C:\Users\<ユーザー名>\.config\goose\.goosehints`

```powershell
mkdir "$HOME\.config\goose" -Force
```

内容:
```
## Safety Rules

- NEVER delete any file without confirming the exact file path with the user first.
- NEVER run rm, del, rmdir, or any deletion command without asking the user to confirm.
- NEVER use rm -rf or recursive deletion under any circumstances.
- Before any bulk file operation, list the files and ask for explicit confirmation.
- If the user says "delete this", ask which specific file and confirm before proceeding.
- Do not overwrite existing files without confirming with the user.
- Do not run commands that modify system settings or environment variables.
```

### 4c. .gooseignore（ファイルアクセス制限）

プロジェクトルートに配置:
```
.env
*.pem
*.key
credentials/
secrets/
```

---

## Step 5: Ollama モデル準備

```bash
ollama pull qwen3.5:9b
```

### 会社PC特有: CPU推論を強制

```powershell
[Environment]::SetEnvironmentVariable('OLLAMA_NUM_GPU', '0', 'User')
```

> RAM 128GBあるので9Bモデルは問題なし。GPU推論より遅いが動作する。

---

## Step 6: 動作確認

```bash
# 1. Ollamaが起動していることを確認
ollama list

# 2. Goose テスト（高速版: --no-profile必須）
goose run --text "respond with OK" --no-session --quiet --no-profile --with-builtin developer
# → "OK" が出ればOK

# 3. 対話モード（高速版）
goose session --no-profile --with-builtin developer
```

---

## 速度に関する注意

config.yamlのextensionは無効化してもGooseが全件ロードするため異常に遅い。
**必ず `--no-profile --with-builtin developer` を指定すること。**

| 構成 | 応答時間（家PC） |
|------|-----------------|
| デフォルト（全extension） | 83-136s |
| `--no-profile --with-builtin developer` | **26s** |
| `--no-profile`（extensionなし） | **3s** |

> 会社PCはCPU推論のためさらに遅くなる。

---

## まとめ：配置場所一覧

| 項目 | パス |
|------|------|
| goose.exe | `C:\Users\<ユーザー名>\.goose\goose.exe` |
| PATH追加 | `C:\Users\<ユーザー名>\.goose` |
| config.yaml | `%APPDATA%\Block\goose\config\config.yaml` |
| .goosehints | `C:\Users\<ユーザー名>\.config\goose\.goosehints` |
| .gooseignore | プロジェクトルートに配置 |
| セッションDB | `%APPDATA%\Block\goose\data\sessions\` (自動生成) |
| ログ | `%APPDATA%\Block\goose\data\logs\` (自動生成) |

## 環境変数一覧

| 変数 | 値 | 用途 |
|------|-----|------|
| `OLLAMA_NUM_GPU` | `0` | CPU推論強制（VRAM少ない場合） |

## トラブルシュート

| 症状 | 原因 | 対処 |
|------|------|------|
| `Error: not connected` | プロバイダー未設定 or Ollama未起動 | `goose configure` を実行 |
| ツール呼び出しが失敗 | モデルがtools非対応 | `ollama show qwen3.5:9b` → Capabilities に `tools` があるか確認 |
| 異常に遅い（1分以上） | extension全件ロード | `--no-profile --with-builtin developer` を付ける |
| 応答が極端に遅い | GPU推論試行→OOM | `OLLAMA_NUM_GPU=0` を設定 |
| 確認なしにファイル削除 | GOOSE_MODEがauto | config.yamlで `GOOSE_MODE: smart_approve` に変更 |
| `goose` コマンドが見つからない | PATH未追加 | Step 2 をやり直し（新しいターミナルで確認） |
