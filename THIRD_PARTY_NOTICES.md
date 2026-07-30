# Third-Party Notices

`Nobigoe Mincho`（のびごえ明朝）、`Nobigoe Novel Mincho`（のびごえ小説明朝）、`Nobigoe Koburi Mincho`（のびごえこぶり明朝）は、次の第三者フォントから輪郭とメトリクスを取り込んだ派生フォントです。STIX Two TextとSource Serif 4は、`--latin-family`で明示した比較ビルドだけに取り込みます。

## Noto Serif JP

- Project: [Noto CJK](https://github.com/notofonts/noto-cjk)
- Version: `2.003`
- Commit: [`9b0f1436e455d902de067a2501422e5dc71ad16b`](https://github.com/notofonts/noto-cjk/commit/9b0f1436e455d902de067a2501422e5dc71ad16b)
- Source directory: `Serif/SubsetOTF/JP/`
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

### 使用箇所と改変

各ウェイトを対応する`Nobigoe Mincho`と`Nobigoe Novel Mincho`の和文ベースとして使用しています。Novel版のひらがなは源暎こぶり明朝の輪郭をコピーせず、対応する同ウェイトのNoto Serif JP輪郭を4字形群・3光学マスターの異方性縮小、位置、細ウェイト縦画補正で変形します。縦組は同じNoto由来輪郭へ独立した3光学マスターと字別の高さ・横幅・縦画黒み補正を追加し、源暎こぶり明朝は寸法と黒みの比較基準としてだけ使用します。U+3041–U+3096、U+309D–U+309F、追加するU+1B132、ひらがな`ccmp`出力、全縦組対応字形が仮名変換の対象です。さらにNovel版では、Unicode 15.1で固定したCJK Unified Ideographs全拡張とCJK Compatibility IdeographsのうちNoto cmapにある13,477 glyph、およびそのglyphから異体字・旧字体・新字体・言語形・縦組のGSUB機能をグラフ追跡して到達する未符号化492 glyphを、1000-unitセル中心(500, 500)基準で`1000 / 1024 = 0.9765625`倍へ等方縮小します。`々`・`〆`・`〇`・`〻`・`〼`、カタカナ、約物、Latin、追加記号、`dlig`・`ruby`出力は漢字縮小の対象外です。h/v advance、`VORG`、cmap、既存GSUB/GPOS/GDEFを維持します。欧文字形とそのメトリクスは選択した欧文プロファイルへ置換するか、`--latin-family noto`ではNoto Serif JPのまま保持します。伸長記号、Manga1方式の感嘆符・疑問符合字、濁点・半濁点付き仮名、ルビ、小書きコを追加し、ファミリー名、PostScript名、バージョン、著作権・Noticeメタデータを元フォントと区別できる名前へ変更しています。

Novel版のカタカナも源暎こぶり明朝の輪郭をコピーせず、対応する同ウェイトのNoto Serif JP輪郭から派生します。U+30A1–U+30FA、U+30FD–U+30FF、U+31F0–U+31FFの109字、追加するU+1B155、カタカナ`ccmp`出力、全縦組対応字形を、直線主体・曲線主体・小書き・反復記号の4群と3光学マスターで変形します。結合濁点・半濁点は合成後の一体輪郭へ一度だけ適用し、源暎こぶり明朝は寸法と黒みの比較基準としてだけ使用します。

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
- Source directory: `fonts/static_otf/`
- Copyright: `Copyright 2001-2021 The STIX Fonts Project Authors (https://github.com/stipub/stixfonts)`
- License: SIL Open Font License 1.1

| Source file | Used for | SHA-256 |
|---|---|---|
| `STIXTwoText-Regular.otf` | Regular | `c4864ca6ec071c2d31d0d8309001faa1ee3517fffb53a31a405a697b71f52ca1` |
| `STIXTwoText-Medium.otf` | Medium | `9cc9f870852a46d708907b96ed024b8d0067a05276d939bfe0b7e89752afc8d9` |
| `STIXTwoText-SemiBold.otf` | SemiBold | `896d80fbfd67e86ead7e2d593d631eab9bb142ee96dcd8e7aa8dff95ddda0f2a` |
| `STIXTwoText-Bold.otf` | Bold | `7ef76c666a6704f76ed3fa27bcdda55b36e558b5c2c93b49b03d854db96bdeb5` |

### 使用箇所と改変

`--latin-family stix-two-text`を指定したNoto版で、Libertinus Serifと同じ欧文Unicode範囲と対応するOpenType異体字・標準合字を使用します。輪郭と水平メトリクスを1.110倍してNoto Serif JP側のグリフへ移植します。STIX Two TextにネイティブソースがあるRegular、Medium、SemiBold、Boldだけを対象とし、源暎こぶり明朝版には取り込みません。

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

`Nobigoe Koburi Mincho Regular`のベースとして使用し、既存のTrueType字形・メトリクス・OpenTypeテーブルを保持して、Noto版と同じ追加機能をTrueType輪郭で収録します。また、同フォントの `ruby` が参照するルビ専用288字形を1000 units/emへ正規化してNoto版へ移植します。線幅補正では、源暎こぶり明朝で97.7%に小さく設計された通常仮名を比較時だけ原寸へ戻して輪郭面積を測り、Noto各ウェイトとの差分をルビ輪郭へ適用します。ルビ字形は拡大縮小しません。派生フォント名にはReserved Font Nameの「源暎」を使用せず、英語ファミリー名を`Nobigoe Koburi Mincho`、日本語ファミリー名を`のびごえこぶり明朝`としています。

## Noto Sans JP

- Project: [Noto CJK](https://github.com/notofonts/noto-cjk)
- Version: `2.004`
- Commit: [`9b0f1436e455d902de067a2501422e5dc71ad16b`](https://github.com/notofonts/noto-cjk/commit/9b0f1436e455d902de067a2501422e5dc71ad16b)
- Source directory: `Sans/SubsetOTF/JP/`
- Copyright: `Copyright 2017-2024 Adobe (http://www.adobe.com/). Noto is a trademark of Google Inc.`
- License: SIL Open Font License 1.1

| Source file | Used for | SHA-256 |
|---|---|---|
| `NotoSansJP-Thin.otf` | ExtraLight | `1d8462eb0050bf6f8ee8dc0a34f11185839e155b0fce8ec2f14427b28d4d134f` |
| `NotoSansJP-Light.otf` | Light | `e358dcfa7970805300a953bb71209c3efcbcc17a00a5e4101f8cf94a3870ad93` |
| `NotoSansJP-Regular.otf` | Regular / Koburi | `dff723ba59d57d136764a04b9b2d03205544f7cd785a711442d6d2d085ac5073` |
| `NotoSansJP-Medium.otf` | Medium | `f396a3b57256e4515be9cb41f7aac54766d654890082a9f1b5c2451b5c093d8a` |
| `NotoSansJP-Bold.otf` | SemiBold / Bold | `1b0edfb500b73a4fa8a4fcaae1bbbd403994e08e73e3e0da37e70d3853f42c5f` |
| `NotoSansJP-Black.otf` | Black | `3aa30b0956510f4205f759ab3079a5b658310ebcda2577f290466ea51c948819` |

### 使用箇所と改変

対応ウェイトの全角感嘆符`！`（U+FF01）と全角疑問符`？`（U+FF1F）の輪郭を使用しています。単独字形とManga1方式の16シーケンスを全角1文字幅へ再配置してゴシック異体字を生成し、さらに右へ12度傾けた異体字を生成します。Noto Sans JPの本文字形、フォント名、OpenTypeテーブルは生成フォントへ取り込みません。

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

Noto Serif JP、Libertinus Serif、STIX Two Text、Source Serif 4、源暎こぶり明朝、Noto Sans JP、しっぽり明朝はいずれもSIL Open Font License 1.1です。OFL 1.1の全文はリポジトリの [`OFL.txt`](OFL.txt) に収録しています。生成フォントと紹介サイト同梱のWebfontを再配布する場合は、この著作権表示、第三者通知、およびOFL 1.1ライセンスをフォントとともに配布してください。
