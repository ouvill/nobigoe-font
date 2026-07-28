# のびごえ明朝 (Nobigoe Mincho)

Noto Serif JPまたは源暎こぶり明朝を和文ベースに、漫画向けの伸長記号、感嘆符・疑問符合字と異体字、濁点・半濁点付き仮名を追加するフォント生成プロジェクトです。Noto版の欧文はLibertinus Serifの字形とメトリクスを使用します。

Noto版は共通ファミリー名`Nobigoe Mincho`（`のびごえ明朝`）の7ウェイト、源暎こぶり明朝版は別ファミリー`Nobigoe Koburi Mincho`（`のびごえこぶり明朝`）のRegularとして配布します。Noto版はOpenType/CFF、源暎こぶり明朝版は元フォントと同じTrueType形式です。

## 配布構成

| ファミリー | ベース | ウェイト | 形式 | 出力 |
|---|---|---|---|---|
| Nobigoe Mincho | Noto Serif JP（和文）+ Libertinus Serif（欧文） | ExtraLight / Light / Regular / Medium / SemiBold / Bold / Black | OpenType/CFF (`.otf`) | `dist/NobigoeMincho-<Weight>.otf` |
| Nobigoe Koburi Mincho | 源暎こぶり明朝 | Regular | TrueType (`.ttf`) | `dist/NobigoeKoburiMincho-Regular.ttf` |

両ファミリーの追加機能とUnicode入力は同じです。Noto版は通常の文書用ウェイトファミリー、源暎こぶり明朝版は小ぶりな仮名と漫画的な組版を活かす独立ファミリーとして扱います。

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

Noto版では、Noto Serif JPに一体字形がある24列は既存輪郭を使用し、残る167列は基字と結合記号の輪郭を一体化します。源暎こぶり明朝版では、同フォントに既存する一体字形を優先します。その他の字形は通常の基字では元のGPOS配置を保ち、小書き仮名では既存の `ㇷ゚` のバランスに合わせて記号を約9割へ縮小し、横組・縦組それぞれで基字へ近づけます。Manga1が縦組字形を規定する53列には、縦組基字を使用した専用字形を生成します。

源暎こぶり明朝が一体字形を持つ濁点74列・半濁点14列の計88列には、同フォントと互換性のある私用領域U+E082–U+E0D9も割り当てています。たとえばU+E082を直接入力しても、`あ` + U+3099と同じ字形になります。OpenTypeの結合処理に対応しないアプリで使用できます。

源暎こぶり明朝と同じく、白ハート `♡`（U+2661）と黒ハート `♥`（U+2665）に結合濁点を続けた2列も一体字形へ置換します。私用領域の基字U+E064・U+E065でも同じ結合が働き、完成字形はそれぞれU+E0DC・U+E0DDで直接入力できます。ハートは各版のベースフォントの輪郭を使用し、濁点の2画を源暎こぶり明朝の配置比率に合わせて個別に配置しています。ハートから差し引く白抜きの半径は、配置後の濁点2画の中心間距離の1/3です。濁点輪郭を16方向へこの半径だけ拡張した範囲を差し引くため、白抜き幅は濁点の大きさと配置に追従し、ハートと濁点が接触しません。

元フォントにない場合、`𛄲`（U+1B132、Hiragana Letter Small Ko）と `𛅕`（U+1B155、Katakana Letter Small Ko）は、ベースフォントの `こ` と `コ`を既存の小書き仮名に合わせて縮小・配置した横組・縦組字形として追加します。

Manga1が規定する半濁点付きルビ14字形（`ㇷ゚`、`か゚`、`き゚`、`く゚`、`け゚`、`こ゚`、`カ゚`、`キ゚`、`ク゚`、`ケ゚`、`コ゚`、`セ゚`、`ツ゚`、`ト゚`）は、通常の一体字形を50%へ縮小した500 units幅の専用字形へ `ruby` で置換します。`ㇷ゚` には縦組専用ルビ字形も用意しています。

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

