const version = import.meta.env.PUBLIC_FONT_VERSION;

export const SITE = {
  name: "のびごえ明朝",
  companion: "のびごえこぶり明朝",
  title: "のびごえ明朝 — 文章も、声の表情も。",
  description:
    "Noto Serif JPを土台に、伸長記号、濁点・半濁点、感嘆符・疑問符の表現を加えた一般用途の明朝体。",
  author: {
    name: "Ouvill",
    url: "https://blog.ouvill.net",
    socialHandle: "@ouvill",
    socialUrl: "https://twitter.com/ouvill",
  },
  version,
  downloadUrl: `https://github.com/ouvill/nobigoe-font/releases/download/v${version}/NobigoeMincho-v${version}.zip`,
  koburiDownloadUrl: `https://github.com/ouvill/nobigoe-font/releases/download/v${version}/NobigoeKoburiMincho-v${version}.zip`,
  essentialDownloadUrl: `https://github.com/ouvill/nobigoe-font/releases/download/v${version}/NobigoeEssential-v${version}.zip`,
  releaseUrl: "https://github.com/ouvill/nobigoe-font/releases",
  repositoryUrl: "https://github.com/ouvill/nobigoe-font",
  supportUrl: "https://github.com/sponsors/ouvill",
} as const;

export const NOVEL_PROSE_SPECIMEN =
  "あのイーハトーヴォのすきとおった風、夏でも底に冷たさをもつ青いそら、うつくしい森で飾られたモリーオ市、郊外のぎらぎらひかる草の波。またそのなかでいっしょになったたくさんのひとたち、ファゼーロとロザーロ、羊飼のミーロや、顔の赤いこどもたち、地主のテーモ、山猫博士のボーガント・デストゥパーゴなど、いまこの暗い巨きな石の建物のなかで考えていると、みんなむかし風のなつかしい青い幻燈のように思われます。";

export const WEIGHTS = [
  { name: "ExtraLight", value: 200 },
  { name: "Light", value: 300 },
  { name: "Regular", value: 400 },
  { name: "Medium", value: 500 },
  { name: "SemiBold", value: 600 },
  { name: "Bold", value: 700 },
  { name: "Black", value: 900 },
] as const;

export const NAVIGATION = [
  { href: "/", label: "紹介" },
  { href: "/#try", label: "文字を試す" },
  { href: "/glyphs/", label: "字形一覧" },
] as const;
