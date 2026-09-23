from threading import Lock


_lock = Lock()

_cancelled_creators = set()
_running_processes = {}
_running_tasks = set()


def start_task(creator_id):
    with _lock:
        _cancelled_creators.discard(creator_id)
        _running_tasks.add(creator_id)


def request_cancel(creator_id):
    process = None

    with _lock:
        _cancelled_creators.add(creator_id)
        process = _running_processes.get(creator_id)

    if process is not None:
        try:
            process.terminate()
        except Exception:
            pass


def is_cancelled(creator_id):
    if creator_id is None:
        return False

    with _lock:
        return creator_id in _cancelled_creators


def register_process(creator_id, process):
    with _lock:
        _running_processes[creator_id] = process


def unregister_process(creator_id, process=None):
    with _lock:
        current = _running_processes.get(creator_id)

        if process is None or current is process:
            _running_processes.pop(creator_id, None)


def is_task_running(creator_id):
    with _lock:
        return creator_id in _running_tasks


def finish_task(creator_id):
    with _lock:
        _running_processes.pop(creator_id, None)
        _running_tasks.discard(creator_id)
        _cancelled_creators.discard(creator_id)


def clear_cancel(creator_id):
    with _lock:
        _cancelled_creators.discard(creator_id)
