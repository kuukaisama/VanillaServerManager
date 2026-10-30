# Vanilla Server Manager

Minecraft Java Edition の公式 Vanilla サーバーを、Windows上から管理するためのデスクトップアプリケーションです。

Python + Tkinter で開発しています。

Minecraftサーバーの起動・停止だけでなく、バックアップ、設定変更、ホワイトリスト管理、複数サーバーの管理などをGUIから行うことを目的としています。

> [!IMPORTANT]
> 本ソフトウェアは Mojang Studios および Microsoft の公式製品ではありません。  
> また、Minecraft公式サーバーJAR、Minecraft本体、ワールドデータ等は本リポジトリに含まれていません。
>
> **NOT AN OFFICIAL MINECRAFT PRODUCT.**  
> **NOT APPROVED BY OR ASSOCIATED WITH MOJANG OR MICROSOFT.**

---

## Version

Current version:

`1.0.0-beta.1`

バージョンは以下の形式で管理しています。

`MAJOR.MINOR.PATCH`

例:

- `1.0.0` 初回公開
- `1.0.1` バグ修正
- `1.1.0` 後方互換性のある機能追加
- `2.0.0` 大きな仕様変更

変更内容については `CHANGELOG.md` を参照してください。

---

## 主な機能

### サーバー管理

- Minecraftサーバーの起動
- Minecraftサーバーの停止
- Minecraftサーバーの再起動
- サーバー状態表示
- 稼働時間表示
- CPU使用率表示
- RAM使用量表示
- オンラインプレイヤー人数表示

サーバー停止時は、通常のプロセス強制終了ではなくMinecraftコンソールへ `stop` コマンドを送信し、安全な終了を行います。

---

### コンソール

Minecraftサーバーの標準出力をアプリ内で確認できます。

また、入力欄からMinecraftサーバーへ直接コマンドを送信できます。

例:

```text
list
say Hello
whitelist list
```

---

## バックアップ

ワールドデータのバックアップをZIP形式で作成できます。

主な機能:

- 手動バックアップ
- 自動バックアップ
- バックアップ一覧表示
- バックアップからの復元

自動バックアップでは、以下の間隔を設定できます。

- 無効
- 30分
- 1時間
- 3時間
- 6時間

サーバー稼働中にバックアップを行う場合は、Minecraftへ保存コマンドを送信してからバックアップ処理を行います。

バックアップ時には、ワールドだけでなく必要なサーバー設定ファイルも保存します。

復元処理では、ZIPファイルや復元先を検証し、サーバーディレクトリ外への意図しない書き込みを防ぐ処理を行っています。

---

## server.properties の管理

GUIからMinecraftサーバーの主な設定を変更できます。

設定可能な項目には、以下のようなものがあります。

- ゲームモード
- 難易度
- MOTD
- 最大プレイヤー人数
- サーバーポート
- PvP
- 飛行許可
- ハードコア
- コマンドブロック
- スポーン保護範囲
- view-distance
- simulation-distance
- online-mode
- white-list
- enforce-whitelist

設定内容によっては、Minecraftサーバーの再起動後に反映されます。

---

## ホワイトリスト管理

GUIからMinecraftサーバーのホワイトリストを管理できます。

- ホワイトリスト一覧表示
- プレイヤー追加
- プレイヤー削除
- ホワイトリスト有効化

友人向けなど、参加者を限定したサーバーでは以下の設定を推奨します。

```properties
online-mode=true
white-list=true
```

---

## 複数サーバープロファイル

複数のMinecraftサーバーを1つのアプリから管理できます。

各プロファイルごとに、以下の情報を分離して管理します。

- サーバー名
- サーバーディレクトリ
- バックアップディレクトリ
- 使用するserver.jar
- Java実行ファイル
- 最小メモリ
- 最大メモリ
- 自動バックアップ間隔

サイドバーから管理するサーバーを切り替えられます。

---

## 新規サーバー作成

新しいMinecraftサーバーをGUIから作成できます。

初期設定ウィザードでは、主に以下を設定できます。

