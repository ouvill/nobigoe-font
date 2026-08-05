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
| `cli.py` | こぶり版・欧文比較・開発用制作VFの引数検証と入出力の解決 |
| `variable_cli.py` / `variable_marks.py` / `variable_novel.py` | Noto CFF2可変ソースへののびごえ共通カスタマイズ、Novel CFF2派生、両可変正本からの固定7ウェイト出力 |
| `essential_cli.py` / `essential.py` | カスタマイズ済み可変ソースから5つの伸長記号と必要なレイアウト閉包だけを残すフォールバック用VF生成 |
| `pipeline.py` | 可変正本の固定ウェイト実体化、Novel固定版専用カスタマイズ、欧文取り込み・命名・ヒント処理 |
| `profiles.py` / `sources.py` | ファミリー、ウェイト、固定取得元、SHA-256検証済みキャッシュ |
| `marks.py` / `mark_positions/` | 濁点・半濁点の対象、配置型、JSON設定の検証 |
| `geometry.py` / `operations.py` | 輪郭変換、cmap、CFF／TrueType、欧文レイアウトの操作 |
| `punctuation.py` / `features.py` | 感嘆符・疑問符合字の合成とOpenType機能の生成・結合 |
| `metadata.py` / `hinting.py` / `release.py` | 命名、欧文再ヒント、配布ZIP作成 |
| `novel.py` / `novel_katakana.py` / `novel_han.py` / `novel_metrics.py` | Novelひらがな・カタカナの3マスター設計、Unicode 15.1 Han集合と等方縮小、字面・ink・カウンター計測 |
| `kana_terminals.py` / `terminal_plans/` | 三次ベジェpathの互換トポロジーを保つ筆端変形と、字別・横縦・3マスター台帳 |
| `brush.py` | Noto由来の漢字へ任意適用する、起筆・送筆・収筆に沿った非水平筆画の筆圧変化 |
| `variable_stix.py` / `stix_latin_tuning.json` | STIX Two Textの主線基準ウェイト補間、制作VFの生成、固定7ウェイト実体化 |

## 自動取得して生成

引数を省略すると、欧文にLibertinus Serifを使用するRegularのNoto版を生成します。`--weight`には`ExtraLight`、`Light`、`Regular`、`Medium`、`SemiBold`、`Bold`、`Black`を指定できます。Noto Serif JP、STIX Two Textは固定コミットまたはタグ、Libertinus Serif、Source Serif 4、源暎こぶり明朝、対応するしっぽり明朝ウェイトは公式配布アーカイブから取得し、すべてSHA-256を検証します。初回に取得したファイルと展開済みフォントは`.cache/font-sources/`へ保存し、2回目以降はSHA-256が一致するローカルファイルを再利用します。取得先、ウェイト対応、ハッシュは`src/nobigoe_font/profiles.py`へ集約しています。

Libertinus Serifの直立体はRegular・Semibold・Boldの3ウェイトです。和文と欧文の高さを厳密に追従させて横幅まで変形するのではなく、Noto Serif JPの和文とおおむね高さが揃う等方拡大を実マスターごとに固定しています。Regular由来のExtraLight・Light・Regular・Mediumは1.119倍、Semiboldは1.129倍、Bold由来のBold・Blackは1.138倍です。同じマスターから作るウェイトでは輪郭と送り幅に同じ倍率を使い、個々の欧文字形の送り幅を共通化することで、拡大率に由来する文字列幅の逆転をなくしています。そのうえで細い横画をほぼ保ち、太い縦画を中心に-13〜+6 unitsのウェイト別輪郭補正を行います。同じ変換を通常字形、`ccmp`・`locl`異体字、標準合字へ適用します。

欧文ソースからはBasic Latin、Latin-1 Supplement、Latin Extended-A/B、Combining Diacritical Marks、Latin Extended Additionalと、欧文組版で使うダッシュ、引用符、分数スラッシュ、マイナス記号などを取り込みます。Unicodeに直接割り当てられた字形だけでなく、`ccmp`、`locl`、`liga`、`dlig`、`frac`、`lnum`、`onum`、`pnum`、`tnum`、`subs`、`sups`、`zero`などのGSUB出力字形、`kern`、`mark`、`mkmk`のGPOS、GDEFの字形クラスとMarkAttachClassも同じ倍率・ベースライン補正で移植します。和文ソース側の縦組・仮名・約物機能は維持します。

`--autohint`を指定すると、生成後にAFDKO `otfautohint`を実行します。処理対象は今回取り込んだ欧文字形だけに限定し、Noto Serif JP由来の和文字形の既存ヒントには触れません。`otfautohint`が見つからない場合はエラーにして、未ヒントの成果物を正常終了として扱いません。

