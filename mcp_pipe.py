import asyncio
import json
import logging
import os
import signal
import sys
import websockets
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("mcp_pipe")


class MCPPipe:
    def __init__(self, script_path, token):
        self.script_path = script_path
        self.token = token.strip()  # Remove any whitespace
        self.ws = None
        self.process = None
        self.running = False
        self.reconnect_delay = 1
        self.max_reconnect_delay = 60

    async def start_mcp_process(self):
        logger.info(f"Starting MCP process: {self.script_path}")
        
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            self.script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        logger.info(f"MCP process started with PID: {self.process.pid}")
        return self.process

    async def connect_websocket(self):
        uri = f"wss://api.xiaozhi.me/mcp/?token={self.token}"
        logger.info(f"Connecting to Xiaozhi WebSocket...")
        logger.info(f"Token length: {len(self.token)} characters")
        logger.info(f"Token starts with: {self.token[:10]}..." if len(self.token) > 10 else f"Token: {self.token}")
        
        try:
            self.ws = await websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10
            )
            logger.info("WebSocket connected successfully")
            self.reconnect_delay = 1
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            if "401" in str(e):
                logger.error("HTTP 401 - Token authentication failed. Please verify your XIAOZHI_TOKEN is correct.")
                logger.error("Get your token from: https://api.xiaozhi.me or your Xiaozhi account settings")
            return False

    async def read_from_process(self):
        try:
            while self.running:
                if not self.process or not self.process.stdout:
                    await asyncio.sleep(0.1)
                    continue
                
                line = await self.process.stdout.readline()
                if not line:
                    break
                
                try:
                    message = line.decode().strip()
                    if message:
                        logger.info(f"Process -> WS: {message[:100]}...")
                        
                        if self.ws and self.ws.open:
                            await self.ws.send(message)
                except Exception as e:
                    logger.error(f"Error processing message from MCP: {e}")
                    
        except Exception as e:
            logger.error(f"Error reading from process: {e}")

    async def read_from_websocket(self):
        try:
            while self.running:
                if not self.ws or not self.ws.open:
                    await asyncio.sleep(0.1)
                    continue
                
                try:
                    message = await self.ws.recv()
                    logger.info(f"WS -> Process: {message[:100]}...")
                    
                    if self.process and self.process.stdin:
                        self.process.stdin.write(f"{message}\n".encode())
                        await self.process.stdin.drain()
                        
                except websockets.exceptions.ConnectionClosed:
                    logger.warning("WebSocket connection closed")
                    break
                except Exception as e:
                    logger.error(f"Error receiving from WebSocket: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in WebSocket reader: {e}")

    async def read_process_stderr(self):
        try:
            while self.running:
                if not self.process or not self.process.stderr:
                    await asyncio.sleep(0.1)
                    continue
                
                line = await self.process.stderr.readline()
                if not line:
                    break
                
                log_message = line.decode().strip()
                if log_message:
                    logger.info(f"[MCP STDERR] {log_message}")
                    
        except Exception as e:
            logger.error(f"Error reading stderr: {e}")

    async def run(self):
        self.running = True
        
        while self.running:
            try:
                await self.start_mcp_process()
                
                connected = await self.connect_websocket()
                if not connected:
                    logger.warning(f"Retrying connection in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                    continue
                
                tasks = [
                    asyncio.create_task(self.read_from_process()),
                    asyncio.create_task(self.read_from_websocket()),
                    asyncio.create_task(self.read_process_stderr())
                ]
                
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
            finally:
                if self.ws:
                    await self.ws.close()
                if self.process:
                    self.process.terminate()
                    await self.process.wait()
                
                if self.running:
                    logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    async def stop(self):
        logger.info("Stopping MCP Pipe...")
        self.running = False
        
        if self.ws:
            await self.ws.close()
        
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()


async def main():
    token = os.getenv("XIAOZHI_TOKEN")
    
    if not token:
        logger.error("=" * 60)
        logger.error("ERROR: XIAOZHI_TOKEN environment variable not set")
        logger.error("=" * 60)
        logger.error("Please set your token:")
        logger.error("  export XIAOZHI_TOKEN=your_actual_token")
        logger.error("")
        logger.error("Get your token from:")
        logger.error("  - Xiaozhi account settings")
        logger.error("  - https://api.xiaozhi.me")
        logger.error("=" * 60)
        sys.exit(1)
    
    token = token.strip()
    
    if len(token) < 10:
        logger.error("=" * 60)
        logger.error("ERROR: XIAOZHI_TOKEN seems too short")
        logger.error(f"Token length: {len(token)} characters")
        logger.error("Please verify your token is correct")
        logger.error("=" * 60)
        sys.exit(1)
    
    script_path = os.getenv("MCP_SCRIPT", "reminder_server.py")
    
    logger.info("=" * 60)
    logger.info("Starting Xiaozhi MCP Reminder Server")
    logger.info("=" * 60)
    logger.info(f"Script: {script_path}")
    logger.info(f"Token: {token[:10]}...{token[-4:]}")
    logger.info("=" * 60)
    
    pipe = MCPPipe(script_path, token)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(pipe.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await pipe.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await pipe.stop()


if __name__ == "__main__":
    asyncio.run(main())
