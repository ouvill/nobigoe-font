# のびごえ明朝 (Nobigoe Mincho)

Noto Serif JPをベースに、漫画向けの伸長記号と感嘆符・疑問符合字を追加するフォント生成プロジェクトです。

生成されるフォント名は `Nobigoe Mincho Regular`（日本語ファミリー名: `のびごえ明朝`）、既定の出力先は `dist/NobigoeMincho-Regular.otf` です。現在はRegularウェイトのみを生成します。

## 機能

### 連続する伸長記号

次の文字を2文字以上続けると、OpenTypeの `calt`（Contextual Alternates）で始端・中間・終端の字形へ置換します。

| 文字 | Unicode | 動作 |
|---|---:|---|
| `ー` | U+30FC | 長音記号を連結 |
| `―` | U+2015 | HORIZONTAL BARを連結 |
| `〜` | U+301C | 波線を連結 |
| `～` | U+FF5E | U+301Cと同じ波線字形を使用 |
| `〰` | U+3030 | Manga1方式のWAVY DASHを連結 |

横組と縦組の両方に対応しています。`〜`と`～`は1文字あたり3半波で、始端・終端には線幅テーパーと0.15半波分の追加位相を持たせています。追加位相の補正は字形中央で行うため、細くなる端部の波長と曲率は通常部分と同じです。

連続する `ー` は、元字形の30%位置と70%位置で中心線を測り、中央を固定したアフィンシアーで右上がりの傾斜だけを打ち消してから始端・中間・終端へ分割します。端の筆形状は残しつつ、中央の直線と両端が同じ軸に見えるようにしています。単独の `ー` は元字形のままです。

`〰`はAdobe-Manga1のGSUB構造に合わせ、中央線から始まって中央線へ戻る1文字4半波の反復可能な中間字形を使用します。振幅、基準線、49 unitsの線幅、山頂の曲率は`〜`と揃えています。単独字形は両端に、連続時は始端と終端に、1/6文字幅のテーパーと0.15半波分の追加位相を持たせています。

### Manga1方式の濁点・半濁点付き仮名

Adobe-Manga1-0が規定する濁点77列と半濁点114列の計191列を、OpenTypeの `ccmp` で1グリフへ置換します。入力には結合濁点（U+3099）または結合半濁点（U+309A）を使用します。

```text
あ゙ ぁ゙ な゙ ん゙ ア゙ ン゙
か゚ あ゚ さ゚ な゚ ま゚ セ゚ ツ゚ ㇷ゚
```

Noto Serif JPに一体字形がある24列は既存輪郭を使用し、残る167列は基字と結合記号の輪郭を一体化します。通常の基字では元のGPOS配置を保ち、小書き仮名では既存の `ㇷ゚` のバランスに合わせて記号を約9割へ縮小し、横組・縦組それぞれで基字へ近づけます。Manga1が縦組字形を規定する53列には、縦組基字を使用した専用字形を生成します。

元フォントにない `𛄲`（U+1B132、Hiragana Letter Small Ko）と `𛅕`（U+1B155、Katakana Letter Small Ko）は、Noto Serif JPの `こ` と `コ`を既存の小書き仮名に合わせて縮小・配置した横組・縦組字形を追加します。Manga1の半濁点付きルビ14字形はまだ含みません。

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

2記号の合字は、しっぽり明朝Regularに収録されている `‼`（U+203C）、`⁇`（U+2047）、`⁈`（U+2048）、`⁉`（U+2049）の輪郭をそのまま流用します。3記号以上は、これら既存合字から感嘆符・疑問符の構成輪郭を抽出し、1文字セルへ再配置して生成します。横組・縦組とも記号はセル内で横並びになります。半角ASCIIの `!` と `?` は合字化しません。

