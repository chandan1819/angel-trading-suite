"""
Concurrent processing system for multiple strategies and operations.
"""

import asyncio
import threading
import logging
from typing import Dict, Any, List, Callable, Optional, Union, Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
import concurrent.futures
from queue import Queue, Empty
import time

logger = logging.getLogger(__name__)


@dataclass
class ProcessingTask:
    """Individual processing task."""
    task_id: str
    operation: Callable
    args: tuple = ()
    kwargs: dict = None
    priority: int = 0  # Higher number = higher priority
    timeout: Optional[float] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class ProcessingResult:
    """Result of processing task."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[Exception] = None
    execution_time: float = 0.0
    completed_at: datetime = None
    
    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.now()


class ConcurrentProcessor:
    """
    Concurrent processor for multiple strategies and operations.
    """
    
    def __init__(self, max_workers: int = 4, queue_size: int = 100):
        self.max_workers = max_workers
        self.queue_size = queue_size
        
        # Thread pool for CPU-bound tasks
        self.thread_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="strategy_worker"
        )
        
        # Process pool for heavy computations (optional)
        self.process_executor = None
        
        # Task management
        self.task_queue: Queue[ProcessingTask] = Queue(maxsize=queue_size)
        self.results: Dict[str, ProcessingResult] = {}
        self.active_tasks: Dict[str, concurrent.futures.Future] = {}
        
        # Statistics
        self.stats = {
            'submitted': 0,
            'completed': 0,
            'failed': 0,
            'timeout': 0,
            'cancelled': 0
        }
        
        # Control
        self._shutdown = False
        self._lock = threading.RLock()
        
        # Start processing thread
        self._processor_thread = threading.Thread(
            target=self._process_tasks,
            daemon=True
        )
        self._processor_thread.start()
        
        logger.info(f"Concurrent processor initialized with {max_workers} workers")
    
    def submit_task(self, task: ProcessingTask) -> bool:
        """
        Submit a task for processing.
        
        Args:
            task: Processing task to submit
            
        Returns:
            True if task was submitted successfully
        """
        try:
            self.task_queue.put(task, timeout=1.0)
            with self._lock:
                self.stats['submitted'] += 1
            logger.debug(f"Submitted task: {task.task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit task {task.task_id}: {e}")
            return False
    
    def submit_strategy_evaluation(self, strategy_name: str, 
                                 evaluate_func: Callable, 
                                 market_data: Any,
                                 priority: int = 0) -> str:
        """
        Submit strategy evaluation task.
        
        Args:
            strategy_name: Name of the strategy
            evaluate_func: Strategy evaluation function
            market_data: Market data for evaluation
            priority: Task priority
            
        Returns:
            Task ID
        """
        task_id = f"strategy_{strategy_name}_{int(time.time() * 1000)}"
        task = ProcessingTask(
            task_id=task_id,
            operation=evaluate_func,
            args=(market_data,),
            priority=priority,
            timeout=30.0  # 30 second timeout for strategy evaluation
        )
        
        if self.submit_task(task):
            return task_id
        else:
            raise RuntimeError(f"Failed to submit strategy evaluation: {strategy_name}")
    
    def submit_data_processing(self, operation_name: str,
                             process_func: Callable,
                             data: Any,
                             priority: int = 1) -> str:
        """
        Submit data processing task.
        
        Args:
            operation_name: Name of the operation
            process_func: Data processing function
            data: Data to process
            priority: Task priority
            
        Returns:
            Task ID
        """
        task_id = f"data_{operation_name}_{int(time.time() * 1000)}"
        task = ProcessingTask(
            task_id=task_id,
            operation=process_func,
            args=(data,),
            priority=priority,
            timeout=10.0  # 10 second timeout for data processing
        )
        
        if self.submit_task(task):
            return task_id
        else:
            raise RuntimeError(f"Failed to submit data processing: {operation_name}")
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Optional[ProcessingResult]:
        """
        Get result for a task.
        
        Args:
            task_id: Task ID
            timeout: Timeout for waiting for result
            
        Returns:
            Processing result or None if not available
        """
        start_time = time.time()
        
        while True:
            with self._lock:
                if task_id in self.results:
                    return self.results[task_id]
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                return None
            
            time.sleep(0.1)  # Small delay to avoid busy waiting
    
    def wait_for_results(self, task_ids: List[str], 
                        timeout: Optional[float] = None) -> Dict[str, ProcessingResult]:
        """
        Wait for multiple task results.
        
        Args:
            task_ids: List of task IDs to wait for
            timeout: Timeout for waiting
            
        Returns:
            Dictionary of task_id -> result
        """
        results = {}
        start_time = time.time()
        
        while len(results) < len(task_ids):
            for task_id in task_ids:
                if task_id not in results:
                    with self._lock:
                        if task_id in self.results:
                            results[task_id] = self.results[task_id]
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                break
            
            time.sleep(0.1)
        
        return results
    
    def _process_tasks(self):
        """Main task processing loop."""
        while not self._shutdown:
            try:
                # Get task from queue with priority
                task = self._get_priority_task()
                if not task:
                    time.sleep(0.1)
                    continue
                
                # Submit to thread pool
                future = self.thread_executor.submit(self._execute_task, task)
                
                with self._lock:
                    self.active_tasks[task.task_id] = future
                
                # Handle completion
                future.add_done_callback(
                    lambda f, tid=task.task_id: self._handle_task_completion(tid, f)
                )
                
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}")
                time.sleep(1.0)
    
    def _get_priority_task(self) -> Optional[ProcessingTask]:
        """Get highest priority task from queue."""
        tasks = []
        
        # Collect available tasks
        while True:
            try:
                task = self.task_queue.get_nowait()
                tasks.append(task)
                if len(tasks) >= 10:  # Limit batch size
                    break
            except Empty:
                break
        
        if not tasks:
            return None
        
        # Sort by priority (higher number = higher priority)
        tasks.sort(key=lambda t: t.priority, reverse=True)
        
        # Put back all but the highest priority task
        for task in tasks[1:]:
            try:
                self.task_queue.put_nowait(task)
            except:
                logger.warning(f"Failed to return task to queue: {task.task_id}")
        
        return tasks[0]
    
    def _execute_task(self, task: ProcessingTask) -> ProcessingResult:
        """Execute a single task."""
        start_time = time.time()
        
        try:
            # Execute the operation
            if task.timeout:
                # Use timeout for execution
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(task.operation, *task.args, **task.kwargs)
                    result = future.result(timeout=task.timeout)
            else:
                result = task.operation(*task.args, **task.kwargs)
            
            execution_time = time.time() - start_time
            
            return ProcessingResult(
                task_id=task.task_id,
                success=True,
                result=result,
                execution_time=execution_time
            )
            
        except concurrent.futures.TimeoutError:
            execution_time = time.time() - start_time
            logger.warning(f"Task {task.task_id} timed out after {execution_time:.2f}s")
            
            with self._lock:
                self.stats['timeout'] += 1
            
            return ProcessingResult(
                task_id=task.task_id,
                success=False,
                error=TimeoutError(f"Task timed out after {task.timeout}s"),
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Task {task.task_id} failed: {e}")
            
            with self._lock:
                self.stats['failed'] += 1
            
            return ProcessingResult(
                task_id=task.task_id,
                success=False,
                error=e,
                execution_time=execution_time
            )
    
    def _handle_task_completion(self, task_id: str, future: concurrent.futures.Future):
        """Handle task completion."""
        try:
            result = future.result()
            
            with self._lock:
                self.results[task_id] = result
                self.active_tasks.pop(task_id, None)
                
                if result.success:
                    self.stats['completed'] += 1
                else:
                    self.stats['failed'] += 1
            
            logger.debug(f"Task {task_id} completed: success={result.success}, "
                        f"time={result.execution_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Error handling task completion for {task_id}: {e}")
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task if it's still active.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was cancelled
        """
        with self._lock:
            future = self.active_tasks.get(task_id)
            if future and not future.done():
                cancelled = future.cancel()
                if cancelled:
                    self.active_tasks.pop(task_id, None)
                    self.stats['cancelled'] += 1
                    logger.info(f"Cancelled task: {task_id}")
                return cancelled
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        with self._lock:
            return {
                'submitted': self.stats['submitted'],
                'completed': self.stats['completed'],
                'failed': self.stats['failed'],
                'timeout': self.stats['timeout'],
                'cancelled': self.stats['cancelled'],
                'active_tasks': len(self.active_tasks),
                'queue_size': self.task_queue.qsize(),
                'max_workers': self.max_workers,
                'success_rate': (
                    self.stats['completed'] / max(1, self.stats['submitted']) * 100
                ) if self.stats['submitted'] > 0 else 0
            }
    
    def get_active_tasks(self) -> List[str]:
        """Get list of active task IDs."""
        with self._lock:
            return list(self.active_tasks.keys())
    
    def clear_results(self, older_than_minutes: int = 60):
        """Clear old results to free memory."""
        cutoff_time = datetime.now() - timedelta(minutes=older_than_minutes)
        
        with self._lock:
            old_task_ids = [
                task_id for task_id, result in self.results.items()
                if result.completed_at < cutoff_time
            ]
            
            for task_id in old_task_ids:
                del self.results[task_id]
            
            if old_task_ids:
                logger.info(f"Cleared {len(old_task_ids)} old results")
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """
        Shutdown the processor.
        
        Args:
            wait: Whether to wait for active tasks to complete
            timeout: Timeout for shutdown
        """
        logger.info("Shutting down concurrent processor")
        
        self._shutdown = True
        
        if wait:
            # Cancel remaining tasks in queue
            cancelled_count = 0
            while True:
                try:
                    task = self.task_queue.get_nowait()
                    cancelled_count += 1
                except Empty:
                    break
            
            if cancelled_count > 0:
                logger.info(f"Cancelled {cancelled_count} queued tasks")
            
            # Wait for active tasks
            if self.active_tasks:
                logger.info(f"Waiting for {len(self.active_tasks)} active tasks to complete")
                
                start_time = time.time()
                while self.active_tasks and (time.time() - start_time) < timeout:
                    time.sleep(0.5)
                
                # Force cancel remaining tasks
                with self._lock:
                    for task_id, future in list(self.active_tasks.items()):
                        if not future.done():
                            future.cancel()
                            logger.warning(f"Force cancelled task: {task_id}")
        
        # Shutdown executors
        self.thread_executor.shutdown(wait=wait)
        
        if self.process_executor:
            self.process_executor.shutdown(wait=wait)
        
        logger.info("Concurrent processor shutdown complete")


