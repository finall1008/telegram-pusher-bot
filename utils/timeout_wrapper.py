import signal
import asyncio
import threading
import sys
import time
import concurrent.futures as ftrs

from typing import *
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from asyncio import AbstractEventLoop
from enum import Enum
from functools import wraps, partial, singledispatch
from inspect import iscoroutinefunction
from queue import Empty
from multiprocessing import Process, Queue


__all__ = (
    'TimeLimitReached',
    'WrapType',
    'wrap_async',
    'timeout',
)


class TimeLimitReached(RuntimeError):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def _raise_exception(exception_type: type, time: float, func: Callable[..., Any], _from: Optional[Exception] = None):
    raise exception_type(f"Time exceeded given bound {time}s when running callable {func!r}.") from _from


def wrap_async(
        loop_or_func: Union[AbstractEventLoop, Callable[..., Any]],
        executor: Executor = None):

    if isinstance(loop_or_func, AbstractEventLoop):
        return _wrap_async(loop_or_func, executor)
    elif callable(loop_or_func) and isinstance(executor, (Executor, type(None))):
        return _wrap_async(asyncio.get_event_loop(), executor)(loop_or_func)
    else:
        raise TypeError("Expected first argument to be an event loop or a callable.")


def _wrap_async(loop: AbstractEventLoop, executor: Executor):
    def decorator(func):
        @ wraps(func)
        async def wrapped(*arg, **kwargs):
            return await loop.run_in_executor(executor, partial(func, *arg, **kwargs))
        return wrapped
    return decorator


class WrapType(Enum):
    SIGNAL = 'signal'
    ASYNC = 'async'
    FUTURE = 'future'
    PROCESS = 'process'
    TIMER = 'timer'


AnyCallable = Callable[..., Any]

@ overload
def timeout(
        timeout: Optional[float],
        exception_type: type,
        wrap_type: WrapType) -> Callable[[AnyCallable], AnyCallable]: ...

@ overload
def timeout(
        func: AnyCallable,
        exception_type: type,
        wrap_type: WrapType) -> AnyCallable: ...

def timeout(
        timeout_or_func = None,
        exception_type = TimeLimitReached,
        wrap_type = WrapType.PROCESS):
    '''Used to wrap a function to raise exception after certain timeout. Note that the running function would not be aborted unless `wrap_type` is set to `WrapType.SIGNAL` or `WrapType.PROCESS`.

    Args:
        timeout: Timeout in seconds. No timeout is applied if None is passed. If 0 is passed, when calling the wrapped function, an instant exception would be raised if `wrap_type` is `WrapType.MULTI_THREADING`, or would behave the same as None is passed under other `wrap_type`s.

        exception: The exception type to be raised when timeout happens.

        wrap_type: Control the method of counting time. Note that the running function would be terminated only if `wrap_type` is `WrapType.SIGNAL` or `WrapType.PROCESS`.
    '''

    if callable(timeout_or_func):
        return _timeout(None, exception_type, wrap_type)(timeout_or_func)
    else:
        return _timeout(timeout_or_func, exception_type, wrap_type)


def _timeout(timeout, exception_type, wrap_type):
    def decorator_signal(func: Callable[..., Any]) -> Callable[..., Any]:

        @ wraps(func)
        def wrapped(*args, timeout: float = timeout, **kwargs):
            def handler(signum, frame):
                _raise_exception(exception_type, timeout, func)

            if timeout:
                old_handler = signal.signal(signal.SIGALRM, handler)
                signal.setitimer(signal.ITIMER_REAL, timeout)
            try:
                return func(*args, **kwargs)
            finally:
                if timeout:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old_handler)

        return wrapped


    def decorator_async(func: Callable[..., Any]) -> Callable[..., Any]:
        @ wraps(func)
        def wrapped(*args, timeout: float = timeout, **kwargs):
            loop = asyncio.new_event_loop()
            afunc = func if iscoroutinefunction(func) else wrap_async(loop)(func)
            try:
                return loop.run_until_complete(asyncio.wait_for(afunc(*args, **kwargs), timeout))
            except asyncio.TimeoutError as exc:
                _raise_exception(exception_type, timeout, func, exc)
            finally:
                loop.close()

        return wrapped


    def decorator_future(func: Callable[..., Any]) -> Callable[..., Any]:
        @ wraps(func)
        def wrapped(*args, timeout: float = timeout, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    future = pool.submit(func, *args, **kwargs)
                    result = future.result(timeout=timeout)
                except ftrs.TimeoutError as exc:
                    _raise_exception(exception_type, timeout, func, exc)
                else:
                    return result
                finally:
                    pool.shutdown(wait=False)

        return wrapped


    def decorator_process(func: Callable[..., Any]) -> Callable[..., Any]:
        @ wraps(func)
        def wrapped(*args, timeout: float = timeout, **kwargs):
            def handler(exc: Optional[Exception] = None):
                _raise_exception(exception_type, timeout, func, exc)

            timeout = 0 if timeout is None else timeout
            proc = _MultiProcessTimer(
                func,
                timeout,
                handler
            )
            flag, ret = proc(*args, **kwargs)
            if flag:
                return ret
            else:
                handler()

        return wrapped


    def decorator_timer(func: Callable[..., Any]) -> Callable[..., Any]:
        '''
        Return value of the wrapped callable must be a tuple `(flag: bool, return_value: Any)`.
        The callable should not be blocking. `flag` in the return value will be used to indicate running status.
        '''
        @ wraps(func)
        def wrapped(*args, timeout: float = timeout, **kwargs):
            original_time = time.perf_counter()
            while time.perf_counter() - original_time <= timeout:
                flag, ret = func(*args, **kwargs)
                if flag:
                    return ret
            _raise_exception(exception_type, timeout, func, exc)

        return wrapped


    mapping = {
        WrapType.SIGNAL: decorator_signal,
        WrapType.ASYNC: decorator_async,
        WrapType.FUTURE: decorator_future,
        WrapType.PROCESS: decorator_process,
        WrapType.TIMER: decorator_timer
    }
    return mapping[wrap_type]


class _MultiProcessTimer():
    def __init__(
            self,
            func: Callable[..., Any],
            timeout: float,
            handler: Callable[..., Any]):

        self.__func = func
        self.__time = timeout
        self.__handler = handler
        self.__queue = Queue(1)


    def __call__(self, *args, **kwargs):
        def __target():
            try:
                self.__queue.put(self.__func(*args, **kwargs))
            except Exception as e:
                self.__handler(e)

        __process = Process(target=__target, daemon=True)
        start_time = time.perf_counter()
        __process.start()
        while time.perf_counter() - start_time <= self.__time:
            try:
                ret = True, self.__queue.get_nowait()
            except Empty:
                ret = False, None
            else:
                break
        __process.kill()
        return ret
