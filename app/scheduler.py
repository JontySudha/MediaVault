import threading
import time

from app.database import get_enabled_creators
from app.sync import sync_creator


SYNC_INTERVAL_SECONDS = 15 * 60

_scheduler_thread = None
_stop_event = threading.Event()


def scheduler_loop():

    print(
        "[Scheduler] Automatic sync started."
    )

    print(
        f"[Scheduler] Interval: "
        f"{SYNC_INTERVAL_SECONDS // 60} minutes"
    )

    while not _stop_event.is_set():

        try:

            creators = get_enabled_creators()

            if not creators:

                print(
                    "[Scheduler] No enabled creators."
                )

            for creator in creators:

                if _stop_event.is_set():
                    break

                creator_id = creator["id"]

                creator_name = (
                    creator.get("display_name")
                    or creator.get("username")
                    or creator.get("profile_url")
                )

                print(
                    f"[Scheduler] Syncing: "
                    f"{creator_name}"
                )

                try:

                    result = sync_creator(
                        creator_id
                    )

                    print(
                        f"[Scheduler] Finished: "
                        f"{creator_name} | "
                        f"discovered="
                        f"{result['discovered']}"
                    )

                except Exception as error:

                    print(
                        f"[Scheduler] Error syncing "
                        f"{creator_name}: {error}"
                    )

        except Exception as error:

            print(
                f"[Scheduler] Error: {error}"
            )

        print(
            f"[Scheduler] Next sync in "
            f"{SYNC_INTERVAL_SECONDS // 60} minutes."
        )

        _stop_event.wait(
            SYNC_INTERVAL_SECONDS
        )

    print(
        "[Scheduler] Automatic sync stopped."
    )


def start_scheduler():

    global _scheduler_thread

    if (
        _scheduler_thread is not None
        and _scheduler_thread.is_alive()
    ):
        return

    _stop_event.clear()

    _scheduler_thread = threading.Thread(
        target=scheduler_loop,
        daemon=True,
        name="MediaVaultScheduler",
    )

    _scheduler_thread.start()


def stop_scheduler():

    _stop_event.set()

    global _scheduler_thread

    _scheduler_thread = None