`--han-brush-elements`を指定すると、Noto由来の漢字とGSUBから到達する漢字異体字へ毛筆エレメントを追加します。輪郭コマンド列から、縦画・斜画の起筆と終筆、横画末端のウロコを形状・方向・寸法で照合し、一致したエレメントだけを局所変形します。縦画・斜画は中央の直線を維持し、起筆と終筆の範囲だけを三次ベジェ曲線へ置換します。終筆は張り出しと収束長を抑えた`--han-brush-end-profile traditional`を既定とし、`silver`で長く非対称な白銀比終筆へ切り替えます。どちらも同じ節点順を使い、Notoの終筆制御点は検出にだけ用います。

`--latin-family`では`noto`、`libertinus`、`stix-two-text`、`source-serif-4`を選択できます。既定の`libertinus`は従来の全7ウェイト設定を保持します。`noto`はNoto Serif JPの欧文字形を置換しません。STIX Two Textは公式`STIXTwoText[wght].ttf`の400・700間にある互換輪郭から全7ウェイトを生成し、1.110倍して取り込みます。Noto Serif JP和文の`口`・`日`・`田`・`中`・`山`と、NotoおよびSTIX欧文の`H`・`I`・`E`・`F`・`L`・`n`・`i`・`l`・`h`・`m`・`u`を基準にします。公式STIXにないExtraLightとLightは、Noto和文とNoto欧文の主縦線幅中央値の中間値へSTIXの主縦線を合わせます。RegularからBlackまではNoto和文の主縦線へ合わせます。ウェイトごとに一つの補間位置を全通常字形とGSUB出力へ共通適用し、字別の輪郭面積や送り幅には合わせないため、STIX本来のコントラストと字形間の関係を維持します。個別位置を持つ外れ値は`ƒ`（U+0192）だけです。求めた補間位置が公式軸の400–700範囲外にある場合も同じ互換輪郭と水平メトリクスだけを外挿し、別フォントを混ぜません。計測ツールの`--thin-target japanese`または`--thin-target noto-latin`で、細字を各端へ合わせた比較位置も生成できます。Source Serif 4は可変フォントを`opsz=20`と各Nobigoeウェイトの`wght=200–900`で実体化し、1.088倍で取り込みます。比較候補の倍率はRegularの大文字高をNoto Serif JPへ揃えた初期値です。

```sh
# STIX細字を和文・欧文主縦線の中間、Regular以降を和文基準で再計測
uv run python tools/measure_stix_stems.py

# 細字を和文側・欧文側の各端で比較
uv run python tools/measure_stix_stems.py --thin-target japanese
uv run python tools/measure_stix_stems.py --thin-target noto-latin

# Noto Variableを一度カスタマイズし、Nobigoe・Novelの固定各7ウェイトを最大4並列で生成
uv run nobigoe-build-variable

# 上で生成した可変ソースから、5文字だけに対応するエッセンシャル版を生成
uv run nobigoe-build-essential

# 両ファミリーへLibertinus Serifを取り込んだ後、欧文字形だけを再ヒント
uv run nobigoe-build-variable --autohint

# CI用に可変フォントとRegularだけを生成
uv run nobigoe-build-variable --static-weight Regular --autohint

# リリース用にNobigoe全7ウェイトと、検証に使うNovelの2ウェイトだけを生成
uv run nobigoe-build-variable --autohint --jobs 4 \
  --novel-static-weight Regular --novel-static-weight Black

# STIX欧文の調整済み制作VFを一度生成し、そこから固定7ウェイトを作る
uv run nobigoe-build \
  --build-variable-stix dist/NobigoeSTIXLatinDesign-VF.ttf
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --latin-family stix-two-text \
    --latin-source dist/NobigoeSTIXLatinDesign-VF.ttf \
    --weight "$weight" \
    --output "dist/comparison/NobigoeMinchoSTIX-$weight.otf"
done

# カスタマイズ済みNobigoe CFF2と派生Novel CFF2の出力先を明示
uv run nobigoe-build-variable \
  --output dist/NobigoeVariableMarks-VF.otf \
  --novel-output dist/NobigoeNovelMincho-VF.otf

# 漢字の縦画・斜画へ起筆から収筆までの筆圧変化を加える
uv run nobigoe-build \
  --han-brush-elements \
  --output dist/comparison/NobigoeMincho-Brush-Regular.otf

# 長く非対称な白銀比終筆へ切り替える
uv run nobigoe-build \
  --source /path/to/NotoSerifJP-Regular.otf \
  --han-brush-elements \
  --han-brush-end-profile silver \
  --output dist/comparison/NobigoeMincho-BrushSilver-Regular.otf

# 起筆・終筆・ウロコを拡大SVGで比較し、Inkscape用の単体SVGも書き出す
uv run python tools/generate-brush-element-patterns.py \
  --noto /path/to/NotoSerifJP-Regular.otf \
  --genryu /path/to/GenRyuMin2JP-R.otf \
  --output /tmp/brush-element-patterns.html

# 別ディレクトリの編集中SVGと選択台帳を一時的に再読込する
uv run python tools/generate-brush-element-patterns.py \
  --noto /path/to/NotoSerifJP-Regular.otf \
  --genryu /path/to/GenRyuMin2JP-R.otf \
  --design-dir /path/to/brush-element-designs \
  --selection /path/to/selection.json \
  --output /tmp/brush-element-patterns.html

# 源暎こぶり明朝版Regular
uv run nobigoe-build --base koburi

# Regularの欧文候補を比較用ディレクトリへ生成
for latin in noto libertinus stix-two-text source-serif-4; do
  uv run nobigoe-build \
    --latin-family "$latin" \
    --output "dist/comparison/NobigoeMincho-Regular-$latin.otf"
done
```

