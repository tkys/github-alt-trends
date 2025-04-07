# GitHub代替トレンドサイト構築計画

## 1. 目的

GitHubトレンドにおけるAI/LLM以外の「急成長中」かつ「個人/小規模チーム開発」のリポジトリを発掘・紹介する静的サイトを構築する。

## 2. アーキテクチャ

GitHub ActionsでPythonスクリプトを定期実行し、GitHub APIからデータを取得・フィルタリング。結果をJinja2でHTML化し、`docs/`ディレクトリに出力。GitHub Pagesで`docs/`ディレクトリをホスティング。AI/LLM判定のために外部LLM APIと連携する。

```mermaid
graph TD
    subgraph GitHub Actions Workflow (Scheduled/Manual Trigger)
        A[Setup Python & uv] --> B(Install Dependencies);
        B --> C(Run Python Script);
        C --> D[Generate Static Files (HTML/CSS) in /docs];
        D --> E[Commit & Push /docs to Repository];
    end

    subgraph Python Script (run by Actions)
        F[Fetch Data from GitHub API] --> G(Filter Repositories - Stage 1: Keywords);
        G --> G2{Keyword Match?};
        G2 -- Yes --> X[Exclude];
        G2 -- No --> H(Filter Repositories - Stage 2: LLM判定);
        H --> H2{LLM says AI/LLM?};
        H2 -- Yes --> X;
        H2 -- No --> I[Prepare Data];
        I --> J[Render HTML using Jinja2];
        J --> D;
    end

    subgraph External Service
        K[LLM API]
        H --> K;
    end

    subgraph GitHub Repository
        L[Source Code (Python Script, Templates, .github/workflows/*.yml)]
        M[Generated Static Files (/docs)]
        E --> M;
    end

    subgraph GitHub Pages
        N[Serve Static Files from /docs]
        M --> N;
    end

    O[User] --> N;
```

## 3. 技術スタック

*   **コア技術:** Python 3
*   **仮想環境/パッケージ管理:** uv
*   **データ収集:** `requests`
*   **テンプレートエンジン:** `Jinja2`
*   **LLM連携:** 外部LLM APIクライアントライブラリ (例: `openai`)
*   **CI/CD:** GitHub Actions
*   **ホスティング:** GitHub Pages

## 4. フィルタリング基準

*   **急成長中:** 直近7日間でのStar獲得数が **50** 以上。
*   **個人/小規模開発:** コントリビューター数が **3名** 以下。
*   **AI/LLM関連除外 (二段階):**
    1.  **一次 (キーワード):** リポジトリの `topics` または `description` に、定義済み除外キーワードリスト（例: `["ai", "llm", "artificial-intelligence", "deep-learning", "machine-learning", "neural-network", "chatbot", "language-model", "nlp", "computer-vision"]`、調整可能）のいずれかが含まれて **いない** こと。
    2.  **二次 (LLM):** 一次フィルタリングを通過したリポジトリについて、LLM APIに判定を依頼し、「AI/LLM関連ではない」と判定されること。（二次判定の対象は、コストと効果を見ながら調整。初期は一次通過したもの全てにかけるか、特定の条件のものに絞るか検討）

## 5. 開発ステップ

1.  **プロジェクトセットアップ:**
    *   作業ディレクトリ `/home/tkys/playground/` 配下に `github_alt_trends` ディレクトリを作成。
    *   `cd github_alt_trends`
    *   `uv init` で仮想環境を初期化。
    *   `uv pip install requests Jinja2 openai` (または使用するLLMライブラリ) で依存関係をインストール。
2.  **データ収集・静的ファイル生成スクリプト開発:**
    *   Pythonスクリプト (`main.py` など) を作成。
    *   GitHub APIからリポジトリ情報を取得するロジックを実装。
    *   上記フィルタリング基準（急成長、個人開発、AI/LLM除外の二段階）を実装。
    *   Jinja2テンプレート (`templates/index.html.j2` など) を作成。
    *   フィルタリング後のデータをテンプレートに渡し、HTMLファイル (`docs/index.html`) を生成するロジックを実装。CSSファイル (`docs/style.css`) も必要に応じて作成。
3.  **LLM API連携実装:**
    *   選択したLLM API (例: OpenAI) のクライアントライブラリを使用してAPI呼び出しを行う関数を実装。
    *   リポジトリ情報（説明文、トピックなど）を基に、LLMにAI/LLM関連かどうかを判定させるプロンプトを作成。
    *   APIキーを環境変数または設定ファイルから読み込むように実装（GitHub ActionsではSecretsを使用）。
4.  **GitHub Actions ワークフロー設定:**
    *   `.github/workflows/update_trends.yml` を作成。
    *   スケジュール実行（例: 毎日）または手動実行トリガーを設定。
    *   Python環境セットアップ、依存関係インストール (`uv pip install -r requirements.txt` など）、Pythonスクリプト実行、生成された `docs/` ディレクトリのコミット＆プッシュを行うジョブを定義。
    *   LLM APIキーをGitHubリポジトリのSecretsに登録し、ワークフロー内で環境変数として読み込むように設定。
5.  **GitHub Pages 設定:**
    *   GitHubリポジトリを作成または使用。
    *   リポジトリの Settings > Pages で、Sourceを "Deploy from a branch"、Branchを `main` (またはデフォルト)、Folderを `/docs` に設定。
6.  **テストと改善:**
    *   ローカルでPythonスクリプトを実行し、`docs/` 内のファイルが正しく生成されるか確認。
    *   GitHub Actionsを手動実行し、ワークフローが成功するか、`docs/` が更新されるか確認。
    *   公開されたGitHub PagesのURLで表示を確認。
    *   フィルタリング結果を見て、基準（Star数、コントリビューター数、除外キーワード、LLMプロンプト、二次判定対象）を調整。

## 6. 注意事項・課題

*   **GitHub APIレート制限:** 頻繁な実行や大量データ取得は制限に注意。効率的なAPIコールとキャッシュ（必要なら）を検討。
*   **LLM APIコスト:** 二次フィルタリングでのAPI呼び出し回数とコストを監視。必要に応じて二次判定の対象を絞る。
*   **LLM判定精度:** プロンプトの調整や、場合によってはLLMモデルの変更が必要になる可能性。
*   **フィルタリング基準の妥当性:** 運用しながらユーザーの反応を見て、基準を継続的に見直す必要あり。
