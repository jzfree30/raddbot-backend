import os
import re
import time
import threading
import subprocess
from flask import Flask, request, jsonify, send_from_directory, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUSTCOIN_PATH = os.path.join(BASE_DIR, "rustcoin")
PACKS_DIR = os.path.join(BASE_DIR, "packs")

tasks = {}

def ensure_executable():
    if os.path.exists(RUSTCOIN_PATH):
        os.chmod(RUSTCOIN_PATH, 0o755)

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def auto_delete_file(file_path, delay=420): # Timer de respaldo: 7 minutos
    time.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Archivo eliminado por tiempo límite: {file_path}")
    except Exception as e:
        print(f"Error en borrado automático: {e}")

def run_download_task(task_id, query, option):
    try:
        os.makedirs(PACKS_DIR, exist_ok=True)
        files_before = set(os.listdir(PACKS_DIR))

        input_commands = f"{query}\nd\n{option}\nq\n"
        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=BASE_DIR,
            text=True
        )
        process.communicate(input=input_commands, timeout=600)

        files_after = set(os.listdir(PACKS_DIR))
        new_files = list(files_after - files_before)

        filename = None
        if new_files:
            filename = new_files[0]
        else:
            all_files = [f for f in os.listdir(PACKS_DIR) if os.path.isfile(os.path.join(PACKS_DIR, f))]
            if all_files:
                filename = max(all_files, key=lambda x: os.path.getmtime(os.path.join(PACKS_DIR, x)))

        if filename:
            file_path = os.path.join(PACKS_DIR, filename)
            tasks[task_id] = {"status": "completed", "file": filename}
            
            # Si el usuario no descarga el archivo, se borra automáticamente en 7 mins
            threading.Thread(target=auto_delete_file, args=(file_path, 420), daemon=True).start()
        else:
            tasks[task_id] = {"status": "error", "message": "No se generó el archivo."}
    except Exception as e:
        tasks[task_id] = {"status": "error", "message": str(e)}

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
        
        lines = [l.strip() for l in clean_output.split('\n') if l.strip() and re.match(r'^\d+\.', l.strip())]
        return jsonify({"results": lines})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/start_download', methods=['GET'])
def start_download():
    ensure_executable()
    query = request.args.get('query', '')
    option = request.args.get('option', '1')

    if not query:
        return jsonify({"error": "Falta la búsqueda"}), 400

    task_id = f"{hash(query)}_{option}_{int(time.time())}"
    tasks[task_id] = {"status": "downloading"}

    thread = threading.Thread(target=run_download_task, args=(task_id, query, option))
    thread.start()

    return jsonify({"success": True, "task_id": task_id})

@app.route('/api/check_status', methods=['GET'])
def check_status():
    task_id = request.args.get('task_id', '')
    task = tasks.get(task_id)

    if not task:
        return jsonify({"status": "not_found"}), 404

    if task["status"] == "completed":
        file_url = f"{request.host_url}files/packs/{task['file']}"
        return jsonify({"status": "completed", "download_url": file_url})

    return jsonify({"status": task["status"]})

@app.route('/files/packs/<path:filename>')
def serve_pack(filename):
    file_path = os.path.join(PACKS_DIR, filename)

    @after_this_request
    def remove_file(response):
        # Borrado inmediato tras ser entregado al navegador del usuario
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Archivo eliminado inmediatamente tras la entrega: {file_path}")
        except Exception as e:
            print(f"Error borrando archivo post-entrega: {e}")
        return response

    return send_from_directory(PACKS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
