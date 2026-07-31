# Third-Party Notices

`Nobigoe Mincho`（のびごえ明朝）、`Nobigoe Novel Mincho`（のびごえ小説明朝）、`Nobigoe Koburi Mincho`（のびごえこぶり明朝）は、次の第三者フォントから輪郭とメトリクスを取り込んだ派生フォントです。STIX Two TextとSource Serif 4は、`--latin-family`で明示した比較ビルドだけに取り込みます。

## Noto Serif JP

- Project: [Noto CJK](https://github.com/notofonts/noto-cjk)
- Version: `2.003`
- Commit: [`9b0f1436e455d902de067a2501422e5dc71ad16b`](https://github.com/notofonts/noto-cjk/commit/9b0f1436e455d902de067a2501422e5dc71ad16b)
- Source directories: `Serif/SubsetOTF/JP/`, `Serif/Variable/OTF/Subset/`
- Copyright: `Copyright 2017-2024 Adobe (http://www.adobe.com/). Noto is a trademark of Google Inc.`
- License: SIL Open Font License 1.1

| Source file | SHA-256 |
|---|---|
| `NotoSerifJP-ExtraLight.otf` | `a5056bf9b22a624b62115e9ad242879492179fe6f0b45ce5932967eb20295d5e` |
| `NotoSerifJP-Light.otf` | `54e6b0fa70430987a6c12001f128812f37fc315d899cb1d964395ab6450bb977` |
| `NotoSerifJP-Regular.otf` | `2c9a12dbd4f2408c4610c7ee84a108b62d7236c3775baed618c64d9cb44b2f04` |
| `NotoSerifJP-Medium.otf` | `f3a906cadd27f812a8b4b18618fa750928e65339fb372bd3f825f24e3271180b` |
| `NotoSerifJP-SemiBold.otf` | `116d06c2b11ceba33ccb3f8c9eb1c86aba3d5761a1199fd37f74e83365e7a53d` |
| `NotoSerifJP-Bold.otf` | `1e03488a0d5e819f07fcd74f54703a7961ba466d3ae900f8a2a730541e6d4543` |
| `NotoSerifJP-Black.otf` | `b7197366b775ccb6cd3473b7b09f2c5759a2fdfdbfedf975029203828d0ad386` |
| `NotoSerifJP-VF.otf` | `39701fd096bc51204a8444c6c2659f007b29674a13eb62ddfa470638fe8179cd` |
| `NotoSerifJP-VF.ttf` | `99999f906b3793c7c97661a05ef9d53488d488604683b308c756d084b71df7d1` |

### 使用箇所と改変

各ウェイトを対応する`Nobigoe Mincho`と`Nobigoe Novel Mincho`の和文ベースとして使用しています。Novel版のひらがなは源暎こぶり明朝の輪郭をコピーせず、対応する同ウェイトのNoto Serif JP輪郭を4字形群・3光学マスターの異方性縮小、位置、細ウェイト縦画補正で変形します。縦組は同じNoto由来輪郭へ独立した3光学マスターと字別の高さ・横幅・縦画黒み補正を追加し、源暎こぶり明朝は寸法と黒みの比較基準としてだけ使用します。U+3041–U+3096、U+309D–U+309F、追加するU+1B132、ひらがな`ccmp`出力、全縦組対応字形が仮名変換の対象です。さらにNovel版では、Unicode 15.1で固定したCJK Unified Ideographs全拡張とCJK Compatibility IdeographsのうちNoto cmapにある13,477 glyph、およびそのglyphから異体字・旧字体・新字体・言語形・縦組のGSUB機能をグラフ追跡して到達する未符号化492 glyphを、1000-unitセル中心(500, 500)基準で`1000 / 1024 = 0.9765625`倍へ等方縮小します。`々`・`〆`・`〇`・`〻`・`〼`、カタカナ、約物、Latin、追加記号、`dlig`・`ruby`出力は漢字縮小の対象外です。h/v advance、`VORG`、cmap、既存GSUB/GPOS/GDEFを維持します。欧文字形とそのメトリクスは選択した欧文プロファイルへ置換するか、`--latin-family noto`ではNoto Serif JPのまま保持します。伸長記号、Manga1方式の感嘆符・疑問符合字、濁点・半濁点付き仮名、ルビ、小書きコを追加し、ファミリー名、PostScript名、バージョン、著作権・Noticeメタデータを元フォントと区別できる名前へ変更しています。

実験的な`nobigoe-build-variable`では`NotoSerifJP-VF.otf`の既存CFF2 Variationを維持し、Notoにない濁点・半濁点付き仮名の横組・縦組CharString、Manga1 PUA、GSUB規則を追加します。全角感嘆符・疑問符とManga1方式の16合字および4異体字は、しっぽり明朝・Noto Sans JP・Adobe-Manga1の輪郭をコピーせず、補間互換の独自Bezier輪郭として生成します。

Novel版のカタカナも源暎こぶり明朝の輪郭をコピーせず、対応する同ウェイトのNoto Serif JP輪郭から派生します。U+30A1–U+30FA、U+30FD–U+30FF、U+31F0–U+31FFの109字、追加するU+1B155、カタカナ`ccmp`出力、全縦組対応字形を、直線主体・曲線主体・小書き・反復記号の4群と3光学マスターで変形します。結合濁点・半濁点は合成後の一体輪郭へ一度だけ適用し、源暎こぶり明朝は寸法と黒みの比較基準としてだけ使用します。
`--variable-kana`経路は同コミットの`Serif/Variable/TTF/Subset/NotoSerifJP-VF.ttf`を制作正本として使用します。wght 200・400・900から互換輪郭を作り、残る4固定ウェイトを補間します。符号化済みひらがな89字・カタカナ109字と対応する縦組・合成字形の輪郭およびメトリクスはNoto由来です。字別の筆端深度データと局所変形を追加しますが、第三者輪郭を新たに混合しません。`Nobigoe Novel Kana Design` VFはこのNotoソースから生成する編集・比較用中間成果物です。
紹介サイトの欧文候補比較では、同じ`NotoSerifJP-VF.ttf`を欧文Unicode範囲へサブセットし、Noto Serif JP内蔵欧文の参考基準としてWOFF2で表示します。輪郭や可変軸を変更せず、通常の配布ZIPには収録しません。

現行Noto cmapではCJK Radicals Supplement／Kangxi Radicalsの293コードポイントが上記Han対象中の290 glyphを共有します。cmapを変更せず共有glyphを一度だけ変換するため、これらのradical aliasも同じ縮小輪郭を表示します。仮名・カタカナ・約物・Latin・追加記号・PUAとの共有glyphは許可せず、変換前にビルドを失敗させます。

Han縮小はIdeographs用CID Font DICTの複製、複製Private DICT、共有local Subrs、元CharStringバイト列、および対象glyphの`FDSelect`再割当で実装し、複製FDの`FontMatrix`だけを追加します。対象輪郭を展開・再符号化せず、元のヒント命令とsubroutine構造を維持します。

## Libertinus Serif

- Project: [Libertinus](https://github.com/alerque/libertinus)
- Version: `7.051`
- Archive: `Libertinus-7.051.zip`
- Download: <https://github.com/alerque/libertinus/releases/download/v7.051/Libertinus-7.051.zip>
- Archive SHA-256: `4d9be29b5cb380c35af8ba967abcc752ad1e07be1f738a9789c33e0dd7478c92`
- Copyright: `Copyright © 2012-2024 The Libertinus Project Authors.`
- License: SIL Open Font License 1.1（アーカイブ内の`OFL.txt`）

| Source file | Used for | SHA-256 |
|---|---|---|
| `LibertinusSerif-Regular.otf` | ExtraLight / Light / Regular / Medium | `fcf06307a77367394fcb0ccb241e59eea70dba3d732be309647611224679c733` |
| `LibertinusSerif-Semibold.otf` | SemiBold | `a4b3f28e85881db34695c1f005e4c79233a6caf3a2bd286c9b418c025fb99308` |
| `LibertinusSerif-Bold.otf` | Bold / Black | `0264914210ed51b3231ebc92ce529e9f2e166ba9eebf0cd4a579558690a27b64` |

### 使用箇所と改変

Noto版のBasic Latin、Latin-1 Supplement、Latin Extended-A/B、Latin Extended Additionalと、英文で使用するダッシュ、引用符、省略記号などの字形・水平メトリクスを使用します。標準の `fi`・`fl`・`ffi`・`ffl` 合字と、Noto Serif JPの `locl` が既定で選ぶ引用符・数字にも対応するLibertinus Serif字形を移植します。Libertinus Serifにない文字はNoto Serif JPの字形を保持します。Libertinus Serifが提供する3ウェイトを上表の対応で使用し、Noto Serif JPの欧文原字を基準に、大文字の輪郭高さ中央値と大文字・小文字・数字の送り幅あたりの輪郭面積を測定して、全7ウェイトの大きさと太さを補正します。Noto Serif JP側のグリフ名とOpenTypeテーブルへ調整後の輪郭と水平メトリクスを移植します。源暎こぶり明朝版には取り込みません。

## STIX Two Text

- Project: [STIX Fonts](https://github.com/stipub/stixfonts)
- Version: `2.13 b171`
- Tag: [`v2.13b171`](https://github.com/stipub/stixfonts/releases/tag/v2.13b171)
- Source directory: `fonts/variable_ttf/`
- Copyright: `Copyright 2001-2021 The STIX Fonts Project Authors (https://github.com/stipub/stixfonts)`
- License: SIL Open Font License 1.1

| Source file | Used for | SHA-256 |
|---|---|---|
| `STIXTwoText[wght].ttf` | ExtraLight / Light / Regular / Medium / SemiBold / Bold / Black | `7962b8b7811e6a896c9a91a0bccbb5241047770eb24d4997c5cb5fe21d5c0df2` |

### 使用箇所と改変

`--latin-family stix-two-text`を指定したNoto版で、Libertinus Serifと同じ欧文Unicode範囲と対応するOpenType異体字・標準合字を使用します。公式可変TTFの互換輪郭を`wght=400`と`700`で実体化し、輪郭と水平メトリクスを1.110倍してNoto Serif JP側のグリフへ移植します。混植時の黒みを揃えるため、Noto Serif JP和文の`口`・`日`・`田`・`中`・`山`と、NotoおよびSTIX欧文の`H`・`I`・`E`・`F`・`L`・`n`・`i`・`l`・`h`・`m`・`u`の直線部を複数の水平scanlineで測ります。公式STIXにないExtraLightとLightは、Noto和文とNoto欧文の主縦線幅中央値の中間値へSTIXの主縦線を合わせます。RegularからBlackまでは、Noto和文の主縦線幅中央値へ合わせます。同じウェイトではすべての通常字形へ一つの補間位置を共通適用し、文字ごとの輪郭面積や送り幅には合わせないため、STIX Two Text本来の字間差、コントラスト、字形間の太さの関係を保持します。例外は、固有の細い形状が周囲から浮く`ƒ`（U+0192）だけで、輪郭面積÷輪郭周長をストローク太さの補助指標として個別位置を設定します。求めた補間位置が公式軸の400–700範囲外にある場合も、同じ互換輪郭と水平メトリクスだけを外挿し、別フォントを混ぜません。調整済み制作VFは`--build-variable-stix`で明示的に生成でき、固定版は公式可変TTFまたはこの制作VFから実体化できます。源暎こぶり明朝版には取り込みません。

## Source Serif 4

- Project: [Source Serif](https://github.com/adobe-fonts/source-serif)
- Version: `4.005`
- Archive: `source-serif-4.005_Desktop.zip`
- Download: <https://github.com/adobe-fonts/source-serif/releases/download/4.005R/source-serif-4.005_Desktop.zip>
- Archive SHA-256: `549fdb8f9a682bd06944298621404969f6de77c2e422ff3b8244a1dcd6a0c425`
- Copyright: `© 2014 - 2023 Adobe (http://www.adobe.com/), with Reserved Font Name ‘Source’.`
- License: SIL Open Font License 1.1

| Source file | SHA-256 |
|---|---|
| `SourceSerif4Variable-Roman.ttf` | `14d360ee1b76655da9276628b229e11671bc1f5d1083636144db6677d452cf55` |

### 使用箇所と改変

`--latin-family source-serif-4`を指定したNoto版で、Libertinus Serifと同じ欧文Unicode範囲と対応するOpenType異体字・標準合字を使用します。可変フォントを`opsz=20`、Nobigoeの各ウェイトに対応する`wght=200–900`で静的に実体化し、輪郭と水平メトリクスを1.088倍してNoto Serif JP側のグリフへ移植します。TrueType複合字形は構成要素を分解してOpenType/CFF輪郭へ変換します。源暎こぶり明朝版には取り込みません。

## 紹介サイト欧文比較用Webfont

- Google Fonts repository commit: [`7ff85c87f93ea6cca5f41c69f2e4edcb90240f26`](https://github.com/google/fonts/commit/7ff85c87f93ea6cca5f41c69f2e4edcb90240f26)
- STIX Fonts tag: [`v2.13b171`](https://github.com/stipub/stixfonts/releases/tag/v2.13b171)
- License: SIL Open Font License 1.1

| Project | Copyright | Source file | SHA-256 |
|---|---|---|---|
| STIX Two Text | `Copyright 2001-2021 The STIX Fonts Project Authors (https://github.com/stipub/stixfonts)` | `STIXTwoText[wght].ttf` | `7962b8b7811e6a896c9a91a0bccbb5241047770eb24d4997c5cb5fe21d5c0df2` |
| Source Serif 4 | `© 2014 - 2021 Adobe Systems Incorporated (http://www.adobe.com/), with Reserved Font Name ‘Source’.` | `SourceSerif4[opsz,wght].ttf` | `97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b` |
| Literata | `Copyright 2017 The Literata Project Authors (https://github.com/googlefonts/literata)` | `Literata[opsz,wght].ttf` | `b41138c9373112f32abb589cc22e8674b06ed4048b0c513be922bdd26f274440` |
| Roboto Serif | `Copyright 2020 The Roboto Serif Project Authors (https://github.com/googlefonts/RobotoSerif)` | `RobotoSerif[GRAD,opsz,wdth,wght].ttf` | `351ced75f3851806aa6d846b669361521eb1925cfc530396df9c1a1b77061ddb` |
| Newsreader | `Copyright 2020 The Newsreader Project Authors (http://github.com/productiontype/Newsreader)` | `Newsreader[opsz,wght].ttf` | `8a08d13f8a6c0d51be379a60af84f945f65369a67e509ee3c3bdcc421254d7c1` |
| Petrona | `Copyright 2019 The Petrona Project Authors (https://github.com/RingoSeeber/Petrona)` | `Petrona[wght].ttf` | `0ede77fbf726541cf93ece7b721a7b069f004cb413ab205f74963560015ab075` |
| Spectral | `Copyright 2017 The Spectral Project Authors (https://github.com/productiontype/Spectral)` | `Spectral-ExtraLight.ttf` | `5d852db897fd7ad5ce640a6e88f1cd70eac75777c541d02d86749af8d4797ff1` |
| Spectral | 同上 | `Spectral-Light.ttf` | `a2a530303d326473b69ab7863b879e9203ec747e51d5fa7c7b19e0e975e00740` |
| Spectral | 同上 | `Spectral-Regular.ttf` | `c89021dc20720c8d0dcf40b0b2f6e00c13665fa8041717f581396f51b8c78f5d` |
| Spectral | 同上 | `Spectral-Medium.ttf` | `f385bc588599c879112272711d4acecc126674009d747a27284f59e93a240e83` |
| Spectral | 同上 | `Spectral-SemiBold.ttf` | `5f86915a744832ecf6e4a17ab04bea091b9fa992ef5164ff65ae34c1da2fe94b` |
| Spectral | 同上 | `Spectral-Bold.ttf` | `70ddb1ec6ae3b0b8d0c79231f670de786978f19baeba2130757526e407aebf9b` |
| Spectral | 同上 | `Spectral-ExtraBold.ttf` | `af3f8513db8d047ebecb1682b5e04dfc12ec7e6b51b71654d4d348f12a5e6b5a` |

### 使用箇所と改変

紹介サイトの`/compare/`で、のびごえ明朝の和文と混植する欧文候補としてのみ使用します。`U+0020–024F`、`U+0300–036F`、`U+1E00–1EFF`、`U+2000–206F`、`U+20A0–20CF`と対応するOpenTypeレイアウト字形へサブセットし、WOFF2へ圧縮します。可変軸は保持し、Spectralは公式固定7ウェイトを使用します。輪郭自体は変更せず、比較画面の「補正後」表示だけにCSS `size-adjust`を適用します。これらの比較用WebfontをNobigoeの配布フォントへ取り込まず、通常の配布ZIPにも収録しません。

## 源暎こぶり明朝

- Project: [源暎フォント](https://okoneya.jp/font/genei-koburimin.html)
- Archive: `GenEiKoburiMin_v6.1.zip`
- Source file in archive: `GenEiKoburiMin_v6.1a/GenEiKoburiMin6-R.ttf`
- Version: `6.1`
- Download: <https://okoneya.jp/font/GenEiKoburiMin_v6.1.zip>
- Archive SHA-256: `b17d4def22c048e704955912423c7bac8a03a3dbf1acaa722f254a7e9ece148a`
- TTF SHA-256: `c27fb4039ac9fae19152716992b5b9d07558e24f6cccea7b0c1abd0109235166`
- Copyright: `Copyright (c) 2017-2018, おたもん (http://okoneya.jp/font/), with Reserved Font Name '源暎'.`
- License: SIL Open Font License 1.1（アーカイブ内の`OFLicense.txt`）

### 使用箇所と改変

`Nobigoe Koburi Mincho Regular`のベースとして使用し、既存のTrueType字形・メトリクス・OpenTypeテーブルを保持して、Noto版と同じ追加機能をTrueType輪郭で収録します。元フォントの`ruby`機能とルビ専用字形は同ファミリー内で保持し、Nobigoe MinchoとNobigoe Novel Minchoには移植しません。派生フォント名にはReserved Font Nameの「源暎」を使用せず、英語ファミリー名を`Nobigoe Koburi Mincho`、日本語ファミリー名を`のびごえこぶり明朝`としています。

## Shippori Mincho（しっぽり明朝）

- Project: [Shippori Mincho](https://github.com/fontdasu/ShipporiMincho)
- Official distribution: [しっぽり明朝](https://fontdasu.com/shippori-mincho/)
- Archive: `shippori3.zip`
- Version: `3.300`
- Download: <https://fontdasu.com/download/shippori3.zip>
- Archive SHA-256: `dbdcab920d82238bda26296bccd9630906b427ee91b31f5da2dde8e47b0b202e`
- Copyright in bundled OFL: `Copyright (c) 2021, The Shippori Mincho Project Authors (https://github.com/fontdasu/ShipporiMincho)`
- License: SIL Open Font License 1.1（アーカイブ内の `OFL.txt`）

| Source file | Used for | SHA-256 |
|---|---|---|
| `ShipporiMincho-OTF-Regular.otf` | ExtraLight / Light / Regular / Koburi | `f597e65ce1e686ad36b63e0c82e4931e9d815187ff2311705dcf1b751ecae804` |
| `ShipporiMincho-OTF-Medium.otf` | Medium | `f2791831f662ad4de127eaef7e86a1ff6deb2e7a404330747729abc565821e06` |
| `ShipporiMincho-OTF-SemiBold.otf` | SemiBold | `52c424195a4b47bdacb3ea5cf4ced699846dfbe8a3287272fdbb8c10bcc3215d` |
| `ShipporiMincho-OTF-Bold.otf` | Bold | `1d890e64150ea8db1b593aa5ba78150a1db6156a6c566d00cf45bfe13526399f` |
| `ShipporiMincho-OTF-ExtraBold.otf` | Black | `1ff1f3d462b1d37d69995ececced9011f89d15a56a4e94db923e982125b7f768` |

### 使用箇所と改変

各ウェイトに収録された直立の全角感嘆符U+E000、全角疑問符U+FF1F、直立感嘆符合字U+E002、U+E007、U+E0E3、および既存合字 `⁇`（U+2047）、`⁈`（U+2048）、`⁉`（U+2049）の輪郭を使用しています。単独の全角感嘆符・疑問符と2〜4連の感嘆符合字は該当する字形へ置換します。5連およびその他の3記号以上では、直立感嘆符と既存合字から構成輪郭を抽出し、全角1文字幅へ再配置します。2記号の `？？`、`？！`、`！？` は該当する既存合字の輪郭を使用します。Noto版のMedium、SemiBold、Bold、Blackには順に同名ウェイト、同名ウェイト、Bold、ExtraBoldを使用します。400未満のしっぽり明朝がないため、ExtraLightとLightはRegularです。さらに各字形を右へ12度傾けた斜体明朝異体字を生成します。Noto版ではCFF輪郭を保持し、源暎こぶり明朝版ではTrueTypeの2次ベジェ曲線へ変換します。しっぽり明朝の本文字形、フォント名、OpenTypeテーブルは生成フォントへ取り込みません。

## Adobe-Manga1-0

- Project: [Adobe-Manga1](https://github.com/adobe-type-tools/Adobe-Manga1)
- License: Apache License 2.0

Adobe-Manga1-0は、伸長記号、感嘆符・疑問符シーケンス、濁点・半濁点付き仮名、およびGSUB動作を確認するための仕様資料として参照しています。Adobe-Manga1のサンプルフォント字形やCIDデータを生成フォントへコピーしていません。

## License Distribution

Noto Serif JP、Libertinus Serif、STIX Two Text、Source Serif 4、Literata、Roboto Serif、Newsreader、Petrona、Spectral、源暎こぶり明朝、Noto Sans JP、しっぽり明朝はいずれもSIL Open Font License 1.1です。OFL 1.1の全文はリポジトリの [`OFL.txt`](OFL.txt) に収録しています。生成フォントと紹介サイト同梱のWebfontを再配布する場合は、この著作権表示、第三者通知、およびOFL 1.1ライセンスをフォントとともに配布してください。
