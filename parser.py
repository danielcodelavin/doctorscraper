"""
HTML Parsing Utility
Converts raw HTML to clean Markdown for token-efficient LLM processing.
"""

import re
from pathlib import Path
from html.parser import HTMLParser

RAW_HTML_DIR = Path("./data/raw_html")
PARSED_MD_DIR = Path("./data/parsed_markdown")
PARSED_MD_DIR.mkdir(parents=True, exist_ok=True)
ACTIVE_SOURCE_PREFIXES = ("gesund_bund_",)

# Tags to skip entirely (including their content)
SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript", "svg", "iframe", "form"}
# Tags that map to markdown
BLOCK_TAGS = {"p", "div", "section", "article", "main", "li", "tr"}
HEADING_TAGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}


class HTMLToMarkdown(HTMLParser):
    def __init__(self):
        super().__init__()
        self.output = []
        self.skip_depth = 0
        self.current_tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return

        self.current_tag_stack.append(tag)

        if tag in HEADING_TAGS:
            self.output.append(f"\n{HEADING_TAGS[tag]} ")
        elif tag == "br":
            self.output.append("\n")
        elif tag == "a":
            href = dict(attrs).get("href", "")
            self.output.append(f"[")
            self.current_tag_stack.append(("a_href", href))
        elif tag in BLOCK_TAGS:
            self.output.append("\n")
        elif tag == "li":
            self.output.append("\n- ")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth > 0:
            return

        if tag == "a" and self.current_tag_stack:
            # Find the href
            href = ""
            while self.current_tag_stack:
                item = self.current_tag_stack.pop()
                if isinstance(item, tuple) and item[0] == "a_href":
                    href = item[1]
                    break
            if href:
                self.output.append(f"]({href})")
            else:
                self.output.append("]")
        elif tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self.output.append("\n")

        if self.current_tag_stack and self.current_tag_stack[-1] == tag:
            self.current_tag_stack.pop()

    def handle_data(self, data):
        if self.skip_depth > 0:
            return
        text = data.strip()
        if text:
            self.output.append(text + " ")

    def get_markdown(self):
        text = "".join(self.output)
        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.strip()
        return text


def parse_html_to_markdown(html_content: str) -> str:
    """Convert HTML string to clean Markdown."""
    parser = HTMLToMarkdown()
    parser.feed(html_content)
    return parser.get_markdown()


def process_all_html_files():
    """Process all HTML files in raw_html directory."""
    html_files = []
    for prefix in ACTIVE_SOURCE_PREFIXES:
        html_files.extend(sorted(RAW_HTML_DIR.glob(f"{prefix}*.html")))

    active_stems = {html_file.stem for html_file in html_files}
    for md_file in PARSED_MD_DIR.glob("*.md"):
        if md_file.stem not in active_stems:
            md_file.unlink()

    print(f"[parser] Found {len(html_files)} HTML files to process.")
    processed = 0

    for html_file in html_files:
        try:
            html_content = html_file.read_text(encoding="utf-8")
            markdown = parse_html_to_markdown(html_content)

            if len(markdown) < 20:
                print(f"  Skipping {html_file.name} (too little content)")
                continue

            md_file = PARSED_MD_DIR / f"{html_file.stem}.md"
            md_file.write_text(markdown, encoding="utf-8")
            processed += 1
        except Exception as e:
            print(f"  Error parsing {html_file.name}: {e}")

    print(f"[parser] Processed {processed} files to Markdown.")
    return processed


if __name__ == "__main__":
    process_all_html_files()
