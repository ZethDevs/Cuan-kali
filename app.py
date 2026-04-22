import requests
from flask import Flask, render_template, jsonify
import re
import threading
import time
from datetime import datetime
import markdown

app = Flask(__name__)

README_URL = "https://raw.githubusercontent.com/alistaitsacle/free-llm-api-keys/refs/heads/main/README.md"

# Cache global
cached_data = {
    'tables': [],
    'how_to_use_html': '',
    'works_with_html': '',
    'supported_models_html': '',
    'changelog_html': '',
    'last_update': None,
    'error_msg': None
}
update_in_progress = False

def extract_section(md_text, heading_text):
    """
    Mengekstrak konten setelah heading yang mengandung `heading_text`
    hingga heading berikutnya dengan level yang sama atau lebih tinggi.
    """
    lines = md_text.splitlines()
    start_idx = None
    heading_level = 0

    # Cari baris heading yang mengandung heading_text
    for i, line in enumerate(lines):
        if re.match(r'^#{1,6}\s+', line):
            # Ambil teks heading tanpa karakter '#'
            h_text = re.sub(r'^#{1,6}\s+', '', line).strip()
            if heading_text in h_text:
                start_idx = i
                heading_level = len(re.match(r'^(#{1,6})', line).group(1))
                break

    if start_idx is None:
        return ""

    content_lines = []
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        # Hentikan jika bertemu heading dengan level <= heading_level
        if re.match(r'^#{1,' + str(heading_level) + r'}\s+', line):
            break
        content_lines.append(line)

    return '\n'.join(content_lines).strip()

def parse_readme(md_text):
    """Parse lengkap README: tabel + section konten."""
    # 1. Parse tabel (seperti sebelumnya)
    heading_pattern = r'^###\s+(.*?)$'
    sections = []
    current_title = None
    current_table_lines = []
    lines = md_text.splitlines()

    for line in lines:
        heading_match = re.match(heading_pattern, line)
        if heading_match:
            if current_title is not None and current_table_lines:
                sections.append({
                    'title': current_title,
                    'lines': current_table_lines
                })
            current_title = heading_match.group(1).strip()
            current_table_lines = []
            continue

        if current_title is not None:
            if '|' in line:
                # Abaikan baris pemisah header (|----|)
                if re.match(r'^[\s\|:\-]+$', line):
                    continue
                current_table_lines.append(line)

    if current_title is not None and current_table_lines:
        sections.append({'title': current_title, 'lines': current_table_lines})

    tables = []
    for section in sections:
        title = section['title']
        lines = section['lines']
        if not lines:
            continue
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip() != '']
        rows = []
        for line in lines[1:]:
            cells = [c.strip() for c in line.split('|') if c.strip() != '']
            if cells:
                rows.append(cells)
        if headers and rows:
            tables.append({'title': title, 'headers': headers, 'rows': rows})

    # 2. Ekstrak section konten dengan fungsi baru
    how_to_use_md = extract_section(md_text, 'How to Use')
    works_with_md = extract_section(md_text, 'Works With')
    supported_models_md = extract_section(md_text, 'Supported Models')
    changelog_md = extract_section(md_text, 'Changelog')

    # Konversi Markdown ke HTML
    md = markdown.Markdown(extensions=['fenced_code', 'tables'])
    how_to_use_html = md.convert(how_to_use_md) if how_to_use_md else "<p>Tidak ada data.</p>"
    works_with_html = markdown.Markdown(extensions=['tables']).convert(works_with_md) if works_with_md else "<p>Tidak ada data.</p>"
    supported_models_html = markdown.Markdown(extensions=['tables']).convert(supported_models_md) if supported_models_md else "<p>Tidak ada data.</p>"
    changelog_html = markdown.Markdown(extensions=['tables']).convert(changelog_md) if changelog_md else "<p>Tidak ada data.</p>"

    return {
        'tables': tables,
        'how_to_use_html': how_to_use_html,
        'works_with_html': works_with_html,
        'supported_models_html': supported_models_html,
        'changelog_html': changelog_html
    }

def fetch_and_parse():
    """Mengambil README, mem-parse, dan menyimpan ke cache global."""
    global cached_data, update_in_progress
    update_in_progress = True
    try:
        response = requests.get(README_URL, timeout=10)
        response.raise_for_status()
        content = response.text
        parsed = parse_readme(content)
        cached_data.update(parsed)
        cached_data['last_update'] = datetime.now()
        cached_data['error_msg'] = None
        print(f"[{cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S')}] Data berhasil diperbarui.")
    except Exception as e:
        cached_data['error_msg'] = f"Gagal update: {str(e)}"
        print(f"[ERROR] {cached_data['error_msg']}")
    finally:
        update_in_progress = False

def background_updater():
    while True:
        fetch_and_parse()
        time.sleep(300)  # 5 menit

# Jalankan background thread
thread = threading.Thread(target=background_updater, daemon=True)
thread.start()

@app.route('/')
def index():
    return render_template('index.html', **cached_data)

@app.route('/refresh', methods=['POST'])
def refresh():
    if not update_in_progress:
        threading.Thread(target=fetch_and_parse, daemon=True).start()
        return jsonify({'status': 'started'})
    else:
        return jsonify({'status': 'already in progress'}), 409

if __name__ == '__main__':
    fetch_and_parse()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)  # debug=False untuk production
