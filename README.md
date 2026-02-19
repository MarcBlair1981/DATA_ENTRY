# Manual Entry Engine 🤖

A robust automation tool for entering translations and data into the Backoffice system.

## 🚀 Setup (New PC / First Time)

1.  **Install Python**
    *   Ensure you have Python installed (Download from [python.org](https://www.python.org/downloads/)).
    *   **Important:** Check the box "Add Python to PATH" during installation.

2.  **Clone / Download this Folder**
    *   Place it anywhere on your computer.

3.  **Install Dependencies (One-Time)**
    *   Double-click **`install_dependencies.bat`**.
    *   This will install the necessary libraries and browser engines automatically.

---

## 🎮 How to Run (Daily)

1.  **Launch the App**
    *   Double-click **`run_engine.bat`**.
    *   A black window will open (leave it open).
    *   The app should automatically open in your web browser at `http://127.0.0.1:8001`.

2.  **Import Your Data**
    *   **Drag & Drop** your `data.csv` file into the app (Note: `data.csv` is NOT included in this repo for privacy).
    *   Select your mode:
        *   **Standard Import:** Processes the file normally.
        *   **Verify Only:** Checks data without making changes.
    *   **Check "Backfill English?"** if you want to fill in empty English source text.
    *   Click **Run Import**.

3.  **The "Human Step"**
    *   A Chrome browser will open.
    *   **Log In** to the Backoffice.
    *   Navigate to the **Labels** page (or **Questions** page if running Question Mode).
    *   *You have 45 seconds to do this.*

4.  **Sit Back**
    *   The bot will take control.
    *   Watch the status log in the web app.
    *   Green messages = Success.

---

## 🛠️ Features

*   **Smart "Resume" Logic:** Checks if an entry exists before adding it.
*   **Questions Mode:** Can create new Questions (if missing) or update existing ones by finding the "Translate" icon.
*   **Safety:** Handles popups, "Save" button glitches, and network delays.
*   **Privacy:** Does not upload your CSVs to the cloud (they are `.gitignored`).

## ⚠️ Troubleshooting

*   **Bot doesn't move?** Ensure you are on the correct page (Labels or Questions) before the timer expires.
*   **"Python not found"?** Re-install Python and ensure "Add to PATH" is checked.
