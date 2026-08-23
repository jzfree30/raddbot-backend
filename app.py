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
        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Enviar consulta e inmediatamente salir con q para cerrar el proceso
        stdout, _ = process.communicate(input=f"{query}\nq\n", timeout=30)
        clean_output = clean_ansi(stdout)
        
        lines = []
        for line in clean_output.split('\n'):
            line = line.strip()
            # Capturar únicamente las líneas de resultados numerados (ej: "1. The Bloop Add-On...")
            if line and re.match(r'^\d+\.', line):
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
        # Recrear el flujo exacto de Termux: Búsqueda -> "d" (Download) -> Selección (ej: 1)
        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Envía: búsqueda -> d -> número de opción
        process.communicate(input=f"{query}\nd\n{option}\nq\n", timeout=60)

        # Buscar en la carpeta raíz y en la subcarpeta 'packs'
        target_dirs = ['.', 'packs']
        found_files = []

        for d in target_dirs:
            if os.path.exists(d):
                files = [os.path.join(d, f) for f in os.listdir(d) 
                         if os.path.isfile(os.path.join(d, f)) 
                         and not f.endswith(('.py', '.txt', '.tsv', '.json', '.md')) 
                         and f != 'rustcoin']
                found_files.extend(files)

        if found_files:
            latest_file = max(found_files, key=os.path.getmtime)
            return send_file(latest_file, as_attachment=True)
        else:
            return "El archivo no se encontró o no se pudo generar.", 404
    except Exception as e:
        return f"Error en la descarga: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
