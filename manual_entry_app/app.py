import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from engine.splash_labels_bot import SplashLabelBot
import threading
import queue
import logging

# --- Setup ---
app = FastAPI()

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount Static & Templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- Logging & Status ---
# Simple in-memory log storage for the UI to poll
log_queue = []
current_status = {"state": "IDLE", "progress": 0, "total": 0, "message": "Ready"}
# Control Flags
pause_event = threading.Event()
pause_event.set() # Initially NOT paused (set = running, clear = paused)
stop_event = threading.Event()

def add_log(message, level="INFO"):
    entry = {"message": message, "level": level}
    log_queue.append(entry)
    # Keep only last 1000 logs
    if len(log_queue) > 1000:
        log_queue.pop(0)

def update_status(state, message=None, progress=None, total=None):
    current_status["state"] = state
    if message: current_status["message"] = message
    if progress is not None: current_status["progress"] = progress
    if total is not None: current_status["total"] = total

# --- Bot Wrapper ---
def run_bot_task(file_path: str, mode: str, backfill_en: bool = False, workflow_mode: str = "labels"):
    """
    Runs the bot in a background thread.
    mode: 'import' or 'verify'
    """
    update_status("RUNNING", f"Starting {mode} process...", 0, 0)
    add_log(f"Starting process with file: {os.path.basename(file_path)}", "INFO")
    if backfill_en:
        add_log("Feature Enabled: Backfill Missing English", "INFO")
    add_log(f"Workflow Mode: {workflow_mode.upper()}", "INFO")
    
    # Reset flags
    pause_event.set() 
    stop_event.clear()

    try:
        bot = SplashLabelBot(
            log_callback=add_log,
            status_callback=update_status,
            pause_event=pause_event,
            stop_event=stop_event
        )
        bot.run(file_path, mode=mode, backfill_en=backfill_en, workflow_mode=workflow_mode)
        update_status("COMPLETED", "Process finished successfully.")
        add_log("Process Complete.", "SUCCESS")
    except Exception as e:
        update_status("ERROR", f"Error: {str(e)}")
        add_log(f"Critical Error: {str(e)}", "ERROR")
    finally:
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def handle_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Form(...),
    backfill_en: str = Form("false"),
    workflow_mode: str = Form("labels") # 'labels' or 'questions'
):
    if current_status["state"] == "RUNNING" or current_status["state"] == "PAUSED":
        return JSONResponse(status_code=400, content={"message": "A task is already running."})

    # Save file
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Clear previous logs
    log_queue.clear()
    
    # Start Task
    background_tasks.add_task(run_bot_task, file_path, mode, backfill_en == "true", workflow_mode)
    
    return {"message": "Task started", "filename": file.filename, "mode": mode}

@app.get("/status")
async def get_status():
    return {
        "status": current_status,
        "logs": log_queue[-50:] # Return last 50 logs for polling
    }

@app.post("/pause")
async def pause_task():
    if current_status["state"] == "RUNNING":
        pause_event.clear() # Blocks the bot
        current_status["state"] = "PAUSED"
        add_log("⏸️ Process Paused", "WARNING")
        return {"message": "Paused"}
    return {"message": "Not running"}

@app.post("/resume")
async def resume_task():
    if current_status["state"] == "PAUSED":
        pause_event.set() # Unblocks
        current_status["state"] = "RUNNING"
        add_log("▶️ Process Resumed", "INFO")
        return {"message": "Resumed"}
    return {"message": "Not paused"}

@app.post("/stop")
async def stop_task():
    if current_status["state"] in ["RUNNING", "PAUSED"]:
        stop_event.set()
        # Ensure it unpauses to actually hit the stop check
        pause_event.set() 
        add_log("🛑 Stop Signal Sent...", "WARNING")
    return {"message": "Stop signal sent"}

@app.get("/download_logs")
async def download_logs():
    # Format logs
    log_content = "Manual Entry Engine - Execution Log\n"
    log_content += "="*50 + "\n"
    for entry in log_queue:
        log_content += f"[{entry['level']}] {entry['message']}\n"
    
    return HTMLResponse(
        content=log_content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=execution_log.txt"}
    )

if __name__ == "__main__":
    import uvicorn
    # Using port 8001 to avoid conflict with potential zombie processes on 8000
    uvicorn.run(app, host="127.0.0.1", port=8001)