- サーバー名
- サーバー保存先
- バックアップ保存先
- 使用する公式server.jar
- Java
- メモリ割り当て
- 自動バックアップ
- ワールド名
- Seed
- ワールドタイプ
- ゲームモード
- 難易度
- Minecraftサーバーポート
- 最大プレイヤー人数
- MOTD
- ホワイトリスト
- PvP
- view-distance
- simulation-distance

Minecraft公式EULAについては、利用者自身で内容を確認したうえで同意する必要があります。

---

# 動作環境

本アプリケーションはWindows向けに開発しています。

必要なもの:

- Windows
- Python 3
- Tkinter
- Java
- Minecraft Java Edition 公式サーバーJAR

Pythonの追加ライブラリとして以下を使用します。

```text
psutil>=5.9
```

Javaのバージョンは、使用するMinecraft公式サーバーJARが要求するバージョンを使用してください。

開発環境では Eclipse Temurin JDK 25 を使用しています。

---

# インストール

## 1. ソースコードを取得

リポジトリをCloneするか、ソースコードをダウンロードしてください。

例:

```bash
git clone <repository>
cd VanillaServerManager
```

---

## 2. Pythonライブラリをインストール

プロジェクトディレクトリで以下を実行します。

```bash
python -m pip install -r requirements.txt
```

Windows環境によっては、以下でも実行できます。

```bash
py -m pip install -r requirements.txt
```

---

## 3. Javaをインストール

Minecraft公式サーバーを実行できるJavaをインストールしてください。

Javaが使用できるかは、以下で確認できます。

```bash
java -version
```

---

## 4. アプリを起動

```bash
python manager.py
```

または、

```bash
py manager.py
```

を実行します。

---

# 初回起動

初回起動時には免責事項が表示されます。

内容を確認し、同意した場合のみアプリを使用できます。

サーバーがまだ登録されていない場合は、

`サーバーを追加`

からMinecraftサーバーを新規作成または登録してください。

---

# Minecraft公式server.jarについて

Minecraft公式サーバーJARは、このリポジトリには含まれていません。

利用者自身でMinecraft公式サイトからダウンロードしてください。

新規サーバー作成機能で使用するJARは、アプリの案内に従ってユーザーデータ領域の `worldversion` フォルダーへ配置できます。

例:

```text
%LOCALAPPDATA%\VanillaServerManager\worldversion
```

内部JARなど、単体でMinecraftサーバーとして起動できないJARが指定された場合はエラーとして扱います。

---

# ユーザーデータ

アプリ本体とMinecraftサーバーデータは分離されています。

標準のユーザーデータ保存先:

```text
%LOCALAPPDATA%\VanillaServerManager
```

この中に、アプリ設定やサーバープロファイルなどが保存されます。

例:

```text
VanillaServerManager/
├─ profiles.json
├─ settings.json
├─ server/
├─ backups/
└─ worldversion/
```

サーバープロファイルで別の保存先を指定した場合は、その場所にサーバーデータやバックアップが保存されます。

そのため、アプリのソースコードを更新・置き換えても、ユーザーデータを分離したまま管理できます。

---

# 公開物に含まれないもの

本リポジトリでは、以下のデータを公開対象にしていません。

- Minecraft公式server.jar
- Minecraftワールド
- Minecraftサーバーログ
- バックアップファイル
- プレイヤー情報
- ローカル設定
- その他ユーザー固有のMinecraftサーバーデータ

これらは利用者自身の環境で管理してください。

---

# ディレクトリ構成

ソースコードは主に以下のように構成されています。

```text
VanillaServerManager/
├─ manager.py
├─ minecraft_manager/
│  ├─ app.py
│  ├─ server.py
│  ├─ backup.py
│  ├─ config.py
│  ├─ profiles.py
│  ├─ setup.py
│  ├─ validation.py
│  ├─ whitelist.py
│  └─ ui/
├─ tests/
├─ worldversion/
├─ requirements.txt
├─ CHANGELOG.md
└─ .gitignore
```

`manager.py` はアプリケーションのエントリーポイントです。

