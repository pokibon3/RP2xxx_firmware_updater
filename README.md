# RP2040 / RP2350 Firmware Updater

RP2040 / RP2350 基板にファームウェア (`.uf2` / `.bin`) を書き込むツールです。
2 つの版があり、仕組みはどちらも同じです。

| 版 | 起動方法 | 特徴 |
|---|---|---|
| **デスクトップアプリ版**（`app/`、おすすめ） | Python + tkinter | ドライブを自動検出。選択画面・許可ダイアログなしでボタン 1 つで書き込み |
| ブラウザ版（`index.html`） | Chrome / Edge で開くだけ | インストール不要。初回にドライブを選ぶ必要あり |

共通の機能:

- 動作中の基板を **自動で書き込みモード (BOOTSEL) に切り替え** て書き込み
  - pico-sdk の Reset インターフェースがあれば USB リセット、無ければ 1200bps タッチ
- 書き込みモードのドライブ (`RPI-RP2` / `RP2350`) へ UF2 をコピーするので、Windows でも Zadig 等のドライバ導入は不要
- `.bin` は書き込み先チップに合わせて UF2 に自動変換
- チップ違いのファームウェア (RP2040 用を RP2350 に、など) は書き込み前に検出して中止

## デスクトップアプリ版 (`app/`)

### セットアップ

Python 3.10 以上と tkinter が必要です（macOS の Homebrew 版 Python は `brew install python-tk@3.14` などで tkinter を追加）。

```sh
cd app
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip install -r requirements.txt
.venv/bin/python rp2updater.py                 # Windows: .venv\Scripts\python rp2updater.py
```

| パッケージ | 用途 |
|---|---|
| `pyserial` | デバイス一覧、1200bps タッチ |
| `pyusb` + `libusb-package` | USB リセット（libusb 同梱。無くても 1200bps で切り替え可） |
| `tkinterdnd2` | ドラッグ＆ドロップ（任意） |

### 使い方

1. **デバイス** — USB で挿した基板が自動で一覧に出ます（複数あるときだけ選ぶ）
2. **ファームウェア** — 「ファームウェアを選択…」「フォルダから…」またはドラッグ＆ドロップ。
   一覧は新しい順で、最新のファイルが自動で選ばれます
3. **「書き込み開始」** — 書き込みモードへの切り替え → ドライブ検出 → コピー → 再起動確認まで自動

- 書き込みモードのドライブが既に出ていれば、切り替えずにそのまま書き込みます
- デバイスが無いときは、BOOTSEL ボタンを押しながら USB を挿すのを待ちます（最大 3 分、「中止」で取り消し）
- ファイルは書き込み直前に読み直すので、ビルドし直したら「書き込み開始」を押すだけで最新版が書き込まれます
- 前回のファイル一覧と選んだデバイスは `~/.rp2xxx_updater.json` に保存されます

### ファイル構成

```
app/rp2updater.py   画面 (tkinter)
app/device.py       デバイス一覧・書き込みモードへの切り替え
app/drive.py        書き込みモードのドライブ検出・コピー
app/uf2.py          UF2 / BIN の解析・チップ適合チェック・変換
```

## ブラウザ版 (`index.html`)

インストール不要で、`index.html` を Chrome / Edge で開くだけで使えます。
書き込み先ドライブ (`RPI-RP2` / `RP2350`) を記憶し、2 回目以降はボタン 1 つで書き込めます。

### 動作環境

| 項目 | 内容 |
|---|---|
| ブラウザ | Chrome / Edge（File System Access API・WebUSB・Web Serial を使用。Firefox / Safari は非対応） |
| OS | Windows / macOS |
| 基板 | RP2040 / RP2350 搭載基板（Raspberry Pi Pico / Pico 2、Waveshare RP2040-Zero / RP2350-Zero、WeAct RP2350 Core など） |

### 使い方

#### 0. ページを開く

`index.html` を Chrome / Edge で開きます（ダブルクリック、またはブラウザへドラッグ）。

#### 1. デバイスに接続（省略可）

書き込みモードへ自動で切り替えたい場合だけ行います。

1. 基板を USB で PC に挿す（普通に起動した状態でよい）
2. **「デバイスに接続」** を押し、一覧から基板を選ぶ
3. Web Serial の許可を求められたら、同じ基板のシリアルポートを選ぶ

切り替え方法は自動で選ばれます。

| 基板のファームウェア | 切り替え方法 |
|---|---|
| pico-sdk の Reset インターフェース付き | USB リセット要求 |
| USB シリアル (CDC) 付き（pico-sdk の `stdio_usb`、arduino-pico など） | 1200bps タッチ |
| どちらも無い（USB を使わないファームなど） | 自動切り替え不可 → 手動で BOOTSEL |

> **手動で書き込みモードにする場合:** BOOTSEL ボタンを押しながら USB を挿すと、
> `RPI-RP2`（RP2040）または `RP2350`（RP2350）というドライブが現れます。この場合、手順 1 は不要です。

一度接続した基板は、次回ページを開いたときに自動で再接続されます。

#### 2. ファームウェアを選ぶ

次のいずれかで `.uf2` / `.bin` を選びます。

