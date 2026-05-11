import docker
import tempfile
import os
from config.settings import ALLOW_CODE_WRITING, DOCKER_SANDBOX_IMAGE

class CodeSandbox:
    def __init__(self):
        self.docker = docker.from_env()
    def run_python(self, code, timeout=10):
        if not ALLOW_CODE_WRITING:
            return "Code execution disabled."
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            f.flush()
            try:
                container = self.docker.containers.run(
                    DOCKER_SANDBOX_IMAGE,
                    command=f"python {os.path.basename(f.name)}",
                    volumes={os.path.dirname(f.name): {'bind': '/sandbox', 'mode': 'ro'}},
                    working_dir='/sandbox',
                    mem_limit='256m',
                    network_mode='none',
                    remove=True,
                    detach=False,
                    timeout=timeout
                )
                return container.decode('utf-8')
            except Exception as e:
                return f"Sandbox error: {e}"
            finally:
                os.unlink(f.name)

sandbox = CodeSandbox()
