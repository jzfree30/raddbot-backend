import os
import re
import time
import threading
import subprocess
import zipfile
from flask import Flask, request, jsonify, send_from_directory, after_this_request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUSTCOIN_PATH = os.path.join(BASE_DIR, "rustcoin")
PACKS_DIR = os.path.join(BASE_DIR, "packs")

tasks = {}
download_lock = threading.Lock()
is_downloading = False
current_query = ""

def ensure_executable():
    if os.path.exists(RUSTCOIN_PATH):
        os.chmod(RUSTCOIN_PATH, 0o755)

def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

def auto_delete_file(file_path, delay=420):
    time.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Error borrando archivo: {e}")

def run_download_task(task_id, query, option, page=1):
    global is_downloading, current_query
    try:
        os.makedirs(PACKS_DIR, exist_ok=True)
        files_before = set(os.listdir(PACKS_DIR))

        # Enviar saltos de página 'n' necesarios según la página actual
        page_commands = "n\n" * (page - 1)
        input_commands = f"{query}\n{page_commands}d\n{option}\nq\n"
        
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
        created_files = [f for f in new_files if os.path.isfile(os.path.join(PACKS_DIR, f))]

        if not created_files:
            tasks[task_id] = {"status": "error", "message": "No se generó ningún archivo."}
            return

        if len(created_files) > 1:
            clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', query)
            zip_filename = f"{clean_name}_p{page}_completo.zip"
            zip_path = os.path.join(PACKS_DIR, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_name in created_files:
                    file_full_path = os.path.join(PACKS_DIR, file_name)
                    zipf.write(file_full_path, arcname=file_name)
                    try:
                        os.remove(file_full_path)
                    except Exception:
                        pass

            final_filename = zip_filename
        else:
            final_filename = created_files[0]

        file_path = os.path.join(PACKS_DIR, final_filename)
        tasks[task_id] = {"status": "completed", "file": final_filename}
        threading.Thread(target=auto_delete_file, args=(file_path, 420), daemon=True).start()

    except Exception as e:
        tasks[task_id] = {"status": "error", "message": str(e)}
    finally:
        with download_lock:
            is_downloading = False
            current_query = ""

@app.route('/api/search', methods=['POST'])
def search():
    ensure_executable()
    data = request.get_json() or {}
    query = data.get('query', '')
    page = int(data.get('page', 1))

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        page_commands = "n\n" * (page - 1)
        input_commands = f"{query}\n{page_commands}q\n"

        process = subprocess.Popen(
            [RUSTCOIN_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, _ = process.communicate(input=input_commands, timeout=30)
        clean_output = clean_ansi(stdout)
        
        lines = [l.strip() for l in clean_output.split('\n') if l.strip() and re.match(r'^\d+\.', l.strip())]
        
        # Detectar si existe el comando [n]ext en la salida
        has_next = "[n]ext" in clean_output
        
        return jsonify({
            "results": lines,
            "page": page,
            "has_next": has_next
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/start_download', methods=['GET'])
def start_download():
    global is_downloading, current_query
    ensure_executable()
    query = request.args.get('query', '')
    option = request.args.get('option', '1')
    page = int(request.args.get('page', 1))

    if not query:
        return jsonify({"error": "Falta la búsqueda"}), 400

    with download_lock:
        if is_downloading:
            return jsonify({
                "success": False, 
                "busy": True,
                "message": f"⚠️ El servidor está procesando otro archivo ('{current_query}'). Espera 1-2 minutos."
            })
        
        is_downloading = True
        current_query = query

    task_id = f"{hash(query)}_{option}_p{page}_{int(time.time())}"
    tasks[task_id] = {"status": "downloading"}

    thread = threading.Thread(target=run_download_task, args=(task_id, query, option, page))
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
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return response

    return send_from_directory(PACKS_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
