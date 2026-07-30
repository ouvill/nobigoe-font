# のびごえ明朝 (Nobigoe Mincho)

Noto Serif JPまたは源暎こぶり明朝を和文ベースに、伸長記号、感嘆符・疑問符合字と異体字、濁点・半濁点付き仮名を追加するフォント生成プロジェクトです。Noto版の既定の欧文はLibertinus Serifの字形とメトリクスを使用します。Noto各ウェイトから小説本文向けの小ぶりなひらがなを生成する`Novel`版も、既存版とは別の明示オプションで提供します。

制作: [Ouvill](https://blog.ouvill.net) · [X / @ouvill](https://twitter.com/ouvill) · [GitHub](https://github.com/ouvill) · [開発を支援](https://github.com/sponsors/ouvill)

Noto版は共通ファミリー名`Nobigoe Mincho`（`のびごえ明朝`）の7ウェイト、源暎こぶり明朝版は`Nobigoe Koburi Mincho`（`のびごえこぶり明朝`）のRegularとして配布します。開発中のNovel版は`Nobigoe Novel Mincho`（`のびごえ小説明朝`）の7ウェイトを明示オプションで生成できますが、通常のGitHub Releaseには含めません。Noto版とNovel版はOpenType/CFF、源暎こぶり明朝版は元フォントと同じTrueType形式です。

![のびごえ明朝とのびごえこぶり明朝の字形一覧。伸長記号、結合濁点・半濁点、感嘆符・疑問符合字、二つのファミリーを掲載](https://nobigoe.ouvill.net/assets/readme-glyphs.png)

## ファミリー構成

| ファミリー | ベース | ウェイト | 形式 | 出力 |
|---|---|---|---|---|
| Nobigoe Mincho | Noto Serif JP（和文）+ Libertinus Serif（欧文） | ExtraLight / Light / Regular / Medium / SemiBold / Bold / Black | OpenType/CFF (`.otf`) | `dist/NobigoeMincho-<Weight>.otf` |
| Nobigoe Novel Mincho（開発中） | Noto Serif JP各ウェイト（和文）+ Libertinus Serif（欧文）、ひらがなをNovel設計へ変換 | ExtraLight / Light / Regular / Medium / SemiBold / Bold / Black | OpenType/CFF (`.otf`) | `dist/NobigoeNovelMincho-<Weight>.otf` |
| Nobigoe Koburi Mincho | 源暎こぶり明朝 | Regular | TrueType (`.ttf`) | `dist/NobigoeKoburiMincho-Regular.ttf` |

3ファミリーの追加機能とUnicode入力は同じです。Noto版は通常の文書用、Novel版は漢字を邪魔しない小説本文用仮名と余白を持つ漢字字面、源暎こぶり明朝版は源暎こぶり明朝由来の小ぶりな仮名を持つ独立ファミリーとして扱います。

### Novel小説本文設計
> [!WARNING]
> Novel版はmain上で統合検証する開発中の実験的ファミリーです。ファミリー名、出力名、既存ビルドの既定値は分離されていますが、字形設計と仕様は正式リリースまで変更される可能性があります。通常の配布ZIPとタグリリースには含まれません。


`--kana-style novel`は、現行Noto版のファミリー名・出力名・既定値を変更せず、別ファミリー`Nobigoe Novel Mincho`を生成します。輪郭は源暎こぶり明朝からコピーせず、出力と同じウェイトの固定Noto Serif JPを変形した派生設計です。「完全なゼロからのオリジナル」ではありません。Noto CJKの著作権表示とSIL Open Font License 1.1は生成フォント内と第三者通知に維持します。

対象ひらがなはNotoソースが収録するU+3041–U+3096とU+309D–U+309Fの89字です。小書き、符号化済み濁点・半濁点付き、`ゔ`、`ゐ`・`ゑ`、反復記号、`ゟ`を含み、追加するU+1B132小書きこ、ひらがなを基字とする`ccmp`出力と全縦組字形も同じ設計群で変換します。結合濁点・半濁点の一体字形は合成後の輪郭全体を一度だけ変換するため、基字と記号の間隔を保ちます。

対象カタカナはU+30A1–U+30FA、U+30FD–U+30FF、U+31F0–U+31FFの符号化済み109字と、ビルド時に追加するU+1B155小書きコです。標準78字、小書き29字、反復記号等3字を漏れなく扱い、カタカナを基字とする`ccmp`出力と全縦組字形も変換します。U+30FB中点、U+30FC長音記号、半角カタカナは仮名字面変換の対象外です。変換対象は横組203 glyph・縦組202 glyphで、符号化済み字形、既存一体字形、生成した濁点・半濁点付き字形を重複なく含みます。ひらがな・カタカナともcmap、既存GSUB/GPOS、1000 units/emの全角送り、各縦字形の縦原点を維持します。

漢字はUnicode 15.1で固定したCJK Unified Ideographs全拡張とCJK Compatibility Ideographsを対象にします。範囲はU+3400–U+4DBF、U+4E00–U+9FFF、U+F900–U+FAFF、U+20000–U+2A6DF、U+2A700–U+2B73F、U+2B740–U+2B81F、U+2B820–U+2CEAF、U+2CEB0–U+2EBEF、U+2EBF0–U+2EE5F、U+2F800–U+2FA1F、U+30000–U+3134F、U+31350–U+323AFです。Noto cmapにある13,736コードポイントが参照する13,477 glyphをseedとし、`aalt`、`jp78`、`jp83`、`jp90`、`locl`、`nlck`、`salt`、`ss01`–`ss20`、`vert`、`vrt2`等をseedからグラフ追跡して、未符号化の異体字492 glyphを加えた重複なし13,969 glyphを変換します。現行ソースの到達出力数／新規追加数は`aalt` 769／492、`jp78` 569／0、`jp83` 380／0、`jp90` 160／0、`nlck` 210／0で、`locl`・`salt`・`ss01`–`ss07`・`vert`・`vrt2`からの追加は0です。`dlig`と`ruby`は漢字異体字ではなく表示・寸法機能なので追跡しません。

漢字輪郭は全7ウェイト共通で1000-unitセル中心(500, 500)を基準に`1000 / 1024 = 0.9765625`倍する純粋な等方アフィン変換です。weight調整は行わず、h/v advance 1000と既存の縦原点・`VORG`を維持します。`々` U+3005、`〆` U+3006、`〇` U+3007、`〻` U+303B、`〼` U+303C、カタカナ、約物、Latin、追加記号は漢字変換の対象外です。対象glyphと保護対象の仮名・約物・Latin・記号・PUAに共有aliasがあれば、輪郭を変更する前にビルドを失敗させます。現行Noto cmapではCJK Radicals Supplement／Kangxi Radicalsの293コードポイントが対象中の290 glyphをaliasするため、cmap不変の条件下で同じ縮小輪郭を表示します。数値と範囲の正本は[`novel_han.py`](src/nobigoe_font/novel_han.py)です。

輪郭縮小の実装はNotoのIdeographs用CID Font DICTを複製し、Private DICTを独立させつつlocal Subrsと対象CharStringバイト列を保持し、複製FDの`FontMatrix`と`FDSelect`割当だけで行います。これにより13,969 glyphを個別展開せず、全ウェイトで元のヒント命令とsubroutine構造を維持します。`glyph_path`と計測CLIはFDごとの相対`FontMatrix`を反映するため、ソース輪郭との比較も実際の描画寸法と一致します。

設計は200（細）、400（標準）、900（太）の3光学マスターを`normal`、懐を持つ`counter`、`small`、`iteration`の4群に分け、300・500・600・700へ補間します。横組の字面横縮率は通常字で0.950→0.940→0.935、縦縮率は0.960→0.950→0.950です。太字のcounter群だけ横0.925としてBlackのカウンターを確保し、小書きと反復記号は通常字より縮小を抑えます。位置基準は横組の(500, 370)、縦組通常字の(500, 370)、縦組小書きの(650, 395)で、0.25 units以上の必要な縦画補正だけを加えます。

カタカナは同じ200・400・900の3光学マスターを、直線主体41字、曲線主体37字、小書き29字、反復記号3字の4群へ分け、残る4ウェイトを補間します。横組マスターの字面横縮率は直線主体で0.950→0.940→0.935、曲線主体で0.950→0.940→0.930、縦縮率は0.960→0.950→0.950です。小書きと反復記号は縮小を抑え、縦組では別マスターで横幅を1.025→1.030→1.035倍へ復元し、小書きだけ(650, 395)を位置基準にします。字別の縦高さ補正は`ハ・シ・ン・チ・ワ・ネ・ケ`へ適用します。数値の正本は[`novel_katakana.py`](src/nobigoe_font/novel_katakana.py)です。

縦組は横組マスターを正本として先に適用し、別の200・400・900マスターと字別補正を二段目に適用します。通常字の横幅復元は1.025→1.030→1.035、counter群のBlackは1.030、小書きは1.000です。RegularでKoburiより高かった25字だけ高さを0.880–0.995倍に抑え、狭い`ぬ・り・ひ・け`はさらに1.030倍、準狭幅5字は1.015倍、もともと広い9字は0.980倍の横幅係数を使います。低かった`あ・す・ゆ・る`と全小書きは高さを変えません。補正強度は細0.9・標準1.0・太0.9で補間し、ExtraLightの細線とBlackのカウンターを守ります。縦送り1000と`VORG`は不変です。数値の正本は[`novel.py`](src/nobigoe_font/novel.py)の`NOVEL_MASTER_PROFILES`、`NOVEL_VERTICAL_MASTER_PROFILES`、`NOVEL_VERTICAL_HEIGHT_CORRECTIONS`、`NOVEL_VERTICAL_WIDTH_CORRECTIONS`です。

縦組の黒みは、Regular基本46字について各書体内平均へ正規化したNovel/Koburi比を全字走査し、1.040以上をstrong、1.025以上をmoderateとして補正します。strongは`か・き・け・せ・は・も`、moderateは`た・ち・に・み・む`です。`な`は1.085でしたが、-1.15 unitsを超える補正で小輪郭を失うためfragile群として独立させます。stem補正の200→400→900マスターはstrongが-0.75→-1.50→-0.75、fragileが-0.50→-1.00→-0.50、moderateが-0.50→-0.75→-0.50 unitsです。符号化済み濁点・半濁点字と`ccmp`出力は基字群を継承し、記号を痩せさせないため合成済み輪郭へ2/3強度で一度だけ適用します。数値の正本は`NOVEL_VERTICAL_STEM_GROUPS`と`NOVEL_VERTICAL_STEM_MASTER_PROFILES`です。

実測は[`nobigoe-measure-kana`](src/nobigoe_font/novel_metrics.py)で再現できます。89字の平均を1000 units/emへ正規化すると、RegularのNotoは字面0.7531×0.7684、ink area 0.1278、代表漢字9字に対するink比0.6807、源暎こぶり明朝は0.7064×0.7200、0.1113、0.6202、Novelは0.7131×0.7337、0.1162、0.6490です。Novelの同ink比はExtraLight 0.6708、Black 0.6580で、ウェイト端でも本文濃度の比率をほぼ一定に保ちます。

カタカナ109字のRegular平均は、横組でNotoの字面0.714492×0.692168・ink area 0.097757に対してNovelが0.674508×0.659149・0.088418で、比率は94.40%・95.23%・90.45%です。Koburiの0.664157×0.646458・0.086242に対してNovelは幅+1.56%、高さ+1.96%、ink +2.52%です。Notoに対するNovelの横組字面幅比／高さ比／ink比はExtraLightで95.64%／96.24%／94.93%、Blackで93.62%／95.12%／88.99%となり、細字の線を保ちながら太字のカウンターを確保します。代表漢字9字に対するカタカナink比はExtraLight 0.5002、Regular 0.4936、Black 0.5234です。縦組でもNoto比は全ウェイトで幅95.30–96.79%、高さ94.23–95.44%、ink 90.10–95.48%に収まります。

代表漢字`永漢字山川雨月語本`のRegular平均は、変換前Noto／Novelの字面0.888778×0.898778・ink area 0.187824・fill 0.234243に対し、変換後Novelが0.867947×0.877713・0.179122・0.234243です。源暎こぶり明朝の0.867188×0.878255・0.179431・0.234725との差はwidth +0.09%、height -0.06%、ink -0.17%、fill -0.21%です。計測JSONの比較セクションにも代表漢字9字のmean／median比を出力します。


基本46字のRegular縦字形では、Novelと源暎こぶり明朝の高さMAEが0.018139emから0.009811em、中央値絶対誤差が0.015500emから0.006297emへ改善しました。width/heightのaspect MAEは0.056932から0.024008、中央値絶対誤差は0.043717から0.022450です。調整後の平均はKoburiの0.7016×0.7345・aspect 0.9788に対してNovelが0.6953×0.7290・0.9738です。横組90字の輪郭と`hmtx`は調整前と同一です。

同じ46字の相対黒みMAEは0.029699から0.022134、中央値絶対誤差は0.022802から0.014402へ改善しました。Regularの`か・が・は・ば・ぱ`のink areaはそれぞれ0.126261→0.121131、0.141355→0.137004、0.141028→0.135520、0.154692→0.150306、0.156831→0.152426です。Koburi比は1.008、1.002、1.011、1.002、1.003となり、bbox高さの変化は最大1 unitです。補正後の相対黒み上位は、輪郭保護を優先した`な`1.065、`せ`1.035、`よ`1.032、`を`1.030、`き`1.030です。

```sh
uv run nobigoe-measure-kana --strict --json \
  --output dist/novel-kana-metrics.json \
  NotoR=.cache/font-sources/NotoSerifJP-Regular.otf \
  KoburiR=.cache/font-sources/GenEiKoburiMin6-R.ttf \
  NovelR=dist/NobigoeNovelMincho-Regular.otf
```

縦組の`vert`/`vrt2`置換後の輪郭を測る場合は、同じコマンドへ`--vertical`を追加します。

## 機能

### 連続する伸長記号

次の文字を2文字以上続けると、OpenTypeの `calt`（Contextual Alternates）で始端・中間・終端の字形へ置換します。

| 文字 | Unicode | 動作 |
|---|---:|---|
| `ー` | U+30FC | 長音記号を連結 |
| `―` | U+2015 | HORIZONTAL BARを連結 |
| `〜` | U+301C | WAVE DASH（波ダッシュ）を連結 |
| `～` | U+FF5E | U+301Cと同じWAVE DASH字形を使用 |
| `〰` | U+3030 | Manga1方式のWavy Dashを連結 |

横組と縦組の両方に対応しています。`〜`と`～`は1文字あたり3半波で、連続時の外側の始端・終端には単独字形と同じ約50 unitsの余白、線幅テーパーと0.3半波分の追加位相を持たせています。追加位相の補正は字形中央で行うため、細くなる端部の波長と曲率は通常部分と同じです。

生成する波線の線幅は、元グリフの山・谷と中央線を横切る位置でそれぞれ測定し、位相に応じて補間します。連続線の黒みを抑えるため、斜め部分の線幅変化は元グリフとの差の30%を適用します。Noto版Regularでは山・谷が約49 units、中央線との交点が約56 unitsです。外側の線幅テーパーには、この位相別線幅へ滑らかな縮小率を掛けます。

`ss04`を有効にすると、2文字以上連続する`〜`と`～`を1文字あたり2.5半波（1.25周期）のゆるやかな波形へ切り替えます。位相の異なる4字形を順番に使用し、外側でも位相を補正しないため、始端から終端まで波長は一定です。開始位相は元グリフの輪郭に合わせて-0.25半波とし、連続時の外側には既定版と同じ余白と線幅テーパーを適用します。単独字形は`ss04`の有無にかかわらず、既定字形を使用します。

連続する `ー` は、元字形の30%位置と70%位置で中心線を測り、中央を固定したアフィンシアーで右上がりの傾斜だけを打ち消してから始端・中間・終端へ分割します。端の筆形状は残しつつ、中央の直線と両端が同じ軸に見えるようにしています。単独の `ー` は元字形のままです。

`〰`はAdobe-Manga1のGSUB構造に合わせ、中央線から始まって中央線へ戻る1文字4半波の反復可能な中間字形を使用します。振幅、基準線、位相に応じた線幅、山頂の曲率は`〜`と揃えています。単独字形の両端と連続時の外側の始端・終端には約50 unitsの余白、1/6文字幅のテーパーと0.3半波分の追加位相を持たせています。

### Manga1方式の濁点・半濁点付き仮名

Adobe-Manga1-0が規定する濁点77列と半濁点114列の計191列を、OpenTypeの `ccmp` で1グリフへ置換します。正式な入力には結合濁点（U+3099）または結合半濁点（U+309A）を使用します。入力互換のため、全角幅濁点（U+309B）または全角幅半濁点（U+309C）を基字に続けた場合も、既定で有効な `liga` により同じ一体字形へ置換します。`liga` を無効にすると全角幅記号だけが基字と分離し、単独のU+309B・U+309Cは設定にかかわらず変更しません。

```text
あ゙ ぁ゙ な゙ ん゙ ア゙ ン゙
か゚ あ゚ さ゚ な゚ ま゚ セ゚ ツ゚ ㇷ゚
ー゙
```

Noto版では、Noto Serif JPに一体字形がある24列は既存輪郭を使用し、残る167列は基字と結合記号の輪郭を一体化します。Regularで字ごとに決めた配置を基準に、ほかの6ウェイトも全191列の横組・縦組を目視し、ウェイト専用JSONへ個別調整を記録しています。生成時の自動移動は行いません。源暎こぶり明朝版では、同フォントに既存する88列の一体字形を優先し、残る103列には同フォントの既存字形から測定して目視調整した専用配置を使用します。小書き仮名では記号を縮小して基字へ近づけ、横組・縦組それぞれに専用字形を生成します。

源暎こぶり明朝が一体字形を持つ濁点74列・半濁点14列の計88列には、同フォントと互換性のある私用領域U+E082–U+E0D9も割り当てています。たとえばU+E082を直接入力しても、`あ` + U+3099と同じ字形になります。OpenTypeの結合処理に対応しないアプリで使用できます。

長音 `ー`（U+30FC）に結合濁点を続けた字形も、横組・縦組それぞれの一体字形へ置換します。源暎こぶり明朝版は元フォントの既存字形を保持し、Noto版はその相対配置を1000 units/emへ正規化して各ウェイトの `ー` と濁点から生成します。完成字形は両ファミリーとも私用領域U+E0DBで直接入力できます。

白ハート `♡`（U+2661）と黒ハート `♥`（U+2665）に結合濁点を続けた2列も一体字形へ置換します。私用領域の基字U+E064・U+E065でも同じ結合が働き、完成字形はそれぞれU+E0DC・U+E0DDで直接入力できます。源暎こぶり明朝版は、通常のハート、私用領域の基字、完成字形、4つの`ccmp`入力を含めて元フォントの既存字形と対応を変更せず保持します。Noto版だけは各ウェイトのハートと濁点から字形を生成し、配置後の濁点2画の中心間距離の1/3を白抜き半径として、濁点を16方向へ拡張した範囲をハートから差し引きます。

全角感嘆符 `！`（U+FF01）と全角疑問符 `？`（U+FF1F）にも、結合濁点または結合半濁点を続けた4列を用意しています。`ccmp`で全角1文字幅の一体字形へ置換し、横組・縦組それぞれの専用字形を使用します。Noto版7ウェイトと源暎こぶり明朝版Regularについて、4列すべての配置を個別に記録しています。

```text
！゙ ！゚ ？゙ ？゚
```

元フォントにない場合、`𛄲`（U+1B132、Hiragana Letter Small Ko）と `𛅕`（U+1B155、Katakana Letter Small Ko）は、ベースフォントの `こ` と `コ`を既存の小書き仮名に合わせて縮小・配置した横組・縦組字形として追加します。

通常のかな、数字、約物と、Manga1が規定する半濁点付き14列（`ㇷ゚`、`か゚`、`き゚`、`く゚`、`け゚`、`こ゚`、`カ゚`、`キ゚`、`ク゚`、`ケ゚`、`コ゚`、`セ゚`、`ツ゚`、`ト゚`）は、OpenTypeの `ruby` で源暎こぶり明朝のルビ専用字形へ置換します。Noto版には源暎こぶり明朝の288字形と配置を1000 units/emへ正規化して移植します。線幅は、源暎こぶり明朝で97.7%に小さく設計された通常仮名を比較時だけ原寸へ戻して輪郭面積を測り、各Notoウェイトとの差分だけをルビ字形へ適用します。ルビ字形は拡大縮小せず、小サイズ向けの抑揚を維持します。小書き仮名、小書きコ、`ㇷ゚`などには縦組専用ルビ字形も用意しています。

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

単独の `！` と `！！`、`！！！`、`！！！！` には、しっぽり明朝に収録された直立字形U+E000、U+E002、U+E007、U+E0E3を使用します。`！！！！！` はU+E002から直立感嘆符の構成輪郭を抽出し、1文字セルへ再配置して生成します。2記号の `？？`、`？！`、`！？` は、それぞれ既存合字 `⁇`（U+2047）、`⁈`（U+2048）、`⁉`（U+2049）の輪郭を使用します。その他の3記号以上では、直立感嘆符と既存合字から抽出した疑問符を再配置します。横組・縦組とも記号はセル内で横並びになります。半角ASCIIの `!` と `?` は合字化しません。

単独の全角 `！`・`？` と16通りの合字には、明朝、右へ12度傾けた明朝、ゴシック、右へ12度傾けたゴシックの4字形を用意しています。既定は明朝です。`ss01`、`ss02`、`ss03` でそれぞれ斜体明朝、ゴシック、斜体ゴシックへ切り替えられ、3異体字は `aalt` にも登録されています。単独の明朝 `！` と2〜4連の明朝感嘆符合字、および単独の明朝 `？` はしっぽり明朝の字形を使用し、その他の明朝合字もしっぽり明朝をもとに全角1文字幅へ収めています。ゴシック字形はNoto Sans JPを使用します。Noto版の明朝合字はMedium、SemiBold、Bold、Blackでそれぞれしっぽり明朝Medium、SemiBold、Bold、ExtraBoldを使用します。しっぽり明朝に400未満がないため、ExtraLight、Light、RegularはRegularを使用します。そのままでは和文との太さが揃わないため、しっぽり明朝の単独字形と全合字には、Noto Serif JPの全角 `！`・`？`を基準にした-13〜+11 unitsのウェイト別輪郭補正を適用します。

この機能は[Adobe-Manga1-0](https://github.com/adobe-type-tools/Adobe-Manga1)の合字シーケンス集合、異体字構成、GSUB規則を参考にしています。Adobe-Manga1のCIDコレクション全体を実装するものではありません。

## 使用フォント

| 用途 | フォント | バージョン |
|---|---|---:|
| Noto版の本文、長音、ダッシュ、波線 | [Noto Serif JP](https://github.com/notofonts/noto-cjk) | 2.003 |
| Noto版の既定欧文 | [Libertinus Serif](https://github.com/alerque/libertinus) | 7.051 |
| 比較用欧文候補 | [STIX Two Text](https://github.com/stipub/stixfonts) | 2.13 b171 |
| 比較用欧文候補 | [Source Serif 4](https://github.com/adobe-fonts/source-serif) | 4.005 |
| 源暎こぶり明朝版の本文、長音、ダッシュ、波線、および両版のルビ専用字形 | [源暎こぶり明朝](https://okoneya.jp/font/genei-koburimin.html) | 6.1 |
| Manga1感嘆符・疑問符合字の記号輪郭 | [Shippori Mincho OTF 5ウェイト（しっぽり明朝）](https://fontdasu.com/shippori-mincho/) | 3.300 |
| Manga1感嘆符・疑問符合字のゴシック異体字 | [Noto Sans JP](https://github.com/notofonts/noto-cjk) | 2.004 |

取得元、バージョン、SHA-256、著作権表示は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) に記載しています。

## ビルド

### 必要環境

- Python 3.13
- `uv`
- `fonttools`
- `skia-pathops`
- OpenType SanitizerとHarfBuzz（検証する場合）
- AFDKOの`otfautohint`（`--autohint`を使用する場合）

Python依存関係をuvで同期します。Python 3.13を使用します。

```sh
uv sync
```

`--autohint`を使用する場合もAFDKOは通常依存に含まれるため、`uv run`から`otfautohint`を実行できます。通常のビルドには不要です。

### コード構成

Pythonコードは`src/nobigoe_font/`へ集約し、CLI、生成パイプライン、フォント操作、設定データをインストール可能な1パッケージとして管理しています。

| モジュール | 責務 |
|---|---|
| `cli.py` | `nobigoe-build`の引数検証と入出力の解決 |
| `pipeline.py` | フォント生成手順のオーケストレーション |
| `profiles.py` / `sources.py` | ファミリー、ウェイト、固定取得元、SHA-256検証済みキャッシュ |
| `marks.py` / `mark_positions/` | 濁点・半濁点の対象、配置型、JSON設定の検証 |
| `geometry.py` / `operations.py` | 輪郭変換、cmap、CFF／TrueType、欧文レイアウトの操作 |
| `punctuation.py` / `features.py` | 感嘆符・疑問符合字の合成とOpenType機能の生成・結合 |
| `metadata.py` / `hinting.py` / `release.py` | 命名、欧文再ヒント、配布ZIP作成 |
| `novel.py` / `novel_katakana.py` / `novel_han.py` / `novel_metrics.py` | Novelひらがな・カタカナの3マスター設計、Unicode 15.1 Han集合と等方縮小、字面・ink・カウンター計測 |

### 自動取得して生成

引数を省略すると、欧文にLibertinus Serifを使用するRegularのNoto版を生成します。`--weight`には`ExtraLight`、`Light`、`Regular`、`Medium`、`SemiBold`、`Bold`、`Black`を指定できます。Noto Serif JP、Noto Sans JP、STIX Two Textは固定コミットまたはタグ、Libertinus Serif、Source Serif 4、源暎こぶり明朝、対応するしっぽり明朝ウェイトは公式配布アーカイブから取得し、すべてSHA-256を検証します。初回に取得したファイルと展開済みフォントは`.cache/font-sources/`へ保存し、2回目以降はSHA-256が一致するローカルファイルを再利用します。取得先、ウェイト対応、ハッシュは`src/nobigoe_font/profiles.py`へ集約しています。

Libertinus Serifの直立体はRegular・Semibold・Boldの3ウェイトです。和文と欧文の高さを厳密に追従させて横幅まで変形するのではなく、Noto Serif JPの和文とおおむね高さが揃う等方拡大を実マスターごとに固定しています。Regular由来のExtraLight・Light・Regular・Mediumは1.119倍、Semiboldは1.129倍、Bold由来のBold・Blackは1.138倍です。同じマスターから作るウェイトでは輪郭と送り幅に同じ倍率を使い、個々の欧文字形の送り幅を共通化することで、拡大率に由来する文字列幅の逆転をなくしています。そのうえで細い横画をほぼ保ち、太い縦画を中心に-13〜+6 unitsのウェイト別輪郭補正を行います。同じ変換を通常字形、`ccmp`・`locl`異体字、標準合字へ適用します。

欧文ソースからはBasic Latin、Latin-1 Supplement、Latin Extended-A/B、Combining Diacritical Marks、Latin Extended Additionalと、欧文組版で使うダッシュ、引用符、分数スラッシュ、マイナス記号などを取り込みます。Unicodeに直接割り当てられた字形だけでなく、`ccmp`、`locl`、`liga`、`dlig`、`frac`、`lnum`、`onum`、`pnum`、`tnum`、`subs`、`sups`、`zero`などのGSUB出力字形、`kern`、`mark`、`mkmk`のGPOS、GDEFの字形クラスとMarkAttachClassも同じ倍率・ベースライン補正で移植します。和文ソース側の縦組・仮名・約物機能は維持します。

`--autohint`を指定すると、生成後にAFDKO `otfautohint`を実行します。処理対象は今回取り込んだ欧文字形だけに限定し、Noto Serif JP由来の和文字形の既存ヒントには触れません。`otfautohint`が見つからない場合はエラーにして、未ヒントの成果物を正常終了として扱いません。

`--latin-family`では`noto`、`libertinus`、`stix-two-text`、`source-serif-4`を選択できます。既定の`libertinus`は従来の全7ウェイト設定を保持します。`noto`はNoto Serif JPの欧文字形を置換しません。STIX Two TextはネイティブソースがあるRegular、Medium、SemiBold、Boldを対象とし、1.110倍で取り込みます。Source Serif 4は可変フォントを`opsz=20`と各Nobigoeウェイトの`wght=200–900`で実体化し、1.088倍で取り込みます。比較候補の倍率はRegularの大文字高をNoto Serif JPへ揃えた初期値です。

```sh
# Noto版Regular
uv run nobigoe-build

# 取り込んだ欧文字形だけをAFDKOで再ヒント
uv run nobigoe-build --autohint

# Noto版の全7ウェイト
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --weight "$weight" --autohint
done

# Novel小説仮名版の全7ウェイト
for weight in ExtraLight Light Regular Medium SemiBold Bold Black; do
  uv run nobigoe-build --kana-style novel --weight "$weight" --autohint
done

# 源暎こぶり明朝版Regular
uv run nobigoe-build --base koburi

# Regularの欧文候補を比較用ディレクトリへ生成
for latin in noto libertinus stix-two-text source-serif-4; do
  uv run nobigoe-build \
    --latin-family "$latin" \
    --output "dist/comparison/NobigoeMincho-Regular-$latin.otf"
done
```

既定ビルドの出力は`dist/NobigoeMincho-<Weight>.otf`と`dist/NobigoeKoburiMincho-Regular.ttf`です。`--kana-style novel`の出力は`dist/NobigoeNovelMincho-<Weight>.otf`で、既存配布名を上書きしません。`--output`を省略して既定以外の欧文候補を指定した場合は、`dist/comparison/<PostScript名>-<Latin family>.otf`へ出力します。固定取得元は`.cache/font-sources/`へ保存するため、同じソースを使用するビルドでは再ダウンロードやZIPの再展開を行いません。キャッシュ場所は`--cache-dir /path/to/cache`で変更できます。

公開版は[GitHub Releases](https://github.com/ouvill/nobigoe-font/releases)から、Noto版と源暎こぶり明朝版を別々のZIPで配布します。開発中のNovel版は公開版に含めません。

### 配布ZIPを作成

既定では安定版2ファミリーだけを、フォント、README、OFL、第三者通知、SHA-256マニフェストを含む再現可能なZIPへまとめます。先にNoto版と源暎こぶり明朝版を生成してください。

```sh
uv run nobigoe-package
```

```text
dist/NobigoeMincho-v1.033.zip
dist/NobigoeKoburiMincho-v1.033.zip
```

ローカル検証用にNovel版ZIPも必要な場合だけ、Novel全7ウェイトを生成してから明示的に追加します。このオプションはGitHub Releaseでは使用しません。

```sh
uv run nobigoe-package --include-experimental
```

```text
dist/NobigoeNovelMincho-v1.030.zip
```

### GitHub Releaseを公開

`.github/workflows/release.yml`は`src/nobigoe_font/profiles.py`の`VERSION_NUMBER`と同じタグ（例: `v1.033`）で起動します。安定版8フォントと開発中のNovel版7フォントを生成し、テスト、OpenType Sanitizer、HarfBuzzで検証します。GitHub Releaseへ添付するのは安定版8フォントを収録した再現可能な2つのZIPと`SHA256SUMS`だけです。`v*`タグをpushするか、GitHub Actionsの「Build and publish release」を同じタグ名で手動実行してください。

### ローカルの元フォントを使用

```sh
uv run nobigoe-build \
  --source /path/to/NotoSerifJP-Regular.otf \
  --latin-source /path/to/LibertinusSerif-Regular.otf \
  --punctuation-source /path/to/ShipporiMincho-OTF-Regular.otf \
  --sans-source /path/to/NotoSansJP-Regular.otf \
  --output dist/NobigoeMincho-Regular.otf
```

`--source`、`--latin-source`、`--punctuation-source`、`--sans-source` の一部だけを指定した場合、指定しなかったフォントだけを自動取得します。`--latin-source`はNoto版だけに適用され、`--latin-family`で選択したプロファイルの倍率・補正・可変軸設定を使用します。`source-serif-4`へローカルファイルを指定する場合は`wght`と`opsz`を持つ可変フォントが必要です。`--latin-family noto`と`--latin-source`は併用できません。Noto Serif CJKのTTCを入力する場合は `--face` でフェイス番号を指定できます。源暎こぶり明朝版へローカルファイルを渡す場合は`--base koburi --source /path/to/GenEiKoburiMin6-R.ttf`とします。

明示したローカルファイルはキャッシュより優先します。指定しなかった取得元だけキャッシュを検索し、正しいSHA-256のファイルがなければダウンロードします。キャッシュ内の不完全または不正なファイルは一時ファイルへ再取得し、検証成功後に置換します。

しっぽり明朝はOTF版とTTF版のどちらも `--punctuation-source` に指定できます。明示したファイルはすべての明朝合字に使用されます。既定の自動取得ではNobigoeのウェイトに対応するOTF版を選び、Noto版ではCFF、源暎こぶり明朝版ではTrueTypeの輪郭形式へ追加字形を変換します。

### テスト

生成設定、命名、固定取得元とTrueType字形追加処理の単体テストを実行します。

```sh
uv run python -m unittest discover -s tests -v
```

### 濁点・半濁点の位置を調整

共通の基準配置191列は、字種と記号ごとの4ファイルへ分割しています。源暎こぶり明朝版の専用レイヤーと、感嘆符・疑問符4列のファミリー・ウェイト別配置も同じディレクトリで管理します。

```text
src/nobigoe_font/mark_positions/hiragana_dakuten.json
src/nobigoe_font/mark_positions/hiragana_handakuten.json
src/nobigoe_font/mark_positions/katakana_dakuten.json
src/nobigoe_font/mark_positions/katakana_handakuten.json
src/nobigoe_font/mark_positions/koburi.json
src/nobigoe_font/mark_positions/punctuation.json
```

各字の `horizontal` と `vertical` は `[scale, x, y, rotation]` です。`scale` は結合記号の等方倍率、`x` と `y` は拡大後の平行移動量で、正の値は右・上へ移動します。`rotation` は度数法の回転角で、正の値は反時計回りです。回転の中心には `scale`、`x`、`y` 適用後の記号輪郭のバウンディングボックス中心を使うため、角度を変えても記号の中心位置は動きません。`nobigoe-build`は共通4ファイルの記号種、キー集合、配列長、有限値、正の倍率を検証し、191列の不足や重複があれば生成を停止します。収録値では濁点だけを文字ごと・横縦別に光学調整し、半濁点は回転させていません。Noto版で生成する167列は、実際のウェイトの輪郭で基字との交差も検査します。交差時は記号の大きさを変えず、基字と記号の中心関係から求めた上・横・斜めの外向き候補を比較し、縦メトリクス内で輪郭が離れる最短距離の移動を採用します。

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

Noto Serif JPに既存一体字形がある24列は元の輪郭と縦組字形を優先します。該当列にも完全な191キー集合を検証するための設定値がありますが、生成輪郭には適用されません。U+31F7 `ㇷ` + U+309Aもこの24列に含まれます。

## 紹介サイト

紹介サイトのコードと開発設定は`website/`にまとめています。リポジトリ直下のフォント生成処理とは独立しています。

```sh
cd website
npm ci
npm run dev
```

`website/`内で`npm run check`を実行するとAstroの型検査、`npm run build`を実行すると`website/site-dist/`への静的ビルドを行います。

かな比較`/compare/`は`npm run dev`でだけ有効になる開発用ページです。`npm run build`の静的成果物、公開ナビゲーション、GitHub Pagesには含めず、PagesワークフローもNovel比較用Webfontを生成しません。

公開サイトは <https://nobigoe.ouvill.net/> です。`.github/workflows/pages.yml`が`main`へのpushごとに最新GitHub Releaseのフォントを取得し、Webfontを生成してAstroの成果物をGitHub Pagesへ配信します。

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

## OpenType機能

| feature | 用途 |
|---|---|
| `ccmp` | 全角感嘆符・疑問符合字と濁点・半濁点付き仮名 |
| `liga` | 全角幅濁点・半濁点を既存の一体字形へ置換 |
| `aalt` | 全角感嘆符・疑問符および合字の3異体字を列挙 |
| `ss01` | 全角感嘆符・疑問符および合字を斜体明朝へ置換 |
| `ss02` | 全角感嘆符・疑問符および合字をゴシックへ置換 |
| `ss03` | 全角感嘆符・疑問符および合字を斜体ゴシックへ置換 |
| `ss04` | 連続する`〜`・`～`を1文字1.25周期のゆるやかな波形へ置換 |
| `ruby` | Manga1の半濁点付きルビ14字形へ置換 |
| `calt` | 連続する長音・ダッシュ・波線の始端／中間／終端置換 |
| `vert` / `vrt2` | 縦組用の伸長記号、濁点・半濁点付き仮名、`ㇷ゚`ルビ字形 |

一般的なシェーピングエンジンでは `ccmp`、`liga`、`calt` は既定で有効です。アプリケーション側で `liga` を無効にするとU+309B・U+309Cは全角幅の独立字形になり、結合文字U+3099・U+309Aの `ccmp` は維持されます。ただし、欧文の `fi`・`fl` などの標準合字も同時に無効になります。`calt` を無効にすると、伸長記号の自動連結は行われません。

CSSでは、たとえば `font-feature-settings: "liga" 0;` で全角幅濁点・半濁点を分離し、`font-feature-settings: "ss03" 1;` で全角感嘆符・疑問符を斜体ゴシックへ、`font-feature-settings: "ss04" 1;` で`〜`・`～`を1文字1.25周期の波形へ、`font-feature-settings: "ruby" 1;` で対象の半濁点付き仮名をルビ字形へ切り替えられます。

## ライセンス

生成フォントに取り込まれるNoto Serif JP、Libertinus Serif、源暎こぶり明朝、Noto Sans JP、しっぽり明朝は、いずれもSIL Open Font License 1.1で提供されています。本プロジェクトのフォント関連ファイルと生成フォントも [`OFL.txt`](OFL.txt) の条件に従います。

第三者フォントの著作権表示と改変内容は [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) を参照してください。生成フォントのファミリー名は元フォントと区別し、`Noto`の名称を派生フォント名に残さない `Nobigoe Mincho`（のびごえ明朝）に変更しています。

本プロジェクトはAdobe、Google、Noto Project、Libertinus Project、またはShippori Mincho Projectによる公式配布物ではありません。`Noto`はGoogle LLCの商標です。各名称は出典と互換性を明示する目的でのみ使用しています。