実際のサーバー管理処理やバックアップ処理、GUI処理などは `minecraft_manager` パッケージ以下へ分割しています。

---

# テスト

回帰テストを用意しています。

v1.0.0-beta.1公開準備時点で、

```text
30 tests passed
```

を確認しています。

テストでは実際のMinecraftワールドを直接使用せず、一時データを利用して主要な処理を確認しています。

---

# セキュリティについて

Minecraftサーバーをインターネットへ公開する場合は、利用者自身でネットワークとサーバーのセキュリティを管理してください。

特に以下を推奨します。

```properties
online-mode=true
white-list=true
```

また、

- Minecraftサーバーを最新版に保つ
- Javaを適切に更新する
- Windows Updateを適用する
- 不要なポートを開放しない
- 必要なプレイヤーのみホワイトリストへ登録する

などの対策を行ってください。

本アプリケーション自体が、Minecraftサーバーやネットワークの安全性を保証するものではありません。

---

# バックアップに関する注意

本アプリケーションにはバックアップ機能がありますが、重要なワールドについては、本アプリケーションが作成するバックアップだけに依存しないことを推奨します。

例えば、

```text
Vanilla Server Managerのバックアップ
+
外付けSSD / NAS / 別PC / クラウド等への追加バックアップ
```

のように、別の保存先にもコピーしてください。

---

# Minecraftとの関係について

Vanilla Server Manager は非公式のMinecraftサーバー管理ツールです。

本プロジェクトは、

- Mojang Studios
- Microsoft

とは関係がなく、両社から承認・保証されたものではありません。

MinecraftおよびMinecraft関連の名称・コンテンツに関する権利は、それぞれの権利者に帰属します。

Minecraftの利用規約およびEULAについては、利用者自身で確認してください。

---

# 免責事項

本ソフトウェアは現状有姿（AS IS）で提供されます。

作者は、本ソフトウェアが常に正常に動作すること、データが失われないこと、または特定の目的に適合することを保証しません。

本ソフトウェアの使用に伴う、

- Minecraftワールドの破損・消失
- 設定ファイルの破損
- バックアップまたは復元の失敗
- サーバー停止
- ネットワーク上の問題
- その他の損害

については、適用法令で認められる範囲で利用者自身の責任で使用してください。

初回起動時にも、アプリ内で免責事項への確認を行います。

---

# ライセンス

本プロジェクトのソースコードは **Apache License 2.0** のもとで公開しています。

Copyright 2026 kuukaisama

本ライセンスの条件に従うことで、ソースコードの利用、改変、再配布、商用利用が可能です。

改変・再配布を行う場合は、Apache License 2.0 の条件に従い、元の著作権表示・ライセンス・該当する帰属表示を保持してください。

詳細については、リポジトリ内の以下のファイルを参照してください。

- `LICENSE`
- `NOTICE`

なお、Apache License 2.0 の対象となるのは、本プロジェクトで作成したソースコードです。

以下は本プロジェクトのライセンス対象には含まれません。

- Minecraft公式サーバーJAR
- Minecraft本体
- Minecraftのワールドデータ
- Minecraftに含まれる画像・音声・その他のコンテンツ
- Mojang Studios / Microsoft が権利を保有するその他のコンテンツ

Vanilla Server Manager は非公式のMinecraftサーバー管理ツールです。

本プロジェクトは Mojang Studios および Microsoft とは関係がなく、両社から承認、保証、後援されたものではありません。

---

# 今後の予定

今後、以下のような機能を検討しています。

- UIの改善
- サーバー監視機能の強化
- バックアップ機能の改善
- 外部アクセスログの分析
- IPアドレスの推定国・ASN表示
- 緊急地震速報を利用したワールド自動保存
- アプリケーション更新機能

これらは今後の開発状況によって変更される可能性があります。

---

# 開発について

このアプリケーションは、Minecraftサーバーをより簡単かつ安全に管理することを目的として開発しています。

不具合や改善案については、GitHub Issues等で管理できる形を今後整備する予定です。

# Author

**kuukaisama**

Vanilla Server Manager の開発・管理を行っています。