2記号の合字は、しっぽり明朝に収録されている `‼`（U+203C）、`⁇`（U+2047）、`⁈`（U+2048）、`⁉`（U+2049）の輪郭を使用します。3記号以上は、これら既存合字から感嘆符・疑問符の構成輪郭を抽出し、1文字セルへ再配置して生成します。横組・縦組とも記号はセル内で横並びになります。半角ASCIIの `!` と `?` は合字化しません。

単独の全角 `！`・`？` と16通りの合字には、明朝、右へ12度傾けた明朝、ゴシック、右へ12度傾けたゴシックの4字形を用意しています。既定は明朝です。`ss01`、`ss02`、`ss03` でそれぞれ斜体明朝、ゴシック、斜体ゴシックへ切り替えられ、3異体字は `aalt` にも登録されています。単独の明朝字形はベースフォント、明朝合字はしっぽり明朝、ゴシック字形はNoto Sans JPをもとに、全角1文字幅へ収めています。Noto版の明朝合字はMedium、SemiBold、Bold、Blackでそれぞれしっぽり明朝Medium、SemiBold、Bold、ExtraBoldを使用します。しっぽり明朝に400未満がないため、ExtraLight、Light、RegularはRegularを使用します。

この機能は[Adobe-Manga1-0](https://github.com/adobe-type-tools/Adobe-Manga1)の合字シーケンス集合、異体字構成、GSUB規則を参考にしています。Adobe-Manga1のCIDコレクション全体を実装するものではありません。

## 使用フォント

| 用途 | フォント | バージョン |
|---|---|---:|
| Noto版の本文、長音、ダッシュ、波線 | [Noto Serif JP](https://github.com/notofonts/noto-cjk) | 2.003 |
| Noto版の欧文 | [Libertinus Serif](https://github.com/alerque/libertinus) | 7.051 |
| 源暎こぶり明朝版の本文、長音、ダッシュ、波線 | [源暎こぶり明朝](https://okoneya.jp/font/genei-koburimin.html) | 6.1 |
| Manga1感嘆符・疑問符合字の記号輪郭 | [Shippori Mincho OTF 5ウェイト（しっぽり明朝）](https://fontdasu.com/shippori-mincho/) | 3.300 |
| Manga1感嘆符・疑問符合字のゴシック異体字 | [Noto Sans JP](https://github.com/notofonts/noto-cjk) | 2.004 |

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

引数を省略するとRegularのNoto版を生成します。`--weight`には`ExtraLight`、`Light`、`Regular`、`Medium`、`SemiBold`、`Bold`、`Black`を指定できます。Noto Serif JPとNoto Sans JPは固定コミット、Libertinus Serifと対応するしっぽり明朝ウェイトは公式配布アーカイブから取得し、すべてSHA-256を検証します。取得先、ウェイト対応、ハッシュは`font_profiles.py`へ集約しています。

Libertinus Serifの直立体はRegular・Semibold・Boldの3ウェイトだけですが、そのまま重複使用はしません。Noto Serif JPの7ウェイトにおける欧文インク量の推移を基準に、Regular由来のExtraLight・Lightを細く、Mediumを太くし、Bold由来のBlackを太く補正します。Regular・SemiBold・Boldは元のLibertinus輪郭を保持します。

```sh
# Noto版Regular
.venv/bin/python build_font.py

# Noto版の全7ウェイト
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  .venv/bin/python build_font.py --weight "$weight"
done

# 源暎こぶり明朝版Regular
.venv/bin/python build_font.py --base koburi
```

出力は`dist/NobigoeMincho-<Weight>.otf`と`dist/NobigoeKoburiMincho-Regular.ttf`です。ダウンロードした元フォントは一時ディレクトリだけに置き、リポジトリへ保存しません。

公開版は[GitHub Releases](https://github.com/ouvill/nobigoe-font/releases)から、Noto版と源暎こぶり明朝版を別々のZIPで配布する予定です。

### 配布ZIPを作成

2ファミリーを混在させず、フォント、README、OFL、第三者通知、SHA-256マニフェストをそれぞれの再現可能なZIPへまとめます。先に上記の全フォントを生成してください。

```sh
.venv/bin/python package_release.py
```

```text
dist/NobigoeMincho-v1.024.zip
dist/NobigoeKoburiMincho-v1.024.zip
```

### ローカルの元フォントを使用

```sh
.venv/bin/python build_font.py \
  --source /path/to/NotoSerifJP-Regular.otf \
  --latin-source /path/to/LibertinusSerif-Regular.otf \
  --punctuation-source /path/to/ShipporiMincho-OTF-Regular.otf \
  --sans-source /path/to/NotoSansJP-Regular.otf \
  --output dist/NobigoeMincho-Regular.otf
```

`--source`、`--latin-source`、`--punctuation-source`、`--sans-source` の一部だけを指定した場合、指定しなかったフォントだけを自動取得します。`--latin-source`はNoto版だけに適用されます。Noto Serif CJKのTTCを入力する場合は `--face` でフェイス番号を指定できます。源暎こぶり明朝版へローカルファイルを渡す場合は`--base koburi --source /path/to/GenEiKoburiMin6-R.ttf`とします。

しっぽり明朝はOTF版とTTF版のどちらも `--punctuation-source` に指定できます。明示したファイルはすべての明朝合字に使用されます。既定の自動取得ではNobigoeのウェイトに対応するOTF版を選び、Noto版ではCFF、源暎こぶり明朝版ではTrueTypeの輪郭形式へ追加字形を変換します。

### テスト

生成設定、命名、固定取得元とTrueType字形追加処理の単体テストを実行します。

```sh
.venv/bin/python -m unittest discover -s tests -v
```

### 濁点・半濁点の位置を調整

Manga1方式の全191列は、字種と記号ごとに次の4ファイルへ分割しています。各ファイルは独立して位置を調整できます。

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
| `aalt` | 全角感嘆符・疑問符および合字の3異体字を列挙 |
| `ss01` | 全角感嘆符・疑問符および合字を斜体明朝へ置換 |
| `ss02` | 全角感嘆符・疑問符および合字をゴシックへ置換 |
| `ss03` | 全角感嘆符・疑問符および合字を斜体ゴシックへ置換 |
| `ruby` | Manga1の半濁点付きルビ14字形へ置換 |
| `calt` | 連続する長音・ダッシュ・波線の始端／中間／終端置換 |
| `vert` / `vrt2` | 縦組用の伸長記号、濁点・半濁点付き仮名、`ㇷ゚`ルビ字形 |

一般的なシェーピングエンジンでは `ccmp` と `calt` は既定で有効です。アプリケーション側で `calt` を無効にすると、伸長記号の自動連結は行われません。

CSSでは、たとえば `font-feature-settings: "ss03" 1;` で全角感嘆符・疑問符を斜体ゴシックへ、`font-feature-settings: "ruby" 1;` で対象の半濁点付き仮名をルビ字形へ切り替えられます。

## ライセンス

生成フォントに取り込まれるNoto Serif JP、Libertinus Serif、源暎こぶり明朝、Noto Sans JP、しっぽり明朝は、いずれもSIL Open Font License 1.1で提供されています。本プロジェクトのフォント関連ファイルと生成フォントも [`OFL.txt`](OFL.txt) の条件に従います。

第三者フォントの著作権表示と改変内容は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。生成フォントのファミリー名は元フォントと区別し、`Noto`の名称を派生フォント名に残さない `Nobigoe Mincho`（のびごえ明朝）に変更しています。

本プロジェクトはAdobe、Google、Noto Project、Libertinus Project、またはShippori Mincho Projectによる公式配布物ではありません。`Noto`はGoogle LLCの商標です。各名称は出典と互換性を明示する目的でのみ使用しています。
