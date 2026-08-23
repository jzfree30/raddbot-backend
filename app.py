from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import subprocess, os, re, stat, uuid

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/minecraft_addons"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BINARY_PATH = os.path.join(BASE_DIR, "rustcoin")

def ensure_executable():
    if os.path.exists(BINARY_PATH):
        st = os.stat(BINARY_PATH)
        os.chmod(BINARY_PATH, st.st_mode | stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

def clean_ansi(text):
    return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

def search_rustcoin(query):
    ensure_executable()
    if not os.path.exists(BINARY_PATH):
        return []
    try:
        process = subprocess.Popen(
            [BINARY_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=BASE_DIR
        )
        stdout, _ = process.communicate(input=f"{query}\nq\n", timeout=20)
        clean_output = clean_ansi(stdout)
        
        results = []
        for line in clean_output.splitlines():
            match = re.match(r'^(\d+)\.\s+(.+)', line.strip())
            if match:
                results.append(match.group(2))
        return results[:20]
    except Exception as e:
        print(f"Error en búsqueda: {e}")
        return []

def download_rustcoin_option(query, option_index, session_dir):
    ensure_executable()
    os.makedirs(session_dir, exist_ok=True)
    input_sequence = f"{query}\n{option_index}\n\ny\nq\n"
    
    try:
        process = subprocess.Popen(
            [BINARY_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=session_dir
        )
        stdout, _ = process.communicate(input=input_sequence, timeout=90)
        
        addon_files = []
        ignored_exts = ('.tsv', '.txt', '.json', '.key', '.keys', '.py', '.sh', '.log')
        
        for root, _, files in os.walk(session_dir):
            for f in files:
                if not f.endswith(ignored_exts) and not f.startswith('.') and f != "rustcoin":
                    addon_files.append(os.path.join(root, f))
        
        if not addon_files:
            for root, _, files in os.walk(BASE_DIR):
                for f in files:
                    if not f.endswith(ignored_exts) and not f.startswith('.') and f != "rustcoin":
                        addon_files.append(os.path.join(root, f))

        if not addon_files:
            return None
            
        latest_file = max(addon_files, key=os.path.getmtime)
        target_path = os.path.join(session_dir, os.path.basename(latest_file))
        if latest_file != target_path:
            os.rename(latest_file, target_path)

        return os.path.basename(target_path)
    except Exception as e:
        print(f"Error descargando: {e}")
        return None

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Servidor en línea y listo"})

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json(force=True) or {}
    query = data.get('query', '').strip()
    if not query:
        return jsonify({"results": []})
    results = search_rustcoin(query)
    return jsonify({"query": query, "results": results})

@app.route('/api/download', methods=['GET'])
def api_download():
    query = request.args.get('query', '')
    option = request.args.get('option', type=int)
    if not query or option is None:
        return "Parámetros incompletos", 400

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(DOWNLOAD_DIR, session_id)
    filename = download_rustcoin_option(query, option, session_dir)
    
    if filename:
        return redirect(f"/files/{session_id}/{filename}")
    return "Error en la descarga", 504

@app.route('/files/<session_id>/<filename>', methods=['GET'])
def serve_file(session_id, filename):
    folder = os.path.join(DOWNLOAD_DIR, session_id)
    return send_from_directory(folder, filename, as_attachment=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
