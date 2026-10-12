"""Збирає самодостатній фрагмент погоджувального макета для перегляду в розмові."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / 'docs' / 'redesign'


def build():
    source = (DESIGN / 'minimal-concepts.html').read_text(encoding='utf-8')
    css = re.search(r'<style[^>]*>([\s\S]*?)</style>', source).group(1)
    body = re.search(r'<body[^>]*>([\s\S]*?)</body>', source).group(1)
    scripts = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)</script>', body)
    if len(scripts) != 1:
        raise ValueError('Expected one application script')
    markup = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', '', body)
    code = scripts[0]
    model = (DESIGN / 'forecast-model.js').read_text(encoding='utf-8')

    # Повторно використовуємо живий макет; ізолюємо два незалежні екземпляри.
    css = css.replace(':root', ':host')
    css = re.sub(r'html(\[data-theme[^\]]*\])', r':host(\1)', css)
    css = re.sub(r'(?<!\()\[data-theme=(dark|light)\]', r':host([data-theme=\1])', css)
    css = re.sub(r'(?<![\w-])html(?![\w-])', ':host', css)
    css = re.sub(r'(?<![\w-])body(?![\w-])', '.cf-preview-body', css)
    css = re.sub(r'@media\s*\((min|max)-width\s*:', r'@container cashflow-stage (\1-width:', css)
    code = code.replace('document.documentElement', 'host')
    code = code.replace('document.body', 'bodyRoot')
    code = code.replace('document.querySelectorAll', 'appRoot.querySelectorAll')
    code = code.replace('document.querySelector', 'appRoot.querySelector')
    code = code.replace('document.getElementById', 'appRoot.getElementById')
    code = code.replace('document.addEventListener', 'appRoot.addEventListener')
    code = code.replace('document.activeElement', 'appRoot.activeElement')
    code = code.replace('new URLSearchParams(location.search)', "new URLSearchParams('')")
    code = code.replace('new URLSearchParams(window.location.search)', "new URLSearchParams('')")
    code = code.replace('window.scrollTo(0,0)', 'void 0')
    # Піктограми надає середовище inline-перегляду.
    code = re.sub(r'^const icons=.*?;\s*$', '', code, flags=re.M)
    code = re.sub(r'^const icon=.*?;\s*$', 'const icon=productIcon;', code, flags=re.M)
    # Власні токени та класи продукту не запозичують стилі оболонки перегляду.
    for token in ('card', 'btn', 'nav'):
        css = re.sub(r'\b' + token + r'\b', 'cf-' + token, css)
        markup = re.sub(r'\b' + token + r'\b', 'cf-' + token, markup)
        code = re.sub(r'\b' + token + r'\b', 'cf-' + token, code)

    shell = (DESIGN / 'inline-preview-shell.html').read_text(encoding='utf-8')
    result = shell.replace('/* PRODUCT_CSS */', css).replace('<!-- PRODUCT_MARKUP -->', markup)
    result = result.replace('/* FORECAST_MODEL */', model).replace('/* PRODUCT_SCRIPT */', code)
    if re.search(r'<!doctype\s|<\s*(?:html|head|body)(?:\s|>)', result, re.I):
        raise ValueError('Inline output must be a fragment')
    if len(result.encode('utf-8')) >= 1_000_000:
        raise ValueError('Inline output exceeds 1 MB')
    output = DESIGN / 'minimal-preview.html'
    output.write_text(result, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    build()
