"""
記事MarkdownをHTMLに変換し、サイトに組み込む
"""

import re
import os
from pathlib import Path


def markdown_to_html(md_text: str) -> str:
    """簡易Markdown → HTML変換"""
    html = md_text

    # コードブロック（```...```）を先に処理して中身を保護
    code_blocks = []
    def save_code(m):
        code_blocks.append(m.group(1))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"
    html = re.sub(r'```(?:\w+)?\n(.*?)```', save_code, html, flags=re.DOTALL)

    # 見出し（{#id} アンカー対応）
    def heading_with_id(m, tag):
        text = m.group(1).strip()
        # {#id} を抽出
        id_match = re.search(r'\s*\{#(\S+)\}\s*$', text)
        if id_match:
            anchor_id = id_match.group(1)
            text = text[:id_match.start()]
            return f'<{tag} id="{anchor_id}">{text}</{tag}>'
        return f'<{tag}>{text}</{tag}>'

    html = re.sub(r'^##### (.+)$', lambda m: heading_with_id(m, 'h5'), html, flags=re.MULTILINE)
    html = re.sub(r'^#### (.+)$', lambda m: heading_with_id(m, 'h4'), html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', lambda m: heading_with_id(m, 'h3'), html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', lambda m: heading_with_id(m, 'h2'), html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', lambda m: heading_with_id(m, 'h1'), html, flags=re.MULTILINE)

    # 太字・イタリック
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # リンク（Markdown形式）
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', html)

    # 裸のURL（https://... がそのまま書かれている場合）をクリック可能なリンクに変換
    # ただし既に <a href="..."> 内にあるURLは除外
    html = re.sub(
        r'(?<!href=")(?<!">)(https?://[^\s<>\)]+)',
        r'<a href="\1" target="_blank" rel="noopener">\1</a>',
        html
    )

    # テーブル
    lines = html.split('\n')
    result = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue  # セパレータ行をスキップ
            if not in_table:
                result.append('<div class="table-wrapper"><table>')
                # 最初の行はヘッダー
                result.append('<thead><tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr></thead><tbody>')
                in_table = True
            else:
                result.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        else:
            if in_table:
                result.append('</tbody></table></div>')
                in_table = False
            result.append(line)
    if in_table:
        result.append('</tbody></table></div>')
    html = '\n'.join(result)

    # リスト（箇条書き）
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>\n?)+', lambda m: '<ul>' + m.group(0) + '</ul>', html)

    # 番号付きリスト
    html = re.sub(r'^\d+\. (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

    # 引用
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)

    # 水平線
    html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)

    # 段落（空行で区切られたテキスト）
    html = re.sub(r'\n\n([^<\n].+?)(?=\n\n|\n<|$)', r'\n\n<p>\1</p>', html, flags=re.DOTALL)

    # コードブロック復元
    for i, code in enumerate(code_blocks):
        html = html.replace(f'__CODE_BLOCK_{i}__', f'<pre><code>{code}</code></pre>')

    return html


def parse_article_file(filepath: Path) -> dict:
    """記事ファイルからフロントマターと本文を抽出"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # YAMLフロントマター
    meta = {}
    body = content

    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split('\n'):
                if ':' in line:
                    k, _, v = line.partition(':')
                    meta[k.strip()] = v.strip().strip('"').strip("'")
            body = parts[2].strip()

    # JSON形式の記事の場合、articleフィールドを抽出
    if body.startswith('```json'):
        import json
        try:
            json_text = body.split('```json')[1].split('```')[0]
            data = json.loads(json_text)
            meta['title'] = data.get('title', meta.get('title', ''))
            meta['description'] = data.get('meta_description', meta.get('description', ''))
            body = data.get('article', body)
        except (json.JSONDecodeError, IndexError):
            pass

    return {'meta': meta, 'body': body}


ARTICLE_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | AI Tools Lab</title>
    <meta name="description" content="{description}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Helvetica Neue', 'Noto Sans JP', sans-serif; color: #333; line-height: 1.9; background: #f8fafc; }}
        header {{ background: #fff; border-bottom: 2px solid #2563eb; padding: 16px 0; position: sticky; top: 0; z-index: 100; }}
        .header-inner {{ max-width: 1100px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }}
        .logo {{ font-size: 1.5em; font-weight: 800; color: #2563eb; text-decoration: none; }}
        .logo span {{ color: #333; }}
        nav a {{ color: #555; text-decoration: none; margin-left: 24px; font-size: 0.95em; }}
        nav a:hover {{ color: #2563eb; }}
        .article-container {{ max-width: 780px; margin: 0 auto; padding: 40px 20px; }}
        .breadcrumb {{ font-size: 0.85em; color: #888; margin-bottom: 24px; }}
        .breadcrumb a {{ color: #2563eb; text-decoration: none; }}
        article {{ background: #fff; border-radius: 12px; padding: 40px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        article h1 {{ font-size: 1.7em; line-height: 1.4; margin-bottom: 24px; color: #1e3a5f; }}
        article h2 {{ font-size: 1.35em; margin: 36px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; color: #1e3a5f; }}
        article h3 {{ font-size: 1.15em; margin: 28px 0 12px; color: #334155; }}
        article p {{ margin-bottom: 16px; color: #444; }}
        article ul, article ol {{ margin: 16px 0; padding-left: 28px; }}
        article li {{ margin-bottom: 8px; }}
        article a {{ color: #2563eb; }}
        article blockquote {{ border-left: 4px solid #2563eb; padding: 12px 20px; margin: 20px 0; background: #f0f4ff; border-radius: 0 8px 8px 0; }}
        article hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 32px 0; }}
        article strong {{ color: #1e3a5f; }}
        .table-wrapper {{ overflow-x: auto; margin: 20px 0; }}
        article table {{ width: 100%; border-collapse: collapse; font-size: 0.9em; }}
        article th {{ background: #f0f4ff; padding: 10px 14px; text-align: left; border: 1px solid #e2e8f0; font-weight: 600; }}
        article td {{ padding: 10px 14px; border: 1px solid #e2e8f0; }}
        article pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 16px 0; }}
        .article-meta {{ font-size: 0.85em; color: #888; margin-bottom: 24px; }}
        .cta-box {{ background: linear-gradient(135deg, #2563eb, #7c3aed); color: white; padding: 28px; border-radius: 12px; margin: 36px 0; text-align: center; }}
        .cta-box h3 {{ margin-bottom: 8px; }}
        .cta-box a {{ color: white; background: rgba(255,255,255,0.2); padding: 10px 28px; border-radius: 8px; text-decoration: none; display: inline-block; margin-top: 12px; }}
        footer {{ background: #1e293b; color: #94a3b8; padding: 40px 20px; text-align: center; font-size: 0.85em; margin-top: 60px; }}
        @media (max-width: 768px) {{
            article {{ padding: 24px 16px; }}
            article h1 {{ font-size: 1.4em; }}
        }}
    </style>
</head>
<body>
<header>
    <div class="header-inner">
        <a href="index.html" class="logo">AI Tools <span>Lab</span></a>
        <nav>
            <a href="index.html#categories">カテゴリ</a>
            <a href="index.html#articles">記事一覧</a>
        </nav>
    </div>
</header>
<div class="article-container">
    <div class="breadcrumb"><a href="index.html">ホーム</a> &gt; {category} &gt; {title_short}</div>
    <article>
        <div class="article-meta">{date} | {category}</div>
        {content}
        <div class="cta-box">
            <h3>他のAIツールも比較してみませんか？</h3>
            <p>AI Tools Labでは30以上のAIツールを実際に使って徹底レビューしています</p>
            <a href="index.html#articles">記事一覧を見る</a>
        </div>
    </article>
</div>
<footer>
    <p>&copy; 2026 AI Tools Lab. All rights reserved.</p>
</footer>
</body>
</html>"""


