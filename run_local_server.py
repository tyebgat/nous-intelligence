import os
import subprocess
import asyncio
import httpx
from paths import BASE_PATH

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
ORANGE = '\033[38m'
RESET = '\033[0m'

# Default context size for the local LLM. Kept modest on purpose: llama.cpp
# allocates the whole KV cache up front, so a huge ctx-size slows model loading
# and eats RAM for no benefit in a chat assistant flow.
DEFAULT_CTX_SIZE = 4096


class RunLocalServer:
    def __init__(
        self,
        show_ollama_server_logs: bool = False,
        model_dir: str = "",
        device: str = "cuda",
        ctx_size: int = DEFAULT_CTX_SIZE,
    ):
        if device == "cpu":
            server_dir = os.path.join(BASE_PATH, "llama-server-CPU")
        else:
            server_dir = os.path.join(BASE_PATH, "llama-server-CUDA")
        self.server_exe = os.path.join(server_dir, "llama-server.exe")
        self.model_path = os.path.join(BASE_PATH, model_dir) if model_dir else os.path.join(BASE_PATH, "models", "llama-3.2-1b-instruct-q4_k_m.gguf")
        self.show_ollama_server_logs = show_ollama_server_logs
        self.device = device
        self.ctx_size = ctx_size
        self.process = None

    async def _is_alive(self, client: httpx.AsyncClient) -> bool:
        try:
            response = await client.get("http://localhost:8080/health")
            return response.status_code == 200
        except Exception:
            return False

    async def is_running(self) -> bool:
        """True if a llama server is already answering on the shared port."""
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                return await self._is_alive(client)
        except Exception:
            return False

    async def _wait_until_ready(self, timeout: int, client: httpx.AsyncClient) -> None:
        """Poll /health every 0.25s until the server is ready or timeout hits."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if await self._is_alive(client):
                return
            await asyncio.sleep(0.25)
        raise TimeoutError("server did not become healthy in time")

    async def launch_server(self, timeout: int = 30) -> None:
        print(f"{YELLOW}Checking local AI server{RESET}")

        # Reuse a server that is already listening (e.g. left running from a
        # previous app session) instead of loading the model into RAM again.
        async with httpx.AsyncClient(timeout=2) as client:
            if await self._is_alive(client):
                print(f"{GREEN}An existing local server is already running, reusing it.{RESET}")
                print(f"{GREEN}Detected model: {self.model_path}{RESET}")
                return

            cmd = [
                self.server_exe,
                "-m", self.model_path,
                "--port", "8080",
                "--ctx-size", str(self.ctx_size),
                "--fit", "off"
            ]

            #launches it as a background process
            creation_flags = 0 if self.show_ollama_server_logs else subprocess.CREATE_NO_WINDOW
            self.process = subprocess.Popen(cmd, creationflags=creation_flags)
            print(f"{YELLOW} Detected model: {self.model_path}{RESET}")
            print(f"{YELLOW}Running on device: {self.device.upper()}{RESET}")
            print(f"{YELLOW}Loading model into ram...{RESET}")

            try:
                await self._wait_until_ready(timeout, client)
                print(f"{GREEN}Local Server is active!{RESET}")
            except TimeoutError:
                #if the loop finishes
                self.stop_server()
                raise TimeoutError(f"{RED}The local server timed out or failed to start.{RESET}")
    
    def stop_server(self) -> None:
        if hasattr(self, 'process') and self.process:
            print(f"{YELLOW}Shutting down local LLM...{RESET}")
            self.process.terminate()
            self.process.wait()
            self.process = None
            print(f"{GREEN}Local LLM closed with no problems.{RESET}")