この機能は[Adobe-Manga1-0](https://github.com/adobe-type-tools/Adobe-Manga1)の合字シーケンス集合とGSUB規則を参考にしています。Adobe-Manga1のCIDコレクション全体を実装するものではなく、斜体・異体字CIDも含みません。

## 使用フォント

| 用途 | フォント | バージョン |
|---|---|---:|
| 本文、長音、ダッシュ、波線 | [Noto Serif JP Regular](https://github.com/notofonts/noto-cjk) | 2.003 |
| Manga1感嘆符・疑問符合字の記号輪郭 | [Shippori Mincho OTF Regular（しっぽり明朝）](https://fontdasu.com/shippori-mincho/) | 3.300 |

取得元、バージョン、SHA-256、著作権表示は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) に記載しています。

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

引数を省略すると、固定コミットからNoto Serif JP Regularを、FONTDASU公式配布ページからしっぽり明朝OTF版のアーカイブを一時ディレクトリへダウンロードして生成します。両方のSHA-256を検証し、想定した配布物と異なる場合は停止します。元フォントのバイナリはリポジトリへ保存しません。

```sh
.venv/bin/python build_font.py
```

出力:

```text
dist/NobigoeMincho-Regular.otf
```

### ローカルの元フォントを使用

```sh
.venv/bin/python build_font.py \
  --source /path/to/NotoSerifJP-Regular.otf \
  --punctuation-source /path/to/ShipporiMincho-OTF-Regular.otf \
  --output dist/NobigoeMincho-Regular.otf
```

`--source` または `--punctuation-source` の片方だけを指定した場合、指定しなかったフォントだけを自動取得します。Noto Serif CJKのTTCを入力する場合は `--face` でフェイス番号を指定できます。

しっぽり明朝はOTF版とTTF版のどちらも `--punctuation-source` に指定できます。本プロジェクトの生成先はOpenType/CFFなので、同じ3次ベジェ曲線を保持できるOTF版を推奨し、既定の自動取得でもOTF版を使用します。TTF版ではTrueTypeの2次ベジェ曲線をCFFの3次ベジェ曲線へ変換します。

### 濁点・半濁点の位置を調整

Manga1方式の全191列は、字種と記号ごとに次の4ファイルへ分割しています。各ファイルは独立して編集できるため、複数人または複数エージェントで並列に位置調整できます。

```text
mark_positions/hiragana_dakuten.json
mark_positions/hiragana_handakuten.json
mark_positions/katakana_dakuten.json
mark_positions/katakana_handakuten.json
```

各字の `horizontal` と `vertical` は `[scale, x, y]` です。`scale` は結合記号の等方倍率、`x` と `y` は拡大後の平行移動量で、正の値は右・上へ移動します。`build_font.py` は4ファイルの記号種、キー集合、配列長、正の倍率を検証し、191列の不足や重複があれば生成を停止します。生成する167列には横組・縦組それぞれの専用字形を作成します。

```json
"30A1": {
  "horizontal": [0.8, 955, -57],
  "vertical": [0.8, 1036, 171]
}
```

Version 1.015の配置値は、[源暎こぶり明朝](https://okoneya.jp/font/genei-koburimin.html)の一体型濁点・半濁点字形を比較基準にしています。同フォントの1024 units/emの輪郭寸法と基字からの相対位置を1000 units/emへ正規化し、Nobigoe Minchoの各基字へ移植しました。源暎こぶり明朝のフォントデータや輪郭自体は取り込んでいません。

Noto Serif JPに既存一体字形がある24列は元の輪郭と縦組字形を優先します。該当列にも完全な191キー集合を検証するための設定値がありますが、生成輪郭には適用されません。U+31F7 `ㇷ` + U+309Aもこの24列に含まれます。

## 紹介サイト

`site/`に静的な紹介ページと文字テスターがあります。リポジトリ直下でHTTPサーバーを起動し、`http://localhost:8000/site/`を開いてください。

```sh
python3 -m http.server 8000
```

配信用Webfontは`site/assets/NobigoeMincho-Regular.woff2`です。生成フォントを更新した場合は、次のコマンドでWebfontも更新します。

```sh
.venv/bin/pyftsubset dist/NobigoeMincho-Regular.otf \
  --output-file=site/assets/NobigoeMincho-Regular.woff2 \
  --flavor=woff2 \
  --glyphs='*' \
  --layout-features='*' \
  --name-IDs='*' \
  --name-languages='*' \
  --notdef-glyph \
  --notdef-outline \
  --recommended-glyphs
```

## OpenType機能

| feature | 用途 |
|---|---|
| `ccmp` | 全角感嘆符・疑問符合字と濁点・半濁点付き仮名 |
| `calt` | 連続する長音・ダッシュ・波線の始端／中間／終端置換 |
| `vert` / `vrt2` | 縦組用の伸長記号と濁点・半濁点付き仮名字形 |

一般的なシェーピングエンジンでは `ccmp` と `calt` は既定で有効です。アプリケーション側で `calt` を無効にすると、伸長記号の自動連結は行われません。

## ライセンス

生成フォントに取り込まれるNoto Serif JPとしっぽり明朝は、どちらもSIL Open Font License 1.1で提供されています。本プロジェクトのフォント関連ファイルと生成フォントも [`OFL.txt`](OFL.txt) の条件に従います。

第三者フォントの著作権表示と改変内容は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。生成フォントのファミリー名は元フォントと区別し、`Noto`の名称を派生フォント名に残さない `Nobigoe Mincho`（のびごえ明朝）に変更しています。

本プロジェクトはAdobe、Google、Noto Project、またはShippori Mincho Projectによる公式配布物ではありません。`Noto`はGoogle LLCの商標です。各名称は出典と互換性を明示する目的でのみ使用しています。
