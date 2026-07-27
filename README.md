# Noto Serif JP Choon

Noto Serif JPをベースに、漫画向けの伸長記号と感嘆符・疑問符合字を追加するフォント生成プロジェクトです。

生成されるフォント名は `Noto Serif JP Choon Regular`、既定の出力先は `dist/NotoSerifJPChoon-Regular.otf` です。現在はRegularウェイトのみを生成します。

## 機能

### 連続する伸長記号

次の文字を2文字以上続けると、OpenTypeの `calt`（Contextual Alternates）で始端・中間・終端の字形へ置換します。

| 文字 | Unicode | 動作 |
|---|---:|---|
| `ー` | U+30FC | 長音記号を連結 |
| `―` | U+2015 | HORIZONTAL BARを連結 |
| `〜` | U+301C | 波線を連結 |
| `～` | U+FF5E | U+301Cと同じ波線字形を使用 |

横組と縦組の両方に対応しています。波線は1文字あたり3半波で、始端・終端には線幅テーパーと0.15半波分の追加位相を持たせています。追加位相の補正は字形中央で行うため、細くなる端部の波長と曲率は通常部分と同じです。

### Manga1方式の感嘆符・疑問符合字

全角の `！`（U+FF01）と `？`（U+FF1F）による次の16通りを、OpenTypeの `ccmp` で全角1文字幅の合字へ置換します。

```text
？？   ？？？
！！   ！！！   ！！！！   ！！！！！
？！   ！？
？？！ ？！？   ！？？
！！？ ！？！   ？！！
！！？？ ？？！！
```

合字内の `!` と `?` の輪郭には、しっぽり明朝Regularのプロポーショナル記号を使用しています。横組・縦組とも記号は1文字セル内で横並びになります。半角ASCIIの `!` と `?` は合字化しません。

この機能は[Adobe-Manga1-0](https://github.com/adobe-type-tools/Adobe-Manga1)の標準直立セリフ合字とGSUB規則を参考にしています。Adobe-Manga1のCIDコレクション全体を実装するものではなく、斜体・異体字CIDも含みません。

## 使用フォント

| 用途 | フォント | バージョン |
|---|---|---:|
| 本文、長音、ダッシュ、波線 | [Noto Serif JP Regular](https://github.com/notofonts/noto-cjk) | 2.003 |
| Manga1感嘆符・疑問符合字の記号輪郭 | [Shippori Mincho Regular（しっぽり明朝）](https://github.com/fontdasu/ShipporiMincho) | 3.110 |

取得元、固定コミット、SHA-256、著作権表示は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) に記載しています。

## ビルド

### 必要環境

- Python 3
- `fonttools`
- `skia-pathops`
- OpenType SanitizerとHarfBuzz（検証する場合）

Python依存関係をインストールします。

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 自動取得して生成

引数を省略すると、固定コミットからNoto Serif JP Regularとしっぽり明朝Regularを一時ディレクトリへダウンロードして生成します。元フォントのバイナリはリポジトリへ保存しません。

```sh
.venv/bin/python build_font.py
```

出力:

```text
dist/NotoSerifJPChoon-Regular.otf
```

### ローカルの元フォントを使用

```sh
.venv/bin/python build_font.py \
  --source /path/to/NotoSerifJP-Regular.otf \
  --punctuation-source /path/to/ShipporiMincho-Regular.ttf \
  --output dist/NotoSerifJPChoon-Regular.otf
```

`--source` または `--punctuation-source` の片方だけを指定した場合、指定しなかったフォントだけを自動取得します。Noto Serif CJKのTTCを入力する場合は `--face` でフェイス番号を指定できます。

## OpenType機能

| feature | 用途 |
|---|---|
| `ccmp` | 全角感嘆符・疑問符のManga1方式合字 |
| `calt` | 連続する長音・ダッシュ・波線の始端／中間／終端置換 |
| `vert` / `vrt2` | 縦組用の伸長記号字形 |

一般的なシェーピングエンジンでは `ccmp` と `calt` は既定で有効です。アプリケーション側で `calt` を無効にすると、伸長記号の自動連結は行われません。

## ライセンス

生成フォントに取り込まれるNoto Serif JPとしっぽり明朝は、どちらもSIL Open Font License 1.1で提供されています。本プロジェクトのフォント関連ファイルと生成フォントも [`OFL.txt`](OFL.txt) の条件に従います。

第三者フォントの著作権表示と改変内容は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。生成フォントのファミリー名は元フォントと区別するため `Noto Serif JP Choon` に変更しています。

本プロジェクトはAdobe、Google、Noto Project、またはShippori Mincho Projectによる公式配布物ではありません。`Noto`はGoogle LLCの商標です。各名称は出典と互換性を明示する目的でのみ使用しています。
