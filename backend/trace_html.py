from html.parser import HTMLParser

class MyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.div_depth = 0
        
    def handle_starttag(self, tag, attrs):
        if tag in ['img', 'br', 'hr', 'input', 'meta', 'link', 'canvas', 'svg', 'path']: return
        self.tags.append(tag)
        if tag == 'div':
            self.div_depth += 1
            attrs_dict = dict(attrs)
            id_val = attrs_dict.get('id', '')
            if id_val in ['main-app', 'view-dashboard', 'dashboard-content', 'dashboard-skeleton', 'view-screener', 'content-index', 'content-custom', 'content-history', 'resultsContainer', 'view-watchlist', 'view-journal', 'view-profile']:
                print(f'Line {self.getpos()[0]}: <div id="{id_val}"> (depth {self.div_depth})')

    def handle_endtag(self, tag):
        if tag in ['img', 'br', 'hr', 'input', 'meta', 'link', 'canvas', 'svg', 'path']: return
        if self.tags and self.tags[-1] == tag:
            self.tags.pop()
        if tag == 'div':
            self.div_depth -= 1
            if self.div_depth < 2:
                print(f'Line {self.getpos()[0]}: </div> closed below main-app depth! New depth: {self.div_depth}')

parser = MyParser()
with open('app/static/index.html', 'r', encoding='utf-8') as f:
    parser.feed(f.read())