`generate-brush-element-patterns.py`は完全フォントを生成せず、起筆、終筆、ウロコ、横画起筆、点、左払い筆端、右払い筆端、はね、折れ、囲み左下、囲み右下、囲み左上、左払い上部の13種についてA/B/C案を拡大SVGで比較します。終筆には接線連続の試作D、ウロコと折れには他書体の実輪郭を比較して組み直した試作Dも追加します。終筆Bは`silver`、終筆Cは`traditional`と同じ実装から生成し、D案は比較専用です。選択台帳`tools/brush-element-designs/selection.json`では、起筆B・終筆C・ウロコB・横画起筆B・点C・左払い筆端C・右払い筆端C・はねB・折れB・囲み左下B・囲み右下B・囲み左上B・左払い上部Bを確定しています。比較画面は各エレメントのNoto、A、B、C、源流明朝と、3種のDを表示し、全68輪郭を個別の参考SVGへ書き出します。候補案はコード定義から生成し、Notoと源流明朝は入力フォントの実輪郭を比較参照としてだけSVG化します。保管済みSVGとブラウザへ読み込んだSVGは判断・指示用の参考データであり、フォント輪郭の入力やコード候補の上書きには使いません。「選択JSONを保存」では現在の台帳を取得できます。別の台帳は`--selection`、参考SVGの出力先は`--export-svg-dir`で指定します。

点と左右の払いは字形全体を置換しません。Noto輪郭の裁ち落としに接する三次ベジェをde Casteljau分割し、分割点より外側だけを丸い筆端へ置き換えるため、元の曲率とそれ以外の輪郭を保持します。確定したC案は、点で元曲線の外側6%、左払い筆端で外側6%、右払い筆端で片側20%・反対側2.2%だけを置換します。

横画起筆Bは、上下を同じ量だけ張り出させ、白銀比で斜めの筆置きと横画へ収束する長さを決めます。元の横画の上下幅を`w`として、次の順序で設計します。

1. 上下の張り出し量を同じにし、張り出しを含む全高を元の横画幅の`√2`倍、`w√2`とします。したがって上下それぞれの張り出し量は`w(√2−1)/2`です。
2. 上下の張り出し頂点を斜めに結ぶため、両頂点の左右差を`w/√2`とします。頂点間の上下差`w√2`と左右差`w/√2`の比はちょうど`2:1`です。
3. 上下頂点を結ぶ斜線の長さを`c`とすると、`c=w√(5/2)`です。この斜線をさらに`√2`倍した`l=√2c=w√5`を、下側頂点から横画へ収束するまでの水平距離とします。
4. 下側頂点から右へ`l`進んだ位置を下側接点とします。下側曲線は、張り出し頂点と接点を通り、接点で横画下辺へ水平に接する仮想円の弧として描きます。
5. 上側接点は下側接点と同じ`x`座標に置きます。上側頂点は下側頂点より`w/√2`だけ左にあるため、上側の接続距離は`l+w/√2`です。上側も、張り出し頂点と接点を通り、接点で横画上辺へ水平に接する別の仮想円の弧として描きます。

上下の円弧は同じ位置で横画へ収束しますが、接続距離と半径は異なります。下側の寸法から共通の収束位置を決め、上側だけをそこまで延ばすことで、斜めに置いた筆が上下同時に横画へ落ち着く形にします。

