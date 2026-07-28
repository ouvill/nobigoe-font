export const SITE = {
  name: "のびごえ明朝",
  companion: "のびごえこぶり明朝",
  title: "のびごえ明朝・のびごえこぶり明朝 — 声を、つなぐ。",
  description:
    "伸びる記号や結合文字を備えた7ウェイトの明朝体と、小説・縦組向けのこぶり明朝。",
  version: "1.026",
  releaseUrl: "https://github.com/ouvill/nobigoe-font/releases",
  repositoryUrl: "https://github.com/ouvill/nobigoe-font",
} as const;

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
  { href: "/tester/", label: "文字を試す" },
  { href: "/glyphs/", label: "字形一覧" },
] as const;
