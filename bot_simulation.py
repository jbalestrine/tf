import subprocess
import time
import requests
import sys
import os

HUB_URL = "http://localhost:8080/echo-chat"

def start_process(script_name):
    """Spins up a file as an independent background process."""
    return subprocess.Popen(
        [sys.executable, script_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

def read_port_from_worker(process):
    """Reads the console logs of a worker to catch its random dynamic port."""
    for line in iter(process.stdout.readline, ''):
        print(f"[Worker Log] {line.strip()}")
        if "LLM Dynamic Worker Online ->" in line:
            # Extract the URL from the log string
            url = line.split("->")[-1].strip()
            return url
    return None

def run_simulation():
    processes = []
    try:
        # 1. Start the Core Traffic Hub
        print("⚡ Starting Main Traffic Hub...")
        hub_proc = start_process("main_hub.py")
        processes.append(hub_proc)
        time.sleep(2) # Give the hub a moment to bind to port 8080

          # 1. Spin up Bot A's Computational Node
        print("🤖 Launching Bot A (Instance 1)...")
        bot_a_proc = start_process("dynamic_worker.py")
        processes.append(bot_a_proc)
        bot_a_url = read_port_from_worker(bot_a_proc)

        # 2. Spin up Bot B's Computational Node
        print("🤖 Launching Bot B (Instance 2)...")
        bot_b_proc = start_process("dynamic_worker.py")
        processes.append(bot_b_proc)
        bot_b_url = read_port_from_worker(bot_b_proc)

        # 🟢 NEW: Give Mistral a warm-up window to finish loading its weights
        print("\n⏳ Allowing Mistral models to fully load into memory (20s)...")
        time.sleep(20) 

        # Explicitly verify properties match before shooting payloads
        print(f"\n✅ Simulation Cluster Ready!")
        print(f"   - Hub Target: {HUB_URL}")
        print(f"   - Bot A Engine: {bot_a_url}")
        print(f"   - Bot B Engine: {bot_b_url}\n" + "="*50)

        # 4. Set the conversational parameters
        session_id = "autonomous_debate_01"
        max_turns = 5 # Prevent infinite loops/API runaway
        
        # Starting prompt to anchor the dialogue
        current_message = "Let us discuss the best deployment strategy. Why should an operations team prefer Canary deployments over Blue-Green deployments?"
        
        print(f"\n🎬 Starting automated chat session on topic: '{current_message}'\n")

        for turn in range(1, max_turns + 1):
            print(f"\n[TURN {turn}] ────►")
            
            # --- TURN PART 1: BOT A EVALUATES MESSAGE ---
            print(f"💭 Bot A processing...")
            response_a = requests.post(HUB_URL, json={
                "message": current_message,
                "session_id": f"{session_id}_bot_a",
                "worker_url": bot_a_url
            })
            
            if response_a.status_code != 200:
                print(f"❌ Bot A failed to answer: {response_a.text}")
                break
                
            bot_a_output = response_a.json().get('response')
            print(f"🤖 [Bot A says]:\n{bot_a_output}\n")
            
            # Pause slightly so logs are readable in real-time
            time.sleep(2)

            # --- TURN PART 2: BOT B EVALUATES BOT A's OUTPUT ---
            print(f"💭 Bot B processing...")
            response_b = requests.post(HUB_URL, json={
                "message": bot_a_output,
                "session_id": f"{session_id}_bot_b",
                "worker_url": bot_b_url
            })
            
            if response_b.status_code != 200:
                print(f"❌ Bot B failed to answer: {response_b.text}")
                break
                
            bot_b_output = response_b.json().get('response')
            print(f"🤖 [Bot B says]:\n{bot_b_output}\n")
            
            # The output of Bot B becomes the input message for Bot A on the next turn
            current_message = bot_b_output
            time.sleep(2)

        print("="*50 + "\n🏁 Automated session complete. Shutting down cluster safely...")

    except KeyboardInterrupt:
        print("\n⚠️ Simulation interrupted by user. Cleaning up background instances...")
    finally:
        # Gracefully kill all spawned processes so ports don't get stuck open
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                proc.kill()
        print("💀 All background ports flushed and closed.")

if __name__ == '__main__':
    run_simulation()