はねBは`hook-A.svg`の流れを整理し、左端から深いえぐりと右の立ち上がりまでを連続する曲線にします。折れBは源流明朝の三角右辺を構成する三次ベジェを5%地点で分割し、右側95%と`x=884`まで伸びる制御点をそのまま保持します。左上の斜画起点と、分割点までの三角上端だけを確定ウロコBに似た二段の丸みに置き換えます。

左払い筆端は短い接続線が前後の曲線本体より左下にある場合だけ認識します。`父`・`丈`のように大きな払いが交差する輪郭では、上側の露出端にも同じ`curveTo`・`lineTo`・`curveTo`列がありますが、接続線が曲線本体より上にあるため左払い終端から除外します。左右の払いが一つの閉輪郭に二つの短い接続線を持つ場合は、輪郭開始位置付近の接続線が汎用的な左払い条件を満たしても、短辺と長辺の比、右端への張り出し、前後の接線方向をすべて満たす右払い筆端を優先します。`穴`・`公`・`分`などでは上端の輪郭継ぎ目ではなく、右下の実際の払い端だけを丸めます。

はねBの汎用処理は、短い筆端の後ろに三次ベジェが3本連続し、筆端の太さ方向と払い出し方向がほぼ直交する輪郭だけを対象にします。斜交する内部接続をはねとして扱わず、確定案の深いえぐりは元のはね輪郭が持つ太さ方向の深さまでに収めるため、部品ごとの縦寸法を越えて突出しません。

囲み左下Bは源流明朝の四曲線構造をNotoの囲み幅へ正規化します。囲み右下Bも四曲線構造を保ちますが、右脚が源流明朝と同じ太さまで広がらないよう、下端付近の内側を`x=776`、外側を`x=849`へ置きます。これは同じ基準へ正規化したNotoの`x=778`・`x=846`と、源流明朝の`x=773`・`x=851`の中間で、下部の幅も68ユニットと78ユニットの中間にあたる73ユニットです。

囲み左上Bは源流明朝と同じく、横画から左上の張り出し点までは直線で接続し、左外辺だけを1本の三次ベジェで縦画へ戻します。従来案の右側曲線は削除し、張り出し点を従来案と縦画外辺の中間へ移して、左への膨らみを半分に抑えます。汎用検出では同じ閉輪郭上の左右の長い平行辺、内側の短い接続と曲線、上辺との位置関係に加え、逆向きに巻く内側カウンター輪郭を必須とします。これにより、開いた構造の輪郭を囲み角として扱わず、囲みの左上・左下・右下を一組で確定Bへ置き換えます。

左払い上部Bは、源流明朝の二段の左辺、上端の張り、短い戻りをNotoの斜画幅と方向へ正規化します。輪郭の開始位置をまたぐ最初と最後の曲線鎖から、右上から左下へ向かう平行な両辺、幅に比例する短い上端、接線方向を判定します。`右`・`左`・`区`・`有`のように周囲の構造や傾きが異なる場合も同じ局所条件で検出し、既存要素の編集範囲と重なる候補は適用しません。

起筆Bは白銀比による設計です。縦画幅`w`に対し、左上点を左辺から`w(√2−1)/2`張り出させ、左辺の接点を基準点から下へ`w√5`の位置に置き、仮想円弧で約`3w`かけて収束させます。右上点は右辺から`w(√2−1)`張り出し、独立した短い筆置き曲線で右辺へ戻すため、左右の接続位置は揃えません。汎用処理では検出した縦画幅へ全寸法を等比で写し、短い縦画でも起筆の上下比を圧縮しません。左辺が本来の接点へ届く前に横画や次の輪郭接続へ達する場合は、仮想円弧をその位置で切り、曲率が残ったまま次の線へ接続します。

終筆はNotoの左下端を一つの基準点とし、縦画幅`w`、縦方向、横方向だけから全オンカーブ点とオフカーブ点を導出します。選択可能な`silver`では底部の総張り出しを`w(1−1/√2)`、左右比を`√2:1`とし、最下点は底面幅を`1:(1+√2)`に分ける位置へ置きます。左収束長を`w(1+2√2)`、右収束長を`w(2+√2)`とすると、左右の胴側制御点は基準点から同じ`w(3+√2)/2`の高さに揃います。外端側制御点は各外端と胴接点を通る仮想円弧の接線から求め、胴側制御点だけを収束長の半分まで延ばして長い筆運びを残します。

既定の`traditional`も同じ基準点と4本の三次ベジェを使いますが、総張り出しを`w(1−1/√2)/2`へ半減し、最下点の左右比を`1:√2`へ寄せます。左右の胴側制御点は基準点から`w√2`の高さに揃え、左収束長を`w(3√2−2)`、右収束長を`2w`として、縦画本体を下端近くまで直線に保ちます。短い縦画では選択したプロファイルの必要深さと実際の左右辺長から終筆だけの軸方向倍率を求め、起筆や横画との接続を越えない範囲へ収めます。

