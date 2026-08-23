import os
import re
import subprocess
from flask import Flask, request, jsonify
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
    return jsonify({"status": "RADDCRAFT Backend Direct Link Active", "executable_exists": os.path.exists(RUSTCOIN_PATH)})

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
        
        stdout, _ = process.communicate(input=f"{query}\nq\n", timeout=30)
        clean_output = clean_ansi(stdout)
        
        lines = []
        for line in clean_output.split('\n'):
            line = line.strip()
            if line and re.match(r'^\d+\.', line):
                lines.append(line)
            
        return jsonify({"results": lines})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_link', methods=['GET'])
def get_link():
    ensure_executable()
    query = request.args.get('query', '')
    option = request.args.get('option', '1')

    if not query:
        return jsonify({"error": "Falta el parámetro query"}), 400

    try:
        # Enviar comandos: Búsqueda -> "o" (obtener enlace) -> número de opción
        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, _ = process.communicate(input=f"{query}\no\n{option}\nq\n", timeout=40)
        clean_output = clean_ansi(stdout)

        # Buscar cualquier patrón de URL en la salida de rustcoin
        urls = re.findall(r'https?://[^\s]+', clean_output)

        if urls:
            # Retorna el enlace extraído directamente al cliente
            return jsonify({"success": True, "download_url": urls[0]})
        else:
            return jsonify({"error": "No se pudo extraer el enlace directo"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
