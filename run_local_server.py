import os
import subprocess
import asyncio
import httpx

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

class RunLocalServer:
    def __init__(self, show_ollama_server_logs: bool = False):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.server_exe = os.path.join(self.base_dir, "Ollama server", "llama-server.exe")
        self.model_path = os.path.join(self.base_dir, "models", "llama-3.2-1b-instruct-q4_k_m.gguf")
        self.show_ollama_server_logs = show_ollama_server_logs

    async def launch_server(self, timeout: int = 30) -> None:
        print(f"{YELLOW}Checking local AI server{RESET}")

        cmd = [
            self.server_exe,
            "-m", self.model_path,
            "--port", "8080",
            "-c", "2048"
        ]

        creation_flags = 0 if self.show_ollama_server_logs else subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(cmd, creationflags=creation_flags)

        print(f"{YELLOW}Loading model into ram...{RESET}")
        async with httpx.AsyncClient() as client:
            for _ in range(timeout):
                try:
                    response = await client.get("http://localhost:8080/health")
                    if response.status_code == 200:
                        print(f"{GREEN}Local Server is active!{RESET}")
                        return
                except httpx.ConnectError:
                    await asyncio.sleep(1)

        self.stop_server()
        raise TimeoutError(f"{RED}The local server timed out or failed to start.{RESET}")

    def stop_server(self) -> None:
        if hasattr(self, 'process') and self.process:
            print(f"{YELLOW}Shutting down local LLM...{RESET}")
            self.process.terminate()
            self.process.wait()
            self.process = None
            print(f"{GREEN}Local LLM closed with no problems.{RESET}")