比較専用の終筆Dは、`traditional`と同じ収束長と左右の外端高を使い、総張り出しだけを`w(1−1/√2)/3`へ抑えます。側面では軸方向の二つの制御点を収束区間の`1/3`・`2/3`へ等間隔に置き、横方向を`3t²−2t³`で移動させます。これにより側面の横速度は胴接点と外端の両方で0となり、接線は縦画と平行になります。外端から最下点までの左右二曲線は四分楕円として、ハンドル長を各軸距離の`4(√2−1)/3`倍にします。左右外端では縦接線、最下点では水平接線を前後で共有するため、4本の三次ベジェの全接続点が接線連続になります。内側ハンドルの方向を任意の斜線ではなく縦・横の接線条件、長さを四分楕円近似で決める試作です。

ウロコと折れのD案では、Noto Serif JPと源流明朝に加え、[しっぽり明朝](https://github.com/fontdasu/ShipporiMincho)、[Zen Old Mincho](https://github.com/google/fonts/tree/main/ofl/zenoldmincho)、[ひな明朝](https://github.com/google/fonts/tree/main/ofl/hinamincho)、[解星 特ミン](https://github.com/google/fonts/tree/main/ofl/kaiseitokumin)のRegular実輪郭を1000 UPMの同一座標系で比較しました。ウロコはNoto・源流・しっぽり・Zen Oldが、斜めに立ち上がる三角形と非対称な右下がりを共通して持ちます。ひな明朝は低い丸山、解星 特ミンは大きな円弧を使う外れ値でした。折れもNoto・源流・しっぽり・Zen Oldでは左辺が斜めに頂部へ向かい、外側だけが曲線で返ります。ひな明朝の丸い肩と解星 特ミンの直角は比較対象に留め、Dの骨格には採りません。

ウロコDでは横画幅を`w`、白銀比を`s=√2`、円弧半径を`r=w/2`とします。骨格高は`H=(1+s)w=(1+√2)w`を維持し、上りを54°、下りを36°とする黄金角の補角骨格を使います。底辺幅は`U=H(tan 36°+cot 36°)=2H/sin 72°`です。比較用Regularでは`w=33`、`H≈79.669`、上りの水平距離が約`57.883`、下りが約`109.655`、`U≈167.538`となります。丸める前の骨格は、左基点`B₀=(x₀,y)`、頂点`A=(x₀+H/tan 54°,y+H)`、右基点`B₁=(x₀+U,y)`を結びます。頂部での方向転換は90°のままです。横画上辺から上り線へ移る54°の角、頂点の90°の角、横画下辺へ返す右端の144°の角を、すべて同じ半径`r`で丸めます。

折れDは頂部の高さを維持し、上りを54°、下りを36°とする補角の骨格を使います。頂部での方向転換は90°のままです。下り斜辺は、外側の仮想角`C`が横画の中央線上へ達するまで伸ばします。頂点を`A=(xA,yA)`、横画上辺を`yt`、下辺を`yb`、中央を`ym=(yt+yb)/2`とすると、`C=(xA+(yA−ym)/tan 36°,ym)`です。比較用Regularでは`A≈(792.054,738)`、`ym=672`、`C≈(882.895,672)`となり、下り斜辺の水平距離は約`90.841`です。起点・頂部・外端を共通半径`r=w/2`で丸めるため、実輪郭が縦方向へ向く外端は仮想角より`r tan 27°`だけ下に位置します。その後を縦画起筆Bの右側と同じ筆置き曲線で縦画本体へ戻します。戻りの深さは、縦画幅を`v`として`p=v(1−1/√2)`です。三次ベジェの両端を縦方向の接線とし、制御点を各端から`p/(2√2)`の深さへ置くため、外側円弧、戻り曲線、縦画本体の接線が連続します。

`_draw_rounded_corner`は方向転換角を`θ`として、仮想頂点から接点までの距離を`r tan(|θ|/2)`で求めます。三次ベジェのハンドル長は各円弧区間について`4r tan(|θ|/(4n))/3`、`n=ceil(|θ|/90°)`です。ウロコDの144°の右端円弧は72°ずつの2本へ分割し、それ以外も1区間を90°以下に保ちます。これにより全接点で直線と円弧、前後の円弧が同じ接線を共有します。フォント輪郭では円を三次ベジェで近似しますが、半径と接点は指定値から再計算し、制御点を目視調整しません。

起筆検出では縦辺を先に総当たりで組み合わせず、輪郭中の三次ベジェを走査します。Notoの起筆が持つ左上の接続点と右側の2制御点を目印にし、曲線終点を加えた4点について、右への張り出し順、上下比、左上点との戻り量を照合します。ウェイトによって縦画幅と起筆曲線の比率が変わるため、各点を縦画幅の固定範囲へ収めるのではなく、制御点同士と曲線終点の相対比を使います。一致後にだけ前後の局所辺をたどるため、`病`・`水`・`草`・`読`のような片側の分割や、`唐`・`書`のような横画による両側の分割を、長い縦辺の有無と無関係に扱えます。輪郭開始位置をまたぐ戻り線と、`火`の起筆曲線直前にある短い直線も同じ循環セグメント列として検出します。`火`のように起筆側の本体が三次ベジェの場合はde Casteljau分割して元の払い曲線へ戻し、同じ曲線の下端に払い筆端がある場合は両編集を一つの曲線列へ合成して中央の曲率と払いを保持します。

終筆検出も平行な縦辺を先に総当たりせず、Notoの下端にある短い直線と、それに続いて右上へ戻る三次ベジェを走査します。短い直線、第1・第2制御点、曲線終点の横方向の進行と上下比を照合し、一致後にだけ前後の局所辺を取得します。ExtraLight・Regular・Blackで変化する縦画幅へ固定寸法を課さず、曲線終点に対する各点の相対比を使うため、横画や部品との接続で片側辺が短く分割された終筆も同じ形として扱います。起筆と終筆はそれぞれ固有の曲線シグネチャから独立して検出し、一方の一致を理由に他方を追加しません。

確定ウロコBは、Noto Serif JPの`一`（U+4E00）のウロコを基準に、横画上辺から立ち上がる4本の三次ベジェ、内側の直線と丸め、横画下辺へ戻る輪郭を一体で写します。汎用処理ではウロコの横方向の長さと縦方向の高さを別々に正規化し、接続する横画の上下辺を必要な位置で分割して、比較画面で確定したB案の全節点構成へ置き換えます。基準`一`のウロコ領域へ適用した輪郭は確定ウロコBと一致させます。

確定折れBの汎用処理は、折れへ入る右側の縦辺と、折れから戻る横画の位置を維持し、その間を確定案と同じ3本の三次ベジェ、2本の接続直線、非対称な制御点配置へ置き換えます。源流明朝由来の右側曲線は5%分割後の95%を保ち、左側は確定ウロコBと同じ二段の丸みへ接続します。従来は折れ後の横画が140ユニット以上ある場合だけ検出していましたが、方向、山形の点順、縦辺との位置関係も併用することで、40ユニットまでの短い横画を持つ折れを区別します。これにより`典`、`固`の内側、`幅`・`帽`の左側なども折れとして扱います。

フォントへの適用ではSVG、Unicode、字形名、固定の点番号を参照しません。`brush.py`は全漢字輪郭を走査し、方向、長さ、平行度、隣接セグメント、相対位置から縦画の上部起筆と下部終筆、横画起筆、ウロコ、点・左右払い・はねに共通する短い筆端、折れ、囲み三隅、左払い上部を検出します。縦画の起筆はNoto固有の左上点と右側制御点の関係から、終筆はNoto固有の短い直線と右上へ戻る曲線の制御点関係から、それぞれ独立して判定します。起筆と終筆の前後辺は目印の一致後にだけ取得し、横画との接続によって片側辺が分割された縦画も同じ処理へ渡します。起筆の検出だけを理由に終筆処理を加えず、横画や枝へ接続する側辺の切れ目も縦画端として扱いません。輪郭開始位置をまたぐ起筆、点、横画、ウロコは循環セグメントとして検出します。一方、曲線間の短い水平接続は筆端ではないため、払い・はねの丸めから除外します。検出結果からその場で`_CommandEdit`を生成し、同じ輪郭上で候補が重なる場合はウロコの既存曲線を筆端丸めより優先して、重複しない編集だけを適用します。`command_index`は検出結果にだけ保持し、文字別の座標表は持ちません。可変フォントへ拡張する場合は全マスターで同じマッチと編集トポロジーを得られることを確認し、節点を追加する曲線を全マスターで同じ比率に分割して互換性を保つ必要があります。

既定の`nobigoe-build-variable`は、共通カスタマイズ済みCFF2可変フォントを`dist/NobigoeVariableMarks-VF.otf`へ作り、その三次ベジェ輪郭を直接入力として`dist/NobigoeNovelMincho-VF.otf`を派生します。Novel変換は`wght` 200・400・900のpathマスターへ仮名字面と筆端の変形を適用し、標準の200・300・400・500・600・700・900へ補間した輪郭で既存CFF2 VarStoreを置き換えます。独立したかな制作TTFは生成も入力もしません。各可変正本から`dist/NobigoeMincho-<Weight>.otf`と`dist/NobigoeNovelMincho-<Weight>.otf`を実体化した後、可変化されていないLibertinus Serif欧文の取り込み、Novel版の漢字字面調整、リリース用の命名と著作権表示、任意の欧文再ヒントを固定ウェイトだけへ適用します。可変フォントの出力先は`--output`と`--novel-output`、固定ウェイトの出力ディレクトリは`--static-output-dir`で変更できます。`--build-variable-stix OUTPUT`は調整済みSTIX制作VFを明示した場所へ生成し、`--latin-family stix-two-text`は公式STIX可変TTFまたはその制作VFから対象ウェイトの欧文を実体化します。固定取得元は`.cache/font-sources/`へ保存するため、同じソースを使用するビルドでは再ダウンロードやZIPの再展開を行いません。キャッシュ場所は`--cache-dir /path/to/cache`で変更できます。

`--static-weight <Weight>`を指定すると、Nobigoeは指定固定ウェイトだけを実体化し、既定ではNovelも同じウェイトへ追従します。Novelだけを絞る場合は`--novel-static-weight <Weight>`をウェイトごとに繰り返します。省略時は両ファミリーの固定7ウェイトをすべて生成します。固定ウェイトの実体化は利用可能なCPU数に応じて既定で最大4並列になり、`--jobs <N>`で並列数を変更できます。Novel固定版は全漢字輪郭を走査するため先に投入し、短いNobigoe固定版が後続する構成にしています。

`nobigoe-build-essential`は、既定で`dist/NobigoeVariableMarks-VF.otf`を入力し、`ー`、`―`、`〜`、`～`、`〰`だけをUnicodeへ割り当てた`dist/NobigoeEssential-VF.otf`を生成します。`calt`、`ss04`、`ss05`、`vert`、`vrt2`から5文字に到達する字形だけを閉包として保持し、ウェイト軸200–900と7つの名前付きインスタンスを引き継ぎます。入力と出力は`--source`と`--output`で変更できます。

生成順序は、`NotoSerifJP-VF.otf`、のびごえ共通字形・OpenType機能の可変カスタマイズ、カスタマイズ済みNobigoe CFF2からのNovel三次ベジェpathマスター生成、標準7位置を格納したNovel CFF2、両可変正本からの固定ウェイト実体化、固定版専用処理です。符号化済み仮名、縦組字形、既存の濁点・半濁点付き`ccmp`出力はUnicode上の基字を所有者として一度だけ同じNovel変形を受けます。濁点・半濁点、感嘆符・疑問符合字、連結記号とGSUBはNobigoe可変正本からNovel可変正本へ継承し、Novelかなに対応する生成済み濁点・半濁点結合字形は7位置の三次ベジェ輪郭として再合成します。漢字字面調整と欧文取り込みは実体化後に行うため、Noto固定フォントから字形や機能を別に再生成しません。

`nobigoe-build-variable`は固定コミットの`NotoSerifJP-VF.otf`と、固定版でも使用するしっぽり明朝の各ウェイトを取得します。Notoに既存一体字形がない濁点・半濁点列の横組・縦組CFF2 CharString、全角`！`・`？`およびManga1方式の16合字、連続する`ー`、`―`、`〜`（`～`）、`〰`をつなぐ可変字形とGSUB規則を追加します。可変版の明朝感嘆符・疑問符は、ExtraLightだけを18本・6本の少数三次ベジェで再設計し、Light以上はしっぽり明朝Regular、Medium、SemiBold、Bold、ExtraBoldの実輪郭を使用します。しっぽり明朝の14曲線からなる疑問符は、右下内側の1曲線を固定パラメータで5分割し、形を変えず18曲線へ揃えます。直立感嘆符は元から6曲線です。黒みはNotoの全角約物ではなく、Noto Serif JPの`川`・`目`・`田`をY=350、450、550、650で切った縦主線幅の中央値を基準にします。200、300、400、500、600、700、900の基準値は順に44.0、53.6、65.2、80.1、95.0、117.0、144.0 unitsです。疑問符はしっぽり明朝の外周、高さ、筆だまりを保って右太線の内周だけを調整し、感嘆符は下部の細い軸を保って上部テーパーだけを左右から調整します。これによりExtraLightで承認した漢字主線との光学差を全ウェイトへ維持します。下点は元輪郭の上端を保って直径をウェイト別に84〜90%へ縮めた正円とし、5連感嘆符は200-unit間隔で配置して全角セル境界でも間隔を維持します。明朝、回転明朝、ゴシック、回転ゴシックを`aalt`と`ss01`–`ss03`で選択できます。濁点・半濁点の配置と連結記号の輪郭も同じ7ウェイトのレビュー済みマスターを`wght`軸上で補間し、Notoの既存CFF2字形とVariationStoreは維持します。緩い波線は`ss04`、または先頭に`~`を置く方法で選択できます。既定出力は`dist/NobigoeVariableMarks-VF.otf`です。この実験的出力には`nobigoe-build`のその他の約物、欧文・ルビ置換は含みません。
疑問符の下点は本体全体の外接中心ではなく、下へ伸びる線の終端中心へ揃えます。

連結する`ー`・`―`・`〜`・`～`・`〰`の黒みは、固定補正値ではなく、各生成元フォントの`あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん`から求めます。各輪郭の`2 × ink area / outline perimeter`を測り、その中央値を横組・縦組ごとの基準線幅とします。固定版はビルド対象ウェイトの輪郭、可変版は200・300・400・500・600・700・900の各マスター輪郭から個別に基準を計算するため、元フォントの改訂や別の生成元でも本文の黒みに追従します。直線記号は接続方向と直交する軸だけを二分探索で拡縮し、分割後の中間字形が基準値へ一致する倍率を始端・中間・終端へ共通適用します。波線は元字形の位相別線幅比を保ったまま、既定1.5周期、`ss04`の1.25周期、`ss05`の1周期、Manga1の2周期ごとに中間字形の実測値を基準へ揃えます。波線同士の双方向周波数遷移と、`ー`・`―`から既定1.5周期またはManga1の2周期の波線へ出入りする双方向遷移では、両隣の中心線と線幅を滑らかに補間し、境界上では隣接字形の位置・接線・線幅へ一致させます。直線から波線への遷移は境界を中心とした1文字幅に限定し、直線字形の右半分を補間前半、波線字形の左半分を補間後半として生成します。直線字形の左半分は端の筆形状を含む元輪郭、波線字形の右半分は元の断面を維持します。遷移輪郭は整数化前の断面を24区間の三次ベジェへ変換し、接続面の両側へ8 units伸ばします。1文字の波線が直線に挟まれる場合は直線から波形を経て直線へ戻る同一トポロジーの専用輪郭を生成します。横組と縦組は独立して計算するため、種類が切り替わる境界でも線幅差を生じません。`ss04`・`ss05`の波線と直線の間には遷移字形を生成しません。

可変版では、全角`！`・`？`とU+3099・U+309Aの4列、および`♡`・`♥`とU+3099の2列もCFF2可変字形として生成します。全角約物4列は横組・縦組を別字形とし、`ccmp`、全角幅濁点・半濁点用の`liga`、`vert`、`vrt2`へ登録します。ハート2列は固定版と同じ白抜き合成を行った後、7マスターの輪郭を補間互換な三次ベジェ構造へ揃え、既存の私用領域割り当ても維持します。

公開版は[GitHub Releases](https://github.com/ouvill/nobigoe-font/releases)から、Noto版、5文字だけのエッセンシャル版、源暎こぶり明朝版を別々のZIPで配布します。開発中のNovel版は公開版に含めません。

リリース版番号の唯一の正本は`src/nobigoe_font/version.json`です。新しい版ではこのファイルの`version`だけを`N.NNN`形式で更新し、`uv lock`を実行してください。Pythonパッケージのメタデータ、生成フォント、配布ZIP、公開サイト、GitHub Actionsは同じ値を読み取るため、`pyproject.toml`、Webサイト、テスト、説明文へ版番号を転記する必要はありません。

```sh
uv lock
uv lock --check
uv run python -m unittest discover -s tests
```

## 配布ZIPを作成

既定では安定版3ファミリーだけを、フォント、README、OFL、第三者通知、SHA-256マニフェストを含む再現可能なZIPへまとめます。先にNoto版、エッセンシャル版、源暎こぶり明朝版を生成してください。

```sh
uv run nobigoe-package
```

```text
dist/NobigoeMincho-v<version>.zip
dist/NobigoeEssential-v<version>.zip
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

`.github/workflows/release.yml`は`src/nobigoe_font/version.json`と同じ`vN.NNN`タグで起動します。安定版9フォントと開発中のNovel版7フォントを生成し、テスト、OpenType Sanitizer、HarfBuzzで検証します。GitHub Releaseへ添付するのは安定版9フォントを収録した再現可能な3つのZIPと`SHA256SUMS`だけです。次のように正本からタグ名を取得して注釈付きタグをpushするか、GitHub Actionsの「Build and publish release」を同じタグ名で手動実行してください。

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
