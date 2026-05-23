"""
setup_accounts.py — One-time login setup for ChatGPT and Gemini.
Run once on fresh install. Opens each platform so you can sign in.
After login, close Chrome — sessions persist automatically.
"""
import subprocess, time, sys, os as _os

# Example: r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME = _os.environ.get("CHROME_EXE", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
FLAGS = "--disable-blink-features=AutomationControlled,--no-first-run,--no-default-browser-check"
# Example: r"C:\Users\YourName\AppData\Roaming\npm\agent-browser.cmd"
AGENT = _os.environ.get("AGENT_BROWSER", _os.path.join(_os.path.expanduser("~"), "AppData", "Roaming", "npm", "agent-browser.cmd"))
# Example: r"C:\Users\YourName\submind-chatgpt-profile"
CHATGPT_PROFILE = _os.environ.get("CHATGPT_PROFILE", _os.path.join(_os.path.expanduser("~"), "submind-chatgpt-profile"))
# Example: r"C:\Users\YourName\submind-gemini-profile"
GEMINI_PROFILE = _os.environ.get("GEMINI_PROFILE", _os.path.join(_os.path.expanduser("~"), "submind-gemini-profile"))

def setup():
    print("="*60)
    print("Joodei Browser — One-Time Setup")
    print("="*60)
    
    # Step 1: ChatGPT
    print("\n[1/2] Opening ChatGPT for login...")
    subprocess.run([AGENT, "close", "--all"], capture_output=True, timeout=10)
    time.sleep(1)
    subprocess.run([AGENT, "--executable-path", CHROME, "--args", FLAGS, "--headed",
                    "--profile", CHATGPT_PROFILE,
                    "--session-name", "chatgpt", "open", "https://chatgpt.com"],
                   timeout=30)
    input("\n>>> Log into ChatGPT in the opened browser, then press Enter...")
    
    # Step 2: Gemini
    print("\n[2/2] Opening Gemini for login...")
    subprocess.run([AGENT, "close", "--all"], capture_output=True, timeout=10)
    time.sleep(1)
    subprocess.run([AGENT, "--executable-path", CHROME, "--args", FLAGS, "--headed",
                    "--profile", GEMINI_PROFILE,
                    "--session-name", "gemini", "open", "https://gemini.google.com/app"],
                   timeout=30)
    input("\n>>> Log into Gemini (Google account) in the opened browser, then press Enter...")
    
    print("\n✅ Setup complete! Both accounts are now saved.")
    print("Run: python joodei_browser_mcp.py --transport stdio")
    print("Then restart OpenCode/Claude Desktop")

if __name__ == "__main__":
    setup()