class StrategyEvaluationManager:
    """Manager for concurrent strategy evaluation."""
    
    def __init__(self, processor: ConcurrentProcessor):
        self.processor = processor
    
    def evaluate_strategies_concurrent(self, strategies: Dict[str, Callable],
                                     market_data: Any,
                                     timeout: float = 30.0) -> Dict[str, Any]:
        """
        Evaluate multiple strategies concurrently.
        
        Args:
            strategies: Dictionary of strategy_name -> evaluation_function
            market_data: Market data for evaluation
            timeout: Timeout for all evaluations
            
        Returns:
            Dictionary of strategy_name -> evaluation_result
        """
        # Submit all strategy evaluation tasks
        task_ids = {}
        for strategy_name, evaluate_func in strategies.items():
            try:
                task_id = self.processor.submit_strategy_evaluation(
                    strategy_name, evaluate_func, market_data
                )
                task_ids[strategy_name] = task_id
            except Exception as e:
                logger.error(f"Failed to submit strategy {strategy_name}: {e}")
        
        if not task_ids:
            return {}
        
        # Wait for results
        results = self.processor.wait_for_results(
            list(task_ids.values()), timeout
        )
        
        # Map results back to strategy names
        strategy_results = {}
        for strategy_name, task_id in task_ids.items():
            if task_id in results:
                result = results[task_id]
                if result.success:
                    strategy_results[strategy_name] = result.result
                else:
                    logger.error(f"Strategy {strategy_name} evaluation failed: {result.error}")
                    strategy_results[strategy_name] = None
            else:
                logger.warning(f"Strategy {strategy_name} evaluation timed out")
                strategy_results[strategy_name] = None
        
        return strategy_results