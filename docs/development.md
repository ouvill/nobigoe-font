# ビルドと開発

[READMEへ戻る](../README.md)

特記がない限り、コマンドはリポジトリのルートで実行します。

## 使用フォント

| 用途 | フォント | バージョン |
|---|---|---:|
| Noto版の本文、長音、ダッシュ、波線 | [Noto Serif JP](https://github.com/notofonts/noto-cjk) | 2.003 |
| Noto版の既定欧文 | [Libertinus Serif](https://github.com/alerque/libertinus) | 7.051 |
| 比較用欧文候補 | [STIX Two Text](https://github.com/stipub/stixfonts) | 2.13 b171 |
| 比較用欧文候補 | [Source Serif 4](https://github.com/adobe-fonts/source-serif) | 4.005 |
| 源暎こぶり明朝版の本文、長音、ダッシュ、波線、および同版のルビ専用字形 | [源暎こぶり明朝](https://okoneya.jp/font/genei-koburimin.html) | 6.1 |
| Manga1感嘆符・疑問符合字の記号輪郭 | [Shippori Mincho OTF 5ウェイト（しっぽり明朝）](https://fontdasu.com/shippori-mincho/) | 3.300 |

取得元、バージョン、SHA-256、著作権表示は[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)に記載しています。

## 必要環境

- Python 3.13
- `uv`
- `fonttools`
- `skia-pathops`
- OpenType SanitizerとHarfBuzz（検証する場合）
- AFDKOの`otfautohint`（`--autohint`を使用する場合）

Python依存関係をuvで同期します。

```sh
uv sync
```

`--autohint`を使用する場合もAFDKOは通常依存に含まれるため、`uv run`から`otfautohint`を実行できます。通常のビルドには不要です。

## コード構成

Pythonコードは`src/nobigoe_font/`へ集約し、CLI、生成パイプライン、フォント操作、設定データをインストール可能な1パッケージとして管理しています。

| モジュール | 責務 |
|---|---|
| `cli.py` | `nobigoe-build`の引数検証と入出力の解決 |
| `variable_cli.py` / `variable_marks.py` | `nobigoe-build-variable`とNoto CFF2可変フォントへの濁点・半濁点字形、連結記号追加 |
| `pipeline.py` | フォント生成手順のオーケストレーション |
| `profiles.py` / `sources.py` | ファミリー、ウェイト、固定取得元、SHA-256検証済みキャッシュ |
| `marks.py` / `mark_positions/` | 濁点・半濁点の対象、配置型、JSON設定の検証 |
| `geometry.py` / `operations.py` | 輪郭変換、cmap、CFF／TrueType、欧文レイアウトの操作 |
| `punctuation.py` / `features.py` | 感嘆符・疑問符合字の合成とOpenType機能の生成・結合 |
| `metadata.py` / `hinting.py` / `release.py` | 命名、欧文再ヒント、配布ZIP作成 |
| `novel.py` / `novel_katakana.py` / `novel_han.py` / `novel_metrics.py` | Novelひらがな・カタカナの3マスター設計、Unicode 15.1 Han集合と等方縮小、字面・ink・カウンター計測 |
| `kana_terminals.py` / `terminal_plans/` / `variable_kana.py` | 互換トポロジーの筆端変形、字別・横縦・3マスター台帳、可変制作正本の生成と固定ウェイト実体化 |
| `variable_stix.py` / `stix_latin_tuning.json` | STIX Two Textの主線基準ウェイト補間、制作VFの生成、固定7ウェイト実体化 |

## 自動取得して生成

引数を省略すると、欧文にLibertinus Serifを使用するRegularのNoto版を生成します。`--weight`には`ExtraLight`、`Light`、`Regular`、`Medium`、`SemiBold`、`Bold`、`Black`を指定できます。Noto Serif JP、STIX Two Textは固定コミットまたはタグ、Libertinus Serif、Source Serif 4、源暎こぶり明朝、対応するしっぽり明朝ウェイトは公式配布アーカイブから取得し、すべてSHA-256を検証します。初回に取得したファイルと展開済みフォントは`.cache/font-sources/`へ保存し、2回目以降はSHA-256が一致するローカルファイルを再利用します。取得先、ウェイト対応、ハッシュは`src/nobigoe_font/profiles.py`へ集約しています。

Libertinus Serifの直立体はRegular・Semibold・Boldの3ウェイトです。和文と欧文の高さを厳密に追従させて横幅まで変形するのではなく、Noto Serif JPの和文とおおむね高さが揃う等方拡大を実マスターごとに固定しています。Regular由来のExtraLight・Light・Regular・Mediumは1.119倍、Semiboldは1.129倍、Bold由来のBold・Blackは1.138倍です。同じマスターから作るウェイトでは輪郭と送り幅に同じ倍率を使い、個々の欧文字形の送り幅を共通化することで、拡大率に由来する文字列幅の逆転をなくしています。そのうえで細い横画をほぼ保ち、太い縦画を中心に-13〜+6 unitsのウェイト別輪郭補正を行います。同じ変換を通常字形、`ccmp`・`locl`異体字、標準合字へ適用します。

欧文ソースからはBasic Latin、Latin-1 Supplement、Latin Extended-A/B、Combining Diacritical Marks、Latin Extended Additionalと、欧文組版で使うダッシュ、引用符、分数スラッシュ、マイナス記号などを取り込みます。Unicodeに直接割り当てられた字形だけでなく、`ccmp`、`locl`、`liga`、`dlig`、`frac`、`lnum`、`onum`、`pnum`、`tnum`、`subs`、`sups`、`zero`などのGSUB出力字形、`kern`、`mark`、`mkmk`のGPOS、GDEFの字形クラスとMarkAttachClassも同じ倍率・ベースライン補正で移植します。和文ソース側の縦組・仮名・約物機能は維持します。

`--autohint`を指定すると、生成後にAFDKO `otfautohint`を実行します。処理対象は今回取り込んだ欧文字形だけに限定し、Noto Serif JP由来の和文字形の既存ヒントには触れません。`otfautohint`が見つからない場合はエラーにして、未ヒントの成果物を正常終了として扱いません。

`--latin-family`では`noto`、`libertinus`、`stix-two-text`、`source-serif-4`を選択できます。既定の`libertinus`は従来の全7ウェイト設定を保持します。`noto`はNoto Serif JPの欧文字形を置換しません。STIX Two Textは公式`STIXTwoText[wght].ttf`の400・700間にある互換輪郭から全7ウェイトを生成し、1.110倍して取り込みます。Noto Serif JP和文の`口`・`日`・`田`・`中`・`山`と、NotoおよびSTIX欧文の`H`・`I`・`E`・`F`・`L`・`n`・`i`・`l`・`h`・`m`・`u`を基準にします。公式STIXにないExtraLightとLightは、Noto和文とNoto欧文の主縦線幅中央値の中間値へSTIXの主縦線を合わせます。RegularからBlackまではNoto和文の主縦線へ合わせます。ウェイトごとに一つの補間位置を全通常字形とGSUB出力へ共通適用し、字別の輪郭面積や送り幅には合わせないため、STIX本来のコントラストと字形間の関係を維持します。個別位置を持つ外れ値は`ƒ`（U+0192）だけです。求めた補間位置が公式軸の400–700範囲外にある場合も同じ互換輪郭と水平メトリクスだけを外挿し、別フォントを混ぜません。計測ツールの`--thin-target japanese`または`--thin-target noto-latin`で、細字を各端へ合わせた比較位置も生成できます。Source Serif 4は可変フォントを`opsz=20`と各Nobigoeウェイトの`wght=200–900`で実体化し、1.088倍で取り込みます。比較候補の倍率はRegularの大文字高をNoto Serif JPへ揃えた初期値です。

```sh
# STIX細字を和文・欧文主縦線の中間、Regular以降を和文基準で再計測
uv run python tools/measure_stix_stems.py

# 細字を和文側・欧文側の各端で比較
uv run python tools/measure_stix_stems.py --thin-target japanese
uv run python tools/measure_stix_stems.py --thin-target noto-latin

# Noto版Regular
uv run nobigoe-build

# 取り込んだ欧文字形だけをAFDKOで再ヒント
uv run nobigoe-build --autohint

# Noto版の全7ウェイト
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --weight "$weight" --autohint
done

# STIX欧文の調整済み制作VFを一度生成し、そこから固定7ウェイトを作る
uv run nobigoe-build \
  --build-variable-stix dist/NobigoeSTIXLatinDesign-VF.ttf
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --latin-family stix-two-text \
    --latin-source dist/NobigoeSTIXLatinDesign-VF.ttf \
    --weight "$weight" \
    --output "dist/comparison/NobigoeMinchoSTIX-$weight.otf"
done

# Novel可変かな制作正本を一度生成し、そこから固定7ウェイトを作る
uv run nobigoe-build \
  --build-variable-kana dist/NobigoeNovelKanaDesign-VF.ttf
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --kana-style novel --variable-kana \
    --variable-kana-source dist/NobigoeNovelKanaDesign-VF.ttf \
    --weight "$weight" --autohint
done

# 源暎こぶり明朝版Regular
uv run nobigoe-build --base koburi

# Noto CFF2可変フォントへ既存のびごえ約物、濁点字形、連結記号を追加
uv run nobigoe-build-variable

# Regularの欧文候補を比較用ディレクトリへ生成
for latin in noto libertinus stix-two-text source-serif-4; do
  uv run nobigoe-build \
    --latin-family "$latin" \
    --output "dist/comparison/NobigoeMincho-Regular-$latin.otf"
done
```

既定ビルドの出力は`dist/NobigoeMincho-<Weight>.otf`と`dist/NobigoeKoburiMincho-Regular.ttf`です。`--kana-style novel`の出力は`dist/NobigoeNovelMincho-<Weight>.otf`で、既存配布名を上書きしません。`--build-variable-kana OUTPUT`と`--build-variable-stix OUTPUT`は、それぞれの調整済み制作VFを明示した場所へ生成します。`--variable-kana`は前者から対象ウェイトのかなを取り込み、`--latin-family stix-two-text`は公式STIX可変TTFまたは後者から対象ウェイトの欧文を実体化します。`--output`を省略して既定以外の欧文候補を指定した場合は、`dist/comparison/<PostScript名>-<Latin family>.otf`へ出力します。固定取得元は`.cache/font-sources/`へ保存するため、同じソースを使用するビルドでは再ダウンロードやZIPの再展開を行いません。キャッシュ場所は`--cache-dir /path/to/cache`で変更できます。

`nobigoe-build-variable`は固定コミットの`NotoSerifJP-VF.otf`と、固定版でも使用するしっぽり明朝の各ウェイトを取得します。Notoに既存一体字形がない濁点・半濁点列の横組・縦組CFF2 CharString、全角`！`・`？`およびManga1方式の16合字、連続する`ー`、`―`、`〜`（`～`）、`〰`をつなぐ可変字形とGSUB規則を追加します。可変版の明朝感嘆符・疑問符は、ExtraLightだけを18本・6本の少数三次ベジェで再設計し、Light以上はしっぽり明朝Regular、Medium、SemiBold、Bold、ExtraBoldの実輪郭を使用します。しっぽり明朝の14曲線からなる疑問符は、右下内側の1曲線を固定パラメータで5分割し、形を変えず18曲線へ揃えます。直立感嘆符は元から6曲線です。黒みはNotoの全角約物ではなく、Noto Serif JPの`川`・`目`・`田`をY=350、450、550、650で切った縦主線幅の中央値を基準にします。200、300、400、500、600、700、900の基準値は順に44.0、53.6、65.2、80.1、95.0、117.0、144.0 unitsです。疑問符はしっぽり明朝の外周、高さ、筆だまりを保って右太線の内周だけを調整し、感嘆符は下部の細い軸を保って上部テーパーだけを左右から調整します。これによりExtraLightで承認した漢字主線との光学差を全ウェイトへ維持します。下点は元輪郭の上端を保って直径をウェイト別に84〜90%へ縮めた正円とし、5連感嘆符は200-unit間隔で配置して全角セル境界でも間隔を維持します。明朝、斜体明朝、ゴシック、斜体ゴシックを`aalt`と`ss01`–`ss03`で選択できます。濁点・半濁点の配置と連結記号の輪郭も同じ7ウェイトのレビュー済みマスターを`wght`軸上で補間し、Notoの既存CFF2字形とVariationStoreは維持します。緩い波線は`ss04`、または先頭に`~`を置く方法で選択できます。既定出力は`dist/NobigoeVariableMarks-VF.otf`です。この実験的出力には`nobigoe-build`のその他の約物、欧文・ルビ置換は含みません。
疑問符の下点は本体全体の外接中心ではなく、下へ伸びる線の終端中心へ揃えます。

可変版では、全角`！`・`？`とU+3099・U+309Aの4列、および`♡`・`♥`とU+3099の2列もCFF2可変字形として生成します。全角約物4列は横組・縦組を別字形とし、`ccmp`、全角幅濁点・半濁点用の`liga`、`vert`、`vrt2`へ登録します。ハート2列は固定版と同じ白抜き合成を行った後、7マスターの輪郭を補間互換な三次ベジェ構造へ揃え、既存の私用領域割り当ても維持します。

公開版は[GitHub Releases](https://github.com/ouvill/nobigoe-font/releases)から、Noto版と源暎こぶり明朝版を別々のZIPで配布します。開発中のNovel版は公開版に含めません。

リリース版番号の唯一の正本は`src/nobigoe_font/version.json`です。新しい版ではこのファイルの`version`だけを`N.NNN`形式で更新し、`uv lock`を実行してください。Pythonパッケージのメタデータ、生成フォント、配布ZIP、公開サイト、GitHub Actionsは同じ値を読み取るため、`pyproject.toml`、Webサイト、テスト、説明文へ版番号を転記する必要はありません。

```sh
uv lock
uv lock --check
uv run python -m unittest discover -s tests
```

## 配布ZIPを作成

既定では安定版2ファミリーだけを、フォント、README、OFL、第三者通知、SHA-256マニフェストを含む再現可能なZIPへまとめます。先にNoto版と源暎こぶり明朝版を生成してください。

```sh
uv run nobigoe-package
```

```text
dist/NobigoeMincho-v<version>.zip
dist/NobigoeKoburiMincho-v<version>.zip
```

ローカル検証用にNovel版ZIPも必要な場合だけ、Novel全7ウェイトを生成してから明示的に追加します。このオプションはGitHub Releaseでは使用しません。

```sh
uv run nobigoe-package --include-experimental
```

```text
dist/NobigoeNovelMincho-v<version>.zip
```

## GitHub Releaseを公開

`.github/workflows/release.yml`は`src/nobigoe_font/version.json`と同じ`vN.NNN`タグで起動します。安定版8フォントと開発中のNovel版7フォントを生成し、テスト、OpenType Sanitizer、HarfBuzzで検証します。GitHub Releaseへ添付するのは安定版8フォントを収録した再現可能な2つのZIPと`SHA256SUMS`だけです。次のように正本からタグ名を取得して注釈付きタグをpushするか、GitHub Actionsの「Build and publish release」を同じタグ名で手動実行してください。

```sh
version=$(PYTHONPATH=src python3 -m nobigoe_font.version)
git tag -a "v${version}" -m "v${version}"
git push origin main "v${version}"
```

## ローカルの元フォントを使用

```sh
uv run nobigoe-build \
  --source /path/to/NotoSerifJP-Regular.otf \
  --latin-source /path/to/LibertinusSerif-Regular.otf \
  --punctuation-source /path/to/ShipporiMincho-OTF-Regular.otf \
  --output dist/NobigoeMincho-Regular.otf
```

`--source`、`--latin-source`、`--punctuation-source`の一部だけを指定した場合、指定しなかったフォントだけを自動取得します。`--latin-source`はNoto版だけに適用され、`--latin-family`で選択したプロファイルの倍率・補正・可変軸設定を使用します。`source-serif-4`へローカルファイルを指定する場合は`wght`と`opsz`を持つ可変フォントが必要です。`--latin-family noto`と`--latin-source`は併用できません。Noto Serif CJKのTTCを入力する場合は`--face`でフェイス番号を指定できます。源暎こぶり明朝版へローカルファイルを渡す場合は`--base koburi --source /path/to/GenEiKoburiMin6-R.ttf`とします。

明示したローカルファイルはキャッシュより優先します。指定しなかった取得元だけキャッシュを検索し、正しいSHA-256のファイルがなければダウンロードします。キャッシュ内の不完全または不正なファイルは一時ファイルへ再取得し、検証成功後に置換します。

しっぽり明朝はOTF版とTTF版のどちらも`--punctuation-source`に指定できます。明示したファイルはすべての明朝合字に使用されます。既定の自動取得ではNobigoeのウェイトに対応するOTF版を選び、Noto版ではCFF、源暎こぶり明朝版ではTrueTypeの輪郭形式へ追加字形を変換します。

## テスト

生成設定、命名、固定取得元とTrueType字形追加処理の単体テストを実行します。

```sh
uv run python -m unittest discover -s tests -v
```

## 濁点・半濁点の位置を調整

共通の基準配置191列は、字種と記号ごとの4ファイルへ分割しています。源暎こぶり明朝版の専用レイヤーと、感嘆符・疑問符4列のファミリー・ウェイト別配置も同じディレクトリで管理します。

```text
src/nobigoe_font/mark_positions/hiragana_dakuten.json
src/nobigoe_font/mark_positions/hiragana_handakuten.json
src/nobigoe_font/mark_positions/katakana_dakuten.json
src/nobigoe_font/mark_positions/katakana_handakuten.json
src/nobigoe_font/mark_positions/koburi.json
src/nobigoe_font/mark_positions/punctuation.json
```

各字の`horizontal`と`vertical`は`[scale, x, y, rotation]`です。`scale`は結合記号の等方倍率、`x`と`y`は拡大後の平行移動量で、正の値は右・上へ移動します。`rotation`は度数法の回転角で、正の値は反時計回りです。回転の中心には`scale`、`x`、`y`適用後の記号輪郭のバウンディングボックス中心を使うため、角度を変えても記号の中心位置は動きません。`nobigoe-build`は共通4ファイルの記号種、キー集合、配列長、有限値、正の倍率を検証し、191列の不足や重複があれば生成を停止します。収録値では濁点だけを文字ごと・横縦別に光学調整し、半濁点は回転させていません。Noto版で生成する167列は、実際のウェイトの輪郭で基字との交差も検査します。交差時は記号の大きさを変えず、基字と記号の中心関係から求めた上・横・斜めの外向き候補を比較し、縦メトリクス内で輪郭が離れる最短距離の移動を採用します。

```json
"30A1": {
  "horizontal": [0.8, 955, -57, 3],
  "vertical": [0.8, 1036, 171, 3]
}
```

Version 1.015の配置値は、[源暎こぶり明朝](https://okoneya.jp/font/genei-koburimin.html)の一体型濁点・半濁点字形を比較基準にしています。同フォントの1024 units/emの輪郭寸法と基字からの相対位置を1000 units/emへ正規化し、Nobigoe Minchoの各基字へ移植しました。源暎こぶり明朝のフォントデータや輪郭自体は取り込んでいません。

長音濁点はManga1の191列には含まれないため、`src/nobigoe_font/marks.py`の`CHOON_DAKUTEN_MARK_CENTERS`で横組・縦組の記号中心を管理します。この値も源暎こぶり明朝のU+E0DBを1000 units/emへ正規化したものです。

`src/nobigoe_font/mark_positions/punctuation.json`は、感嘆符・疑問符と結合濁点・半濁点の4列について、Noto版7ウェイトと源暎こぶり明朝版Regularの横組・縦組配置をすべて明示します。実輪郭の候補比較と視覚調整に基づき、感嘆符・疑問符の濁点は両ファミリー・全ウェイト・横縦とも時計回り3度（`rotation: -3`）、半濁点は0度に設定しています。ビルド時にファミリー、ウェイト、4つのキー集合と各変換値を検証し、不足や未定義ウェイトがあれば生成を停止します。

`src/nobigoe_font/mark_positions/koburi.json`は、源暎こぶり明朝に一体字形がない103列だけを上書きします。源暎こぶり明朝v6.1の既存88列から、基字に対する記号の相対位置と寸法を通常仮名・小書き仮名、濁点・半濁点、横組・縦組ごとに測定して配置へ反映しています。元フォントの88列は専用レイヤーで上書きせず、元の一体字形をそのまま使用します。設定ファイルには測定元のSHA-256、units/em、GPOS機能、対象数も記録し、ビルド時に検証します。

Noto Serif JPに既存一体字形がある24列は元の輪郭と縦組字形を優先します。該当列にも完全な191キー集合を検証するための設定値がありますが、生成輪郭には適用されません。U+31F7`ㇷ` + U+309Aもこの24列に含まれます。

## 紹介サイト

紹介サイトのコードと開発設定は`website/`にまとめています。リポジトリ直下のフォント生成処理とは独立しています。

```sh
cd website
npm ci
npm run dev
```

`website/`内で`npm run check`を実行するとAstroの型検査、`npm run build`を実行すると`website/site-dist/`への静的ビルドを行います。

### OMPのLanguage Server

リポジトリ直下からOMPを起動すると、`.omp/lsp.json`に従ってPython、Astro、TypeScript／JavaScript、CSS、HTML、JSONのLanguage Serverが有効になります。`uv sync`でbasedpyrightを、`website/`で`npm ci`を実行してWeb用Language Serverをインストールしてください。`npm ci`後の`astro sync`は自動実行され、Astroの型定義も生成されます。

かな比較`/compare/`は、小説本文用のNovel仮名と欧文候補を制作途中から確認できる公開制作プレビューです。Noto／Koburi／Novelの比較、固定7ウェイト、横組・縦組本文、開発用可変かなソースに加え、Noto Serif JP内蔵欧文、STIX Two Text、Spectral、Source Serif 4、Literata、Roboto Serif、Newsreader、Petronaを同じ和欧混植文・サイズ・ウェイト・光学サイズで比較できます。Pagesワークフローで必要な比較用Webfontを生成します。Novel版と欧文比較用Webfontは通常の配布ZIPとタグリリースには含めません。

公開サイトは<https://nobigoe.ouvill.net/>です。`.github/workflows/pages.yml`が`main`へのpushごとに最新GitHub Releaseのフォントを取得し、Webfontを生成してAstroの成果物をGitHub Pagesへ配信します。

配信用Webfont（`website/src/assets/fonts/*.woff2`）は生成物のためGit管理に含めません。リポジトリ直下から標準版Regularを更新する場合は、次のコマンドを使用します。

```sh
uv run pyftsubset dist/NobigoeMincho-Regular.otf \
  --output-file=website/src/assets/fonts/NobigoeMincho-Regular.woff2 \
  --flavor=woff2 \
  --glyphs='*' \
  --layout-features='*' \
  --name-IDs='*' \
  --name-languages='*' \
  --notdef-glyph \
  --notdef-outline \
  --recommended-glyphs
```

欧文比較用Webfontだけを生成する場合は、リポジトリ直下で次を実行します。入力は固定コミットまたはタグとSHA-256で検証し、欧文Unicode範囲へサブセットしたWOFF2を`website/src/assets/fonts/`へ出力します。

```sh
uv run python website/tools/generate-latin-candidate-webfonts.py
```
