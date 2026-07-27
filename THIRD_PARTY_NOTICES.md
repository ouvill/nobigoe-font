# Third-Party Notices

`Noto Serif JP Choon Regular`は、次の第三者フォントから輪郭とメトリクスを取り込んだ派生フォントです。

## Noto Serif JP Regular

- Project: [Noto CJK](https://github.com/notofonts/noto-cjk)
- Source file: `Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf`
- Version: `2.003`
- Commit: [`9b0f1436e455d902de067a2501422e5dc71ad16b`](https://github.com/notofonts/noto-cjk/commit/9b0f1436e455d902de067a2501422e5dc71ad16b)
- Download: <https://raw.githubusercontent.com/notofonts/noto-cjk/9b0f1436e455d902de067a2501422e5dc71ad16b/Serif/SubsetOTF/JP/NotoSerifJP-Regular.otf>
- SHA-256: `2c9a12dbd4f2408c4610c7ee84a108b62d7236c3775baed618c64d9cb44b2f04`
- Copyright: `Copyright 2017-2024 Adobe (http://www.adobe.com/). Noto is a trademark of Google Inc.`
- License: SIL Open Font License 1.1

### 使用箇所と改変

Noto Serif JP Regularを生成フォントのベースとして使用しています。既存字形・メトリクス・OpenTypeテーブルを保持し、次を追加または変更しています。

- `ー`、`―`、`〜`、`～`の連結用字形
- 横組・縦組の文脈置換
- Manga1方式の全角感嘆符・疑問符合字
- ファミリー名、PostScript名、バージョン、著作権・Noticeメタデータ

元フォントと区別するため、生成フォントのファミリー名は `Noto Serif JP Choon` です。

## Shippori Mincho Regular（しっぽり明朝）

- Project: [Shippori Mincho](https://github.com/fontdasu/ShipporiMincho)
- Source file: `fonts/ttf/ShipporiMincho-Regular.ttf`
- Version: `3.110`
- Commit: [`63431fee6c2cfea772325d6251d2935b7cfa7c6d`](https://github.com/fontdasu/ShipporiMincho/commit/63431fee6c2cfea772325d6251d2935b7cfa7c6d)
- Download: <https://raw.githubusercontent.com/fontdasu/ShipporiMincho/63431fee6c2cfea772325d6251d2935b7cfa7c6d/fonts/ttf/ShipporiMincho-Regular.ttf>
- SHA-256: `743f95a923387d9c5d0709b08e98adf706f871bfa7ccaa21ebdf5526ba080476`
- Copyright: `Copyright 2021 The Shippori Mincho Project Authors (https://github.com/fontdasu/ShipporiMincho)`
- License: SIL Open Font License 1.1
- License text: <https://raw.githubusercontent.com/fontdasu/ShipporiMincho/63431fee6c2cfea772325d6251d2935b7cfa7c6d/OFL.txt>

### 使用箇所と改変

しっぽり明朝RegularのASCII `!`（U+0021）と `?`（U+003F）の輪郭だけを抽出し、Adobe-Manga1-0で定義される16通りの全角感嘆符・疑問符合字へ再配置しています。しっぽり明朝の本文字形、フォント名、OpenTypeテーブルは生成フォントへ取り込みません。

## Adobe-Manga1-0

- Project: [Adobe-Manga1](https://github.com/adobe-type-tools/Adobe-Manga1)
- License: Apache License 2.0

Adobe-Manga1-0は、対応する感嘆符・疑問符シーケンスとGSUB動作を確認するための仕様資料として参照しています。Adobe-Manga1のサンプルフォント字形やCIDデータを生成フォントへコピーしていません。

## License Distribution

Noto Serif JPとしっぽり明朝はいずれもSIL Open Font License 1.1です。OFL 1.1の全文はリポジトリの [`OFL.txt`](OFL.txt) に収録しています。生成フォントを再配布する場合は、この著作権表示、第三者通知、およびOFL 1.1ライセンスを生成フォントとともに配布してください。
