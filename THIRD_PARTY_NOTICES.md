# Third-Party Notices

`Nobigoe Mincho Regular`（のびごえ明朝）は、次の第三者フォントから輪郭とメトリクスを取り込んだ派生フォントです。

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

- `ー`、`―`、`〜`、`～`、`〰`の横組・縦組用連結字形と文脈置換
- Manga1方式の全角感嘆符・疑問符合字
- Manga1方式の濁点・半濁点付き仮名と小書きコ
- ファミリー名、PostScript名、バージョン、著作権・Noticeメタデータ

元フォントと区別するため、生成フォントのファミリー名は `Nobigoe Mincho`（のびごえ明朝）です。

## Shippori Mincho Regular（しっぽり明朝）

- Project: [Shippori Mincho](https://github.com/fontdasu/ShipporiMincho)
- Official distribution: [しっぽり明朝](https://fontdasu.com/shippori-mincho/)
- Archive: `shippori3.zip`
- Source file in archive: `ShipporiMincho-OTF-Regular.otf`
- Version: `3.300`
- Download: <https://fontdasu.com/download/shippori3.zip>
- Archive SHA-256: `dbdcab920d82238bda26296bccd9630906b427ee91b31f5da2dde8e47b0b202e`
- OTF SHA-256: `f597e65ce1e686ad36b63e0c82e4931e9d815187ff2311705dcf1b751ecae804`
- Copyright in bundled OFL: `Copyright (c) 2021, The Shippori Mincho Project Authors (https://github.com/fontdasu/ShipporiMincho)`
- License: SIL Open Font License 1.1（アーカイブ内の `OFL.txt`）

### 使用箇所と改変

しっぽり明朝Regularに収録された既存合字 `‼`（U+203C）、`⁇`（U+2047）、`⁈`（U+2048）、`⁉`（U+2049）の輪郭を使用しています。2記号の組み合わせには該当する既存合字のCFF輪郭を直接使用し、3記号以上では `‼`、`⁇`、`⁉` の構成輪郭を抽出して全角1文字幅へ再配置します。OTF版から直接流用する2記号合字では曲線形状を変更しません。利用者がTTF版を指定した場合に限り、TrueTypeの2次ベジェ曲線をOpenType/CFFの3次ベジェ曲線へ変換します。しっぽり明朝の本文字形、フォント名、OpenTypeテーブルは生成フォントへ取り込みません。

## Adobe-Manga1-0

- Project: [Adobe-Manga1](https://github.com/adobe-type-tools/Adobe-Manga1)
- License: Apache License 2.0

Adobe-Manga1-0は、伸長記号、感嘆符・疑問符シーケンス、濁点・半濁点付き仮名、およびGSUB動作を確認するための仕様資料として参照しています。Adobe-Manga1のサンプルフォント字形やCIDデータを生成フォントへコピーしていません。

## License Distribution

Noto Serif JPとしっぽり明朝はいずれもSIL Open Font License 1.1です。OFL 1.1の全文はリポジトリの [`OFL.txt`](OFL.txt) に収録しています。生成フォントと紹介サイト同梱のWebfontを再配布する場合は、この著作権表示、第三者通知、およびOFL 1.1ライセンスをフォントとともに配布してください。
