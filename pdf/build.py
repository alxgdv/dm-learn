"""Собирает dm_answers.pdf из dm_qa.json.

Запуск из любой папки:  python3 pdf/build.py
Нужен tectonic (brew install tectonic).
"""
import json, os, re, shutil, subprocess, sys, tempfile
from itertools import groupby

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
data = json.load(open(os.path.join(ROOT, 'dm_qa.json')))
tmp = tempfile.mkdtemp(prefix='dm_pdf_')
tex_path = os.path.join(tmp, 'dm_answers.tex')
out = open(tex_path, 'w')

ESC = {'\\': r'\textbackslash{}', '#': r'\#', '%': r'\%', '&': r'\&', '_': r'\_',
       '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
UNI = {'∞': r'$\infty$', '₂': r'$_2$', '∼': r'$\sim$'}


def inline(s, maths):
    """Markdown inline -> LaTeX. Math is already replaced by \x00N\x00 placeholders."""
    s = ''.join(ESC.get(c, UNI.get(c, c)) for c in s)
    s = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', s, flags=re.S)
    s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'\\emph{\1}', s, flags=re.S)

    def back(m):
        tex, disp = maths[int(m.group(1))]
        if not disp:
            return '$' + tex + '$'
        m2 = re.search(r'\\tag\{[^}]*\}', tex)
        tag = m2.group(0) if m2 else ''
        body = tex.replace(tag, '') if tag else tex
        return '\n\\[\\fitdisp{%s}{%s}%s\\]\n' % ('4em' if tag else '0pt', body, tag)
    return re.sub(r'\x00(\d+)\x00', back, s)


def protect(s):
    maths = []

    def keep(m):
        disp = m.group(1) is not None
        maths.append((m.group(1) if disp else m.group(2), disp))
        return '\x00%d\x00' % (len(maths) - 1)
    s = re.sub(r'\$\$(.+?)\$\$|\$([^$]+?)\$', keep, s, flags=re.S)
    return s, maths


def md(src):
    s, maths = protect(src)
    lines = s.split('\n')
    res, i = [], 0

    def kind(l):
        if re.match(r'^\s*[-*] ', l): return 'ul'
        if re.match(r'^\s*\d+\. ', l): return 'ol'
        if l.startswith('|'): return 'table'
        if l.startswith('>'): return 'quote'
        if not l.strip(): return 'blank'
        return 'p'

    # group consecutive lines into blocks
    blocks = []
    for l in lines:
        k = kind(l)
        if k == 'p' and blocks and blocks[-1][0] in ('ul', 'ol', 'p', 'quote'):
            blocks[-1][1].append(l)          # continuation line
        elif blocks and blocks[-1][0] == k and k != 'blank':
            blocks[-1][1].append(l)
        else:
            blocks.append([k, [l]])
    for k, ls in blocks:
        if k == 'blank':
            res.append('')
        elif k == 'p':
            res.append(inline('\n'.join(ls), maths))
        elif k == 'quote':
            res.append('\\begin{quote}\n' + inline('\n'.join(l.lstrip('> ') for l in ls), maths) + '\n\\end{quote}')
        elif k in ('ul', 'ol'):
            items = []
            for l in ls:
                if kind(l) == k:
                    items.append(re.sub(r'^\s*(?:[-*]|\d+\.) ', '', l))
                else:
                    items[-1] += '\n' + l
            env = 'itemize' if k == 'ul' else 'enumerate'
            res.append('\\begin{%s}\n' % env + '\n'.join('\\item ' + inline(t, maths) for t in items) + '\n\\end{%s}' % env)
        elif k == 'table':
            rows = [r.strip().strip('|').split('|') for r in ls if not re.match(r'^\|[-|: ]+\|$', r)]
            n = len(rows[0])
            body = [' & '.join(inline(c.strip(), maths) for c in r) + r' \\' for r in rows]
            body[0] += r' \hline'
            res.append('\\begin{center}\\begin{tabular}{' + '|'.join('l' * n) + '}\n' + '\n'.join(body) + '\n\\end{tabular}\\end{center}')
    return '\n'.join(res)


def title(s):
    s, maths = protect(s)
    return inline(s, maths)


W = out.write
W(open(os.path.join(HERE, 'preamble.tex')).read())
for t, qs in groupby(data, key=lambda q: q['ticket']):
    qs = list(qs)
    tt = title(qs[0]['ticket_title'])
    W('\n\\clearpage\n\\markright{Билет %d}\n\\section*{\\boldmath %d. %s}\n' % (t, t, tt))
    W('\\addcontentsline{toc}{section}{\\protect\\numberline{%d}%s}\n' % (t, tt))
    W('{\\small\\color{gray}[Книга: %s]}\n\n' % title(qs[0]['book_ref']))
    for q in qs:
        W('\\subsection*{\\boldmath %s}\n\n' % title(q['question']))
        W(md(q['answer']) + '\n\n')
W('\\end{document}\n')
out.close()

r = subprocess.run(['tectonic', tex_path], cwd=tmp, capture_output=True, text=True)
if r.returncode != 0:
    sys.exit(r.stdout + r.stderr + '\nTeX-файл: ' + tex_path)
shutil.copy(os.path.join(tmp, 'dm_answers.pdf'), os.path.join(ROOT, 'dm_answers.pdf'))
shutil.rmtree(tmp)
print('Готово:', os.path.join(ROOT, 'dm_answers.pdf'))
