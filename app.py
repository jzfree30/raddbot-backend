import os
import re
import glob
import subprocess
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUSTCOIN_PATH = os.path.join(BASE_DIR, "rustcoin")
PACKS_DIR = os.path.join(BASE_DIR, "packs")

def ensure_executable():
    if os.path.exists(RUSTCOIN_PATH):
        os.chmod(RUSTCOIN_PATH, 0o755)

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def upload_to_pixeldrain(file_path):
    """Sube el archivo descargado a Pixeldrain para dar un link directo de descarga."""
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://pixeldrain.com/api/file',
                files={'file': f}
            )
        data = response.json()
        if data.get('success'):
            file_id = data.get('id')
            return f"https://pixeldrain.com/api/file/{file_id}?download"
    except Exception as e:
        print(f"Error subiendo archivo: {e}")
    return None

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "RADDCRAFT Backend Active", "executable_exists": os.path.exists(RUSTCOIN_PATH)})

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
        return jsonify({"error": "Falta la búsqueda"}), 400

    try:
        # 1. Asegurar carpeta packs
        os.makedirs(PACKS_DIR, exist_ok=True)
        
        # Registrar archivos existentes antes de la descarga
        files_before = set(os.listdir(PACKS_DIR))

        # 2. Ejecutar rustcoin simulando la entrada exacta de Termux:
        # Búsqueda -> 'd' (download) -> número de opción -> 'q' (quit)
        input_commands = f"{query}\nd\n{option}\nq\n"
        
        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=BASE_DIR,
            text=True
        )
        
        stdout, stderr = process.communicate(input=input_commands, timeout=90)

        # 3. Detectar el nuevo archivo descargado en 'packs'
        files_after = set(os.listdir(PACKS_DIR))
        new_files = list(files_after - files_before)

        download_file = None
        if new_files:
            download_file = os.path.join(PACKS_DIR, new_files[0])
        else:
            # Si no se detectó por diferencia, buscar el más reciente en packs
            all_files = [os.path.join(PACKS_DIR, f) for f in os.listdir(PACKS_DIR) if os.path.isfile(os.path.join(PACKS_DIR, f))]
            if all_files:
                download_file = max(all_files, key=os.path.getmtime)

        if download_file and os.path.exists(download_file):
            # 4. Subir a la nube para generar link directo
            download_url = upload_to_pixeldrain(download_file)
            
            # Limpiar el archivo local para no llenar el disco del servidor
            try:
                os.remove(download_file)
            except:
                pass

            if download_url:
                return jsonify({"success": True, "download_url": download_url})

        return jsonify({"error": "No se pudo procesar la descarga del archivo"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
