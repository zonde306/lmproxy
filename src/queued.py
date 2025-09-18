import time
from queue import Queue
from asyncio import Lock
from typing import TypeVar
from collections import deque

Task = TypeVar("Task")


class WeightedPriorityScheduler:
    def __init__(
        self,
        n_priorities: int,
        weights: list[int] | None = None,
        max_wait_seconds: int = 300,
    ):
        """
        :param n_priorities: 优先级数量（1 最高，n 最低）
        :param weights: 各优先级权重列表，如 [5, 3, 2, 1]，长度必须 == n_priorities
        :param max_wait_seconds: 任务最大等待时间（超时自动提升优先级）
        """
        if weights is None:
            # 默认：优先级越高权重越大，但最低优先级也有基础权重
            weights = [n_priorities - i for i in range(n_priorities)]
        assert len(weights) == n_priorities, "权重数量必须等于优先级数量"

        self.n_priorities = n_priorities
        self.weights = weights
        self.max_wait_seconds = max_wait_seconds

        # 初始化队列和锁
        self.queues = [Queue() for _ in range(n_priorities)]
        self.locks = [Lock() for _ in range(n_priorities)]

        # 统计处理数量（用于轮询）
        self.task_counters = [0] * n_priorities
        self.total_processed = 0

        # 记录任务入队时间（用于老化）
        self.enqueue_times = [
            dict() for _ in range(n_priorities)
        ]  # task_id -> timestamp
        self.task_id_counter = 0
        self.task_id_lock = Lock()

        # 构建调度轮盘（加权轮询序列）
        self.schedule_wheel = self._build_schedule_wheel()
        self.wheel_index = 0

    def _build_schedule_wheel(self):
        """构建加权轮询序列，如 weights=[3,1] → [0,0,0,1]"""
        wheel = []
        for priority_idx, weight in enumerate(self.weights):
            wheel.extend([priority_idx] * weight)
        return deque(wheel)

    def _get_next_priority_index(self):
        """获取下一个应服务的优先级索引（循环轮询）"""
        if not self.schedule_wheel:
            return 0  # fallback
        idx = self.schedule_wheel[0]
        self.schedule_wheel.rotate(-1)  # 轮转
        return idx

    async def put(self, task: Task, priority: int):
        """插入任务"""
        if not 1 <= priority <= self.n_priorities:
            raise ValueError("Invalid priority")
        idx = priority - 1

        async with self.task_id_lock:
            task_id = self.task_id_counter
            self.task_id_counter += 1

        # 包装任务：加入入队时间
        wrapped_task = {
            "id": task_id,
            "data": task,
            "enqueue_time": time.time(),
            "original_priority": priority,
        }

        async with self.locks[idx]:
            self.queues[idx].put(wrapped_task)
            self.enqueue_times[idx][task_id] = time.time()

    async def _promote_stale_tasks(self):
        """老化机制：提升等待超时任务的优先级"""
        current_time = time.time()
        for idx in range(self.n_priorities - 1, 0, -1):  # 从最低优先级往上检查
            async with self.locks[idx]:
                # 重建队列，提取超时任务并提升
                promoted = []
                remaining = []
                while not self.queues[idx].empty():
                    t = self.queues[idx].get()
                    if current_time - t["enqueue_time"] > self.max_wait_seconds:
                        # 提升到上一优先级（但不能超过P1）
                        new_idx = max(0, idx - 1)
                        t["enqueue_time"] = current_time  # 重置等待时间
                        promoted.append((new_idx, t))
                    else:
                        remaining.append(t)

                # 放回未超时任务
                for t in remaining:
                    self.queues[idx].put(t)

                # 将超时任务放入更高优先级队列
                for new_idx, t in promoted:
                    async with self.locks[new_idx]:
                        self.queues[new_idx].put(t)
                        self.enqueue_times[new_idx][t["id"]] = current_time
                    # 从原队列时间记录中删除
                    self.enqueue_times[idx].pop(t["id"], None)

    async def get(self) -> tuple[Task, int]:
        """Worker 获取下一个任务"""
        await self._promote_stale_tasks()  # 每次调度前检查老化

        # 按加权轮询顺序尝试获取任务
        start_index = self._get_next_priority_index()
        attempts = 0
        max_attempts = self.n_priorities

        while attempts < max_attempts:
            idx = (start_index + attempts) % self.n_priorities
            async with self.locks[idx]:
                if not self.queues[idx].empty():
                    task = self.queues[idx].get()
                    # 清理 enqueue_times
                    self.enqueue_times[idx].pop(task["id"], None)
                    self.task_counters[idx] += 1
                    self.total_processed += 1
                    return task["data"], idx + 1  # 返回原始任务数据和优先级
            attempts += 1

        return None, None  # 无任务
