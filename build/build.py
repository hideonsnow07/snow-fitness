#!/usr/bin/env python3
"""把三個獨立頁面（重訓紀錄、飲控計算機、冰箱食譜）組成一個合併版頁面。

用法：python3 build.py            -> 讀 src/*.html，輸出 build/dist/index.html（不含個人資料）
      python3 build.py --local    -> 同上，另外把 export/ 的紀錄注入成種子，
                                     輸出 ../dist/index.local.html（含個人資料，不可提交）
每個模組放進自己的 Shadow DOM，CSS 與 id 互不影響；
模組程式碼原封不動，只把 document / window / claude 換成該模組專用的版本。
"""
import json, re, pathlib, sys

ROOT = pathlib.Path(__file__).parent
PROJECT = ROOT.parent
EXPORT = PROJECT / "export"
LOCAL_OUT = PROJECT / "dist" / "index.local.html"
SEED_SLOT = "/*LOCAL_SEED*/null"

# 匯出檔 -> 資料庫集合（路徑都是 db_rewrite 改寫後的最終路徑）
SEED_FILES = {
    "sessions.json": "data/users/me/log/sessions",
    "days.json": "days",
    "profile.json": "profile",
    "foods.json": "foods",
    "feed.json": "feed",
    "fridge_book.json": "data/users/me/fridge/book",
}

MODULES = [
    {"id": "gym",    "src": "src/gym.html",    "label": "訓練", "icon": "dumbbell",
     "css_extra": ""},
    {"id": "diet",   "src": "src/diet.html",   "label": "飲食", "icon": "meter",
     # 浮動提示要避開底部分頁列
     "css_extra": "#toast{bottom:calc(16px + var(--barh,0px))!important}",
     "hashes": ["log", "foods", "goal"]},
    {"id": "fridge", "src": "src/fridge.html", "label": "冰箱", "icon": "fridge",
     "css_extra": ".dock{bottom:var(--barh,0px)!important;padding-bottom:10px!important}",
     # 冰箱原本把收藏存在 data/users/<id>，會跟重訓紀錄的 data/users/<id>/log 撞在一起，改放到子集合
     "db_rewrite": [[r"^data/users/([^/]+)$", r"data/users/\1/fridge/book"]]},
]


def split_page(html):
    """取出 <title>、字型連結、CSS、JS 與畫面標記。"""
    body = html.split("<body>", 1)[1] if "<body>" in html else html
    body = body.rsplit("</body>", 1)[0]
    fonts = re.findall(r'<link[^>]+rel="stylesheet"[^>]*>', body)
    styles = re.findall(r"<style[^>]*>(.*?)</style>", body, re.S)
    scripts = re.findall(r"<script[^>]*>(.*?)</script>", body, re.S)
    markup = body
    for pat in (r"<title>.*?</title>", r"<meta[^>]*>", r"<link[^>]*>",
                r"<style[^>]*>.*?</style>", r"<script[^>]*>.*?</script>"):
        markup = re.sub(pat, "", markup, flags=re.S)
    hrefs = [re.search(r'href="([^"]+)"', f).group(1) for f in fonts]
    return hrefs, "\n".join(styles), "\n;\n".join(scripts), markup.strip()


def scope_css(css):
    """把整頁用的選擇器改成 Shadow DOM 裡能用的寫法。"""
    css = css.replace(':root[data-theme="dark"]', ':host([data-theme="dark"])')
    css = css.replace(':root[data-theme="light"]', ':host([data-theme="light"])')
    css = css.replace(':root:not([data-theme="light"])', ':host(:not([data-theme="light"]))')
    css = css.replace(':root:not([data-theme="dark"])', ':host(:not([data-theme="dark"]))')
    css = re.sub(r":root(?![\w-])", ":host", css)
    css = re.sub(r"(?<![\w.#-])html(?=[\s,{])", ":host", css)
    css = re.sub(r"(?<![\w.#-])body(?=[\s,{:.>\[])", ".mbody", css)
    return css


def load_seed():
    """讀 export/，整理成 {集合: [{id, data}]}。"""
    seed = {}
    for name, coll in SEED_FILES.items():
        docs = json.loads((EXPORT / name).read_text(encoding="utf-8"))["documents"]
        seed[coll] = [{"id": d["id"], "data": d["data"]} for d in docs]
    return seed


def script_json(value):
    """轉成可放進 <script> 的 JSON：紀錄內容是資料，不能讓它關掉 script 標籤。"""
    return json.dumps(value).replace("<", "\\u003c")


def build(local=False):
    fonts, mods = [], []
    for m in MODULES:
        html = (ROOT / m["src"]).read_text(encoding="utf-8")
        hrefs, css, js, markup = split_page(html)
        for h in hrefs:
            if h not in fonts:
                fonts.append(h)
        css = ":host{display:block}\n[hidden]{display:none!important}\n" + scope_css(css) + "\n" + m.get("css_extra", "")
        mods.append({**m, "css": css, "js": js, "markup": markup})

    shell = (ROOT / "shell.html").read_text(encoding="utf-8")
    font_links = "\n".join(f'<link rel="stylesheet" href="{h}">' for h in fonts)
    templates = "\n".join(
        f'<template id="tpl-{m["id"]}"><style>{m["css"]}</style><div class="mbody">{m["markup"]}</div></template>'
        for m in mods)
    tabs = "\n".join(
        f'<button class="navbtn" type="button" id="nav-{m["id"]}" data-mod="{m["id"]}" aria-pressed="false">'
        f'<span class="ico ico-{m["icon"]}" aria-hidden="true"></span><span>{m["label"]}</span></button>'
        for m in mods)
    hosts = "\n".join(f'<section class="mod" id="mod-{m["id"]}" hidden></section>' for m in mods)
    config = {m["id"]: {"rewrite": m.get("db_rewrite", []), "hashes": m.get("hashes", [])} for m in mods}
    runners = "\n".join(
        f'MODS[{json.dumps(m["id"])}]=function(document,window,claude){{\n{m["js"]}\n}};'
        for m in mods)

    out = (shell.replace("<!--FONTS-->", font_links)
                .replace("<!--TEMPLATES-->", templates)
                .replace("<!--HOSTS-->", hosts)
                .replace("<!--NAV-->", tabs)
                .replace("/*CONFIG*/", json.dumps(config, ensure_ascii=False))
                .replace("/*MODULES*/", runners))
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / "index.html").write_text(out, encoding="utf-8")
    print("dist/index.html", len(out.encode()), "bytes")

    if local:
        if out.count(SEED_SLOT) != 1:
            sys.exit("shell.html 的種子插槽應該剛好一個")
        seed = load_seed()
        page = out.replace(SEED_SLOT, script_json(seed))
        LOCAL_OUT.parent.mkdir(exist_ok=True)
        LOCAL_OUT.write_text(page, encoding="utf-8")
        counts = ", ".join(f"{c}={len(d)}" for c, d in seed.items())
        print(LOCAL_OUT, len(page.encode()), "bytes;", counts)


if __name__ == "__main__":
    build(local="--local" in sys.argv[1:])
