# Third-Party Notices

`Nobigoe Mincho`（のびごえ明朝）と`Nobigoe Koburi Mincho`（のびごえこぶり明朝）は、次の第三者フォントから輪郭とメトリクスを取り込んだ派生フォントです。

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

各ウェイトを対応する`Nobigoe Mincho`の和文ベースとして使用しています。欧文字形とそのメトリクスはLibertinus Serifへ置換し、それ以外の既存字形・メトリクス・OpenTypeテーブルを保持しています。伸長記号、Manga1方式の感嘆符・疑問符合字、濁点・半濁点付き仮名、ルビ、小書きコを追加し、ファミリー名、PostScript名、バージョン、著作権・Noticeメタデータを元フォントと区別できる名前へ変更しています。


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

`Nobigoe Koburi Mincho Regular`のベースとして使用し、既存のTrueType字形・メトリクス・OpenTypeテーブルを保持して、Noto版と同じ追加機能をTrueType輪郭で収録します。また、同フォントの `ruby` が参照するルビ専用288字形を1000 units/emへ正規化し、通常仮名の輪郭面積を基準に線幅を各ウェイトへ合わせてNoto版へ移植します。派生フォント名にはReserved Font Nameの「源暎」を使用せず、英語ファミリー名を`Nobigoe Koburi Mincho`、日本語ファミリー名を`のびごえこぶり明朝`としています。

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

Noto Serif JP、Libertinus Serif、源暎こぶり明朝、Noto Sans JP、しっぽり明朝はいずれもSIL Open Font License 1.1です。OFL 1.1の全文はリポジトリの [`OFL.txt`](OFL.txt) に収録しています。生成フォントと紹介サイト同梱のWebfontを再配布する場合は、この著作権表示、第三者通知、およびOFL 1.1ライセンスをフォントとともに配布してください。
