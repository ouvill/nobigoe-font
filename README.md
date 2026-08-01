# のびごえ明朝 (Nobigoe Mincho)

のびごえ明朝は、Noto Serif JPを土台にした一般用途の明朝体です。本文を読みやすく組める文字を揃えながら、長く伸びる記号、濁点・半濁点、感嘆符や疑問符まで、声のような文字表現を加えました。横組と縦組の両方で利用できます。

[公式サイト](https://nobigoe.ouvill.net/) · [ブラウザで試す](https://nobigoe.ouvill.net/tester/) · [字形一覧](https://nobigoe.ouvill.net/glyphs/) · [ダウンロード](https://github.com/ouvill/nobigoe-font/releases/latest)

![のびごえ明朝とのびごえこぶり明朝の字形一覧。伸長記号、結合濁点・半濁点、感嘆符・疑問符合字、二つのファミリーを掲載](https://nobigoe.ouvill.net/assets/readme-glyphs.png)

## できること

- `ー`、`―`、`〜`、`～`、`〰`を2文字以上続けると、切れ目のない伸長記号として表示
- 仮名、長音、ハート、全角の感嘆符・疑問符へ濁点・半濁点を結合
- 全角の`！`と`？`を2〜5文字続けると、全角1文字幅の合字として表示
- 感嘆符・疑問符とその合字を、明朝・斜体明朝から選択
- 小書きこ`𛄲`・小書きコ`𛅕`を収録
- 特殊な字形を含め、横組・縦組の両方に対応

入力例:

```text
待ってーーーー！
ざわ〜〜〜〜〜
あ゙っ！！？
か゚ セ゚ ㇷ゚
```

詳しい入力方法、対応文字、OpenType設定は[機能と使い方](docs/features.md)を参照してください。

## ダウンロードとインストール

1. [最新のGitHub Release](https://github.com/ouvill/nobigoe-font/releases/latest)を開きます。
2. 用途に合うZIPをダウンロードして展開します。
3. 展開した`.otf`または`.ttf`ファイルを、OSのフォント管理画面からインストールします。
4. アプリケーションのフォント一覧から「のびごえ明朝」「のびごえエッセンシャル」または「のびごえこぶり明朝」を選びます。

| ZIP | 収録ファミリー | 内容 |
|---|---|---|
| `NobigoeMincho-v<version>.zip` | のびごえ明朝 | ExtraLight / Light / Regular / Medium / SemiBold / Bold / Blackの7ウェイト |
| `NobigoeEssential-v<version>.zip` | のびごえエッセンシャル | `ー` / `―` / `〜` / `～` / `〰`だけを収録した200–900の可変フォント |
| `NobigoeKoburiMincho-v<version>.zip` | のびごえこぶり明朝 | Regularの1ウェイト |

> [!NOTE]
> 伸長記号や合字にはOpenType機能を使用します。一般的なシェーピングエンジンでは必要な`ccmp`、`liga`、`calt`が既定で有効ですが、利用するアプリケーションによって対応状況が異なります。

## ファミリーを選ぶ

| ファミリー | 向いている用途 | ウェイト | 形式 |
|---|---|---|---|
| Nobigoe Mincho（のびごえ明朝） | 一般的な本文、見出し、ウェブ、印刷物 | 7ウェイト | OpenType/CFF (`.otf`) |
| Nobigoe Essential（のびごえエッセンシャル） | 任意のフォントへ連結する伸長記号だけを加える用途 | 200–900（可変） | OpenType/CFF2 (`.otf`) |
| Nobigoe Koburi Mincho（のびごえこぶり明朝） | 小説、長文、縦組など、小ぶりな仮名を生かした本文 | Regular | TrueType (`.ttf`) |

のびごえ明朝はNoto Serif JPの和文とLibertinus Serifの欧文を組み合わせています。のびごえエッセンシャルはNoto版から`ー`、`―`、`〜`、`～`、`〰`と、それらの連結・縦組・波形切替に必要な字形だけを取り出したフォールバック用ファミリーです。のびごえこぶり明朝は源暎こぶり明朝を土台にした独立ファミリーです。伸長記号、濁点・半濁点、感嘆符・疑問符合字、小書きこ・コは通常の2ファミリーで利用でき、のびごえこぶり明朝は元フォントの`ruby`機能も保持しています。

開発中の`Nobigoe Novel Mincho`（のびごえ小説明朝）は、カスタマイズ済みNobigoe CFF2の三次ベジェ輪郭を200・400・900の3マスターで変形し、標準7ウェイトへ展開する実験的ファミリーです。通常の配布ZIPとタグリリースには含まれません。設計と検証内容は[Novel小説本文設計](docs/novel-design.md)に記載しています。

### 他のフォントと組み合わせる

ウェブでは、のびごえエッセンシャルを使いたい本文フォントより前へ指定します。5文字以外のUnicode割り当てを持たないため、本文は後続フォントのまま、伸長記号だけがのびごえの連結字形になります。

```css
@font-face {
  font-family: "Nobigoe Essential";
  src: url("./NobigoeEssential-VF.otf") format("opentype");
  font-weight: 200 900;
}

.example {
  font-family: "Nobigoe Essential", "任意の本文フォント", serif;
}
```

`font-weight`は200から900まで連続して指定できます。OpenTypeの`liga`と`calt`が既定で有効な環境で連結し、`vert` / `vrt2`に対応する環境では縦組字形へ切り替わります。

## OpenTypeの異体字を選ぶ

対応するアプリケーションでは、次の機能を指定できます。

| feature | 表示 |
|---|---|
| `ss01` | 全角感嘆符・疑問符と合字を斜体明朝へ変更 |
| `ss04` | 連続する`〜`・`～`を1文字1.25周期の波形へ変更 |
| `ss05` | 連続する`〜`・`～`を1文字1周期の波形へ変更 |
| `ruby` | 対応するかな、数字、約物、半濁点付き仮名をルビ字形へ変更（のびごえこぶり明朝のみ） |

CSSで斜体明朝とゆるやかな波形を有効にする例:

```css
.example {
  font-family: "Nobigoe Mincho", serif;
  font-feature-settings: "ss01" 1, "ss04" 1;
}
```

波形の`ss04`と`ss05`は同時に指定せず、どちらか一方だけを有効にします。どちらも無効の場合は、既定の1文字1.5周期です。

## ドキュメント

- [機能と使い方](docs/features.md) — 対応する入力、字形の動作、OpenType機能
- [ビルドと開発](docs/development.md) — ローカルビルド、配布、テスト、コード構成、紹介サイト
- [Novel小説本文設計](docs/novel-design.md) — 実験的ファミリーの設計、対象字形、計測結果
- [第三者フォントの通知](THIRD_PARTY_NOTICES.md) — 取得元、バージョン、SHA-256、著作権表示

## ライセンス

本プロジェクトのフォント関連ファイルと生成フォントは[SIL Open Font License 1.1](OFL.txt)の条件に従います。生成フォントに取り込まれる各フォントもSIL Open Font License 1.1で提供されています。著作権表示と改変内容は[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。

本プロジェクトはAdobe、Google、Noto Project、Libertinus Project、またはShippori Mincho Projectによる公式配布物ではありません。`Noto`はGoogle LLCの商標です。各名称は出典と互換性を明示する目的でのみ使用しています。

制作: [Ouvill](https://blog.ouvill.net) · [X / @ouvill](https://twitter.com/ouvill) · [GitHub](https://github.com/ouvill) · [開発を支援](https://github.com/sponsors/ouvill)