- **「ファームウェアを選択…」** ボタン
- ファイルを枠内にドラッグ＆ドロップ
- **「フォルダから選ぶ」** でビルド出力フォルダを指定 → 中の `.uf2` / `.bin` を新しい順に一覧表示し、最新のものを自動選択（クリックで切り替え）

選ぶと、形式・対象チップ・書き込み範囲が表示されます。

#### 3. 書き込む

1. **「書き込み開始」** を押す
2. 初回のみ、書き込み先ドライブを選ぶダイアログが出るので `RPI-RP2` / `RP2350` を選ぶ
   - **Mac で一覧に出ない場合:** ダイアログで `⌘ + Shift + G` を押し、
     `/Volumes/RPI-RP2`（RP2350 は `/Volumes/RP2350`）と入力して「開く」
   - 「このサイトにファイルの編集を許可しますか？」には **「ファイルを編集」** を選ぶ
3. 途中でボタンの表示が「ドライブへの書き込みを許可」などに変わったら、もう一度押す
   （ブラウザの仕様上、許可ダイアログはクリック直後にしか出せないため）
4. 基板が再起動してドライブが消えると **「完了」** と表示され、新しいファームウェアで起動します

ドライブは記憶されるので、2 回目からは「書き込み開始」を押すだけです。
`RPI-RP2` と `RP2350` は別々に記憶されます（それぞれ初回だけ選択）。
記憶したドライブが見つからないときは、待ちながら「書き込み先ドライブを選択」ボタンが出ます。
記憶を消したいときは **「選び直す」** を押します。

## サンプルファームウェア

`samples/` に動作確認用の Lチカ (LED 点滅) ファームウェアがあります。ビルド済み `.uf2` 同梱なので、そのまま書き込めます。
どれも USB シリアルに `blink N: ...` を出力し、1200bps タッチで書き込みモードに入れます。

| フォルダ | 基板 | LED |
|---|---|---|
| `samples/rp2040-zero-blink` | Waveshare RP2040-Zero | GPIO16 の WS2812（赤→緑→青） |
| `samples/rp2350-zero-blink` | Waveshare RP2350-Zero | GPIO16 の WS2812（赤→緑→青） |
| `samples/weact-rp2350-blink` | WeAct Studio RP2350A / RP2350B Core | GPIO25 |

> **注意:** 基板に合わないサンプルを書き込んでも、ファームは動きますが LED は光りません。
> 例えば RP2350-Zero には GPIO25 の LED が無いので、`weact-rp2350-blink` では点滅しません。
> Raspberry Pi Pico 2 W の LED は無線チップ側にあるため、GPIO からは直接点灯できません。

### サンプルのビルド

pico-sdk (2.x) と、newlib 付きの `arm-none-eabi-gcc` が必要です。

```sh
cd samples/rp2350-zero-blink
PICO_SDK_PATH=/path/to/pico-sdk \
PICO_TOOLCHAIN_PATH=/path/to/arm-none-eabi-gcc/bin \
./build.sh
```

`build.sh` は picotool を使わずにビルドし、`tools/bin2uf2.py` で `.bin` を `.uf2` に変換します。
環境変数を省略すると、PlatformIO 同梱の pico-sdk / toolchain（`~/.platformio/packages/...`）を使います。

> Homebrew の `arm-none-eabi-gcc` には newlib が無いためリンクできません。
> Arm GNU Toolchain や xPack 版などを使ってください。

### `tools/bin2uf2.py`

`.bin`（フラッシュ先頭 `0x10000000` からの生イメージ）を UF2 に変換します。

```sh
python3 tools/bin2uf2.py input.bin output.uf2 --family rp2350-arm-s   # rp2040 | rp2350-arm-s | rp2350-riscv
```

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| 「このブラウザはドライブへの書き込みに対応していません」 | （ブラウザ版）Chrome または Edge で開く |
| Mac でドライブ選択画面に `RPI-RP2` / `RP2350` が出ない | （ブラウザ版）`⌘ + Shift + G` でパスを入力。またはデスクトップアプリ版を使う |
| デバイスの一覧に基板が出ない | USB ケーブルが充電専用でないか確認。出なければ BOOTSEL ボタンで手動切り替え |
| 「シリアルポートを開けません（他のアプリが使用中？）」 | シリアルモニタ（Arduino IDE、screen など）を閉じる |
| 「自動で書き込みモードに切り替えられません」 | BOOTSEL ボタンを押しながら USB を挿し直し、「書き込み開始」 |
| 「このファームウェア (...) は RP2350 向けではありません」 | 基板のチップに合った UF2 を選ぶ（RP2040 用と RP2350 用は互換性なし） |
| 「フラッシュ範囲外のアドレスを含みます」 | RAM 実行用の UF2 (`no_flash`) は非対応。フラッシュ用にビルドする |
| 書き込み完了後に LED が光らない | まず USB シリアルに出力が出ているか確認。出ていればファームは動いているので、LED のピン設定が基板と合っているか確認 |

## ファイル構成

```
app/              デスクトップアプリ版 (Python + tkinter)
index.html        ブラウザ版（単一 HTML）
samples/          サンプルファームウェア（ソース・ビルドスクリプト・ビルド済み UF2）
tools/bin2uf2.py  BIN → UF2 変換スクリプト
```
