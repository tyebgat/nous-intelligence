import os
import subprocess
import asyncio
import httpx

class RunLocalServer:
    def __init__(self, detailed_logs: bool = False):
        #gets the absolute path of the root dir
        self.base_dir = os.path.dirname(os.path.abspath(__file__))


        self.server_exe = os.path.join(self.base_dir, "Ollama server", "llama-server.exe")
        self.model_path = os.path.join(self.base_dir, "models", "llama-3.2-1b-instruct-q4_k_m.gguf")

        self.detailes_logs = detailed_logs
    
    async def launch_server(self, timeout: int = 30) -> None:
        print("Checking local AI server")

        cmd = [
            self.server_exe,
            "-m", self.model_path,
            "--port", "8080",
            "-c", "2048"
        ]

        #launches it as a background process
        creation_flags = 0 if self.detailes_logs else subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(cmd, creationflags=creation_flags)

        print("Loading model into ram...")
        async with httpx.AsyncClient() as client:
            for _ in range(timeout):
                try:
                    response = await client.get("http://localhost:8080/health")
                    if response.status_code == 200:
                        print("Local Server is active!")
                        return
                except httpx.ConnectError:
                    await asyncio.sleep(1)

        #if the loop finishes
        self.stop_server()
        raise TimeoutError("The local server timed out or failed to start.")
    
    def stop_server(self) -> None:
        if self.process:
            print("Shutting down local LLM...")
            self.process.terminate()
            self.process.wait()
            self.process = None
            print("Local LLM closed with no problems.")
