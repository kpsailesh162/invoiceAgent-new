from typing import Callable, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from ..monitoring.metrics import MetricsCollector

class TaskQueue:
    def __init__(
        self,
        max_workers: int = 4,
        queue_size: int = 1000
    ):
        self.logger = logging.getLogger(__name__)
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.metrics = MetricsCollector()
        self.running = True
    
    async def start(self):
        """Start worker tasks"""
        workers = [
            asyncio.create_task(self._worker())
            for _ in range(self.workers)
        ]
        await asyncio.gather(*workers)
    
    async def stop(self):
        """Stop worker tasks"""
        self.running = False
        await self.queue.join()
        self.executor.shutdown(wait=True)
    
    async def enqueue(self, task: Callable, *args, **kwargs):
        """Add task to queue"""
        await self.queue.put((task, args, kwargs))
        self.metrics.queue_size.set(self.queue.qsize())
    
    async def _worker(self):
        """Worker process to handle tasks"""
        while self.running:
            try:
                task, args, kwargs = await self.queue.get()
                self.metrics.active_workers.inc()
                
                try:
                    # Execute task in thread pool
                    result = await asyncio.get_event_loop().run_in_executor(
                        self.executor,
                        task,
                        *args,
                        **kwargs
                    )
                    
                    self.metrics.invoice_processed.inc()
                except Exception as e:
                    self.logger.error(f"Task failed: {str(e)}", exc_info=True)
                    self.metrics.invoice_errors.inc()
                
                self.queue.task_done()
                self.metrics.active_workers.dec()
                self.metrics.queue_size.set(self.queue.qsize())
            except Exception as e:
                self.logger.error(f"Worker error: {str(e)}", exc_info=True) 