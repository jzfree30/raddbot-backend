import os
import subprocess
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Ruta absoluta al ejecutable rustcoin
RUSTCOIN_PATH = os.path.join(os.path.dirname(__file__), "rustcoin")

def ensure_executable():
    """Asegura que el ejecutable rustcoin tenga permisos +x"""
    if os.path.exists(RUSTCOIN_PATH):
        os.chmod(RUSTCOIN_PATH, 0o755)

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
        # Ejecuta rustcoin pasándole la consulta
        result = subprocess.run([RUSTCOIN_PATH, query], capture_output=True, text=True, timeout=30)
        output = result.stdout.strip()
        lines = [line.strip() for line in output.split('\n') if line.strip()]
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
        # Ejecuta rustcoin para procesar la opción de descarga
        subprocess.run([RUSTCOIN_PATH, query, option], check=True, timeout=60)

        # Busca el archivo descargado en el directorio actual
        files = [f for f in os.listdir('.') if os.path.isfile(f) and not f.endswith(('.py', '.txt', '.md')) and f != 'rustcoin']
        if files:
            latest_file = max(files, key=os.path.getmtime)
            return send_file(latest_file, as_attachment=True)
        else:
            return "El archivo no se generó correctamente.", 404
    except Exception as e:
        return f"Error en la descarga: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
