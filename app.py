import os
import re
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

RUSTCOIN_PATH = os.path.join(os.path.dirname(__file__), "rustcoin")

def ensure_executable():
    if os.path.exists(RUSTCOIN_PATH):
        os.chmod(RUSTCOIN_PATH, 0o755)

def clean_ansi(text):
    """Limpia secuencias de escape ANSI (colores y códigos de terminal)"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "Server running", "executable_exists": os.path.exists(RUSTCOIN_PATH)})

@app.route('/api/search', methods=['POST'])
def search():
    ensure_executable()
    data = request.get_json() or {}
    query = data.get('query', '')
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        result = subprocess.run([RUSTCOIN_PATH, query], capture_output=True, text=True, timeout=30)
        raw_output = result.stdout
        
        # Limpiar colores ANSI
        clean_output = clean_ansi(raw_output)
        
        lines = []
        for line in clean_output.split('\n'):
            line = line.strip()
            # Omitir líneas vacías, mensajes de login o banners de RUSTCOIN
            if not line or "RUSTCOIN" in line or "PlayFab" in line or "v1.0" in line or "2J" in line:
                continue
            lines.append(line)
            
        return jsonify({"results": lines})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download():
    ensure_executable()
    query = request.args.get('query', '')
    option = request.args.get('option', '1')

    if not query:
        return "Falta el parámetro query", 400

    try:
        # Guardar lista de archivos previos antes de ejecutar
        before_files = set(os.listdir('.'))
        
        subprocess.run([RUSTCOIN_PATH, query, option], check=True, timeout=90)

        after_files = set(os.listdir('.'))
        new_files = list(after_files - before_files)

        # Filtrar solo archivos de contenido, ignorando configs o logs como keys.tsv
        valid_files = [f for f in new_files if not f.endswith(('.py', '.txt', '.tsv', '.json', '.md')) and f != 'rustcoin']

        if not valid_files:
            # Si no hay nuevos en el diff, buscar los más recientes ignorando system files
            all_files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.endswith(('.py', '.txt', '.tsv', '.json', '.md')) and f != 'rustcoin']
            if all_files:
                valid_files = [max(all_files, key=os.path.getmtime)]

        if valid_files:
            return send_file(valid_files[0], as_attachment=True)
        else:
            return "El archivo no se encontró o no se pudo generar.", 404
    except Exception as e:
        return f"Error en la descarga: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