def build_article_page(md_filepath: Path, output_dir: Path, slug: str) -> dict:
    """Markdown記事からHTMLページを生成"""
    article = parse_article_file(md_filepath)
    meta = article['meta']
    body_html = markdown_to_html(article['body'])

    title = meta.get('title', meta.get('keyword', 'AIツール'))
    description = meta.get('description', '')
    date = meta.get('date', '2026-03-28')[:10]
    category = 'AIツール'

    html = ARTICLE_TEMPLATE.format(
        title=title,
        title_short=title[:30] + '...' if len(title) > 30 else title,
        description=description,
        date=date,
        category=category,
        content=body_html,
    )

    out_path = output_dir / f"{slug}.html"
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return {'slug': slug, 'title': title, 'path': str(out_path)}


def build_all():
    """全記事をHTMLに変換"""
    articles_dir = Path(__file__).parent.parent / 'affiliate-generator' / 'output'
    output_dir = Path(__file__).parent

    if not articles_dir.exists():
        print("記事ディレクトリが見つかりません")
        return []

    # 日本語→英語マッピング（部分一致）
    ja_to_en = {
        'AI画像生成': 'ai-image-generation',
        'AI動画編集': 'ai-video-editing',
        'AIエージェント': 'ai-agent',
        'AI文章作成': 'ai-writing',
        'AIコード生成': 'ai-code-generation',
        'AI翻訳ツール': 'ai-translation',
        'AIプレゼン作成': 'ai-presentation',
        'AI議事録ツール': 'ai-minutes',
        'AIライティングツール': 'ai-writing-tools',
        'AIチャットボット': 'ai-chatbot',
        'AI副業': 'ai-side-job',
        'ChatGPT': 'chatgpt',
        '代替ツール': 'alternatives',
        '無料': 'free',
        'おすすめ': 'recommended',
        '比較': 'comparison',
        '最新': 'latest',
        '初心者': 'beginner',
        '稼ぎ方': 'how-to-earn',
        'server_comparison': 'server-comparison',
        'vpn_comparison': 'vpn-comparison',
        'レンタルサーバー': 'server-comparison',
        'VPN': 'vpn',
        'Claude_vs': 'claude-vs-chatgpt',
    }

    def make_slug(filename: str) -> str:
        """ファイル名からURL-safeなスラッグを生成"""
        slug = filename
        for ja, en in ja_to_en.items():
            slug = slug.replace(ja, en)
        # 残りの日本語文字を除去
        slug = re.sub(r'[^\x00-\x7F]', '', slug)
        # 日付部分を保持しつつ整形
        slug = re.sub(r'[_\s]+', '-', slug).strip('-')
        slug = re.sub(r'-+', '-', slug)
        return slug.lower()

    results = []
    for md_file in sorted(articles_dir.glob('*.md')):
        slug = make_slug(md_file.stem)

        info = build_article_page(md_file, output_dir, slug)
        print(f"Built: {info['path']} ({info['title']})")
        results.append(info)

    return results


if __name__ == '__main__':
    results = build_all()
    print(f"\n{len(results)}ページを生成しました")
