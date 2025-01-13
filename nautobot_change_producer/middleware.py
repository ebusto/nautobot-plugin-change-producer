import atexit
import collections
import copy
import dictdiffer
import orjson
import re
import socket
import threading
import time
import typing

from django.conf             import settings
from django.db               import transaction
from django.db.models        import signals
from nautobot.core.api.utils import get_serializer_for_model

from .client import NATS


# Ignore senders that provide duplicate or sensitive information.
IGNORE = re.compile(
    "|".join([
        "django.contrib",
        "nautobot.extras.models.change_logging",
        "nautobot.extras.models.customfields",
        "nautobot.extras.models.datasources",
        "nautobot.extras.models.jobs",
        "nautobot.extras.models.secrets",
        "nautobot.extras.models.tags.TaggedItem",
        "nautobot.users.models",
        "nautobot_rbac.models",
    ])
)

# Retrieve the configuration.
config = settings.PLUGINS_CONFIG["nautobot_change_producer"]["config"]

# Client calls and signal handling must be serialized.
lock = threading.Lock()

# The server hostname is static, and included in each message.
server = socket.gethostname()


# Change represents a per-record change. The "record" is the serialized instance
# prior to any updates. The "instance" is the last unserialized instance,
# intentionally deferred until the end to avoid unnecessary serialization, as
# only the first and last records are of interest.
class Change:
    def __init__(self, event: str, record: object) -> None:
        self.event  = event
        self.record = record

        self.complete = None
        self.instance = None


# Transaction stores a request and the changes that occurred while processing
# that request.
class Transaction:
    def __init__(self, request: object) -> None:
        self.changes = collections.defaultdict(list)

        # Model serializers check the request method and only allow a depth
        # greater than zero for GET requests.
        self.request = copy.copy(request)
        self.request.method = "GET"

        # Define the serialization context, with a sufficient depth to ensure we
        # don't just serialize stub objects, which aren't as useful to consumers
        # as nested objects.
        self.context = {
            "depth": 2, "request": self.request,
        }

        # Requests performed through the UI don't have the version attribute,
        # which the Nautobot custom fields serializer uses to determine the
        # format.
        if not hasattr(self.request, "version"):
            setattr(self.request, "version", settings.REST_FRAMEWORK["DEFAULT_VERSION"])

    # Log a change for the specified object.
    def change(self, instance: object, event: str) -> None:
        if self.ignore(instance):
            return

        self.changes[instance.pk].append(
            Change(event, self.serialize(instance))
        )

    # Mark all changes as complete for the specified object.
    def commit(self, instance: object) -> None:
        if self.ignore(instance):
            return

        changes = self.changes[instance.pk]

        for change in changes:
            change.complete = True
            change.instance = instance

    # Determine whether or not this object should be ignored.
    def ignore(self, instance: object) -> bool:
        return IGNORE.match(
            instance.__class__.__module__ + "." +
            instance.__class__.__qualname__
        )

    # Return the dictionary representation of the object.
    def serialize(self, instance: object) -> dict:
        if not instance.present_in_database:
            return None

        try:
            fn = get_serializer_for_model(instance)

            record = fn(instance, context=self.context)

            return record.data

        except Exception:
            return None

    def signal_pre_delete(self, instance: object, **kwargs) -> None:
        self.change(instance, "delete")

    def signal_pre_save(self, instance: object, **kwargs) -> None:
        action = "create"

        if hasattr(instance, "present_in_database") and instance.present_in_database:
            action = "update"

            # Retrieve the current record from the database, in order to
            # generate the differences between the previous and updated records.
            instance = instance.__class__.objects.get(pk=instance.pk)

        self.change(instance, action)

    def signal_post_delete(self, instance: object, **kwargs) -> None:
        self.commit(instance)

    def signal_post_save(self, instance: object, **kwargs) -> None:
        self.commit(instance)


# Middleware tracks changes by observing signals emitted for models created,
# updated, or deleted during a request.
class Middleware:
    def __init__(self, get_response: typing.Callable) -> None:
        self.client       = None
        self.get_response = get_response

        atexit.register(self.close)

    @transaction.atomic
    def __call__(self, request: object) -> object:
        # GET and GraphQL requests will not result in changes.
        if request.method == "GET" or "/graphql" in request.get_full_path():
            return self.get_response(request)

        tx = Transaction(request)

        with lock:
            connections = [
                ( signals.post_delete, tx.signal_post_delete ),
                ( signals.post_save,   tx.signal_post_save   ),
                ( signals.pre_delete,  tx.signal_pre_delete  ),
                ( signals.pre_save,    tx.signal_pre_save    ),
            ]

            for signal, receiver in connections:
                signal.connect(receiver)

            response = self.get_response(request)

            for signal, receiver in connections:
                signal.disconnect(receiver)

            common = self.common(request)

            for _, changes in tx.changes.items():
                for change in changes:
                    # Discard partial changes lacking a "post" signal.
                    if not change.complete:
                        continue

                    message = self.message(tx, change)

                    if not message:
                        continue

                    self.publish(
                        orjson.dumps({**common, **message},
                            default = lambda obj: str(obj)
                        )
                    )

        return response

    # Close ensures the client disconnects gracefully.
    def close(self):
        with lock:
            if self.client:
                self.client.close()
                self.client = None

    # Common metadata from the request, to be included with each message.
    def common(self, request: object) -> dict:
        addr = request.META["REMOTE_ADDR"]
        user = request.user.get_username()

        # Handle being behind a proxy.
        if "HTTP_X_FORWARDED_FOR" in request.META:
            addr = request.META["HTTP_X_FORWARDED_FOR"]

        # RFC3339 timestamp.
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        return {
            "@timestamp": timestamp,
            "request": {
                "addr": addr,
                "user": user,
            },
            "response": {
                "host": server,
            },
        }

    # Return the difference between two models represented as dictionaries.
    def diff(self, a: dict, b: dict) -> dict:
        detail = {}

        for diff in dictdiffer.diff(a, b, expand=True):
            field = diff[1]

            # Array change.
            if isinstance(field, list):
                field = field[0]

            if not field:
                continue

            detail[field] = [
                dictdiffer.dot_lookup(a, field),
                dictdiffer.dot_lookup(b, field),
            ]

        return detail

    # Return the message to be published for the change.
    def message(self, tx: Transaction, change: Change) -> dict:
        # Track the initial model for diffing.
        initial = None

        if change.event != "delete":
            initial, change.record = change.record, tx.serialize(change.instance)

        # Ignore objects that don't serialize, or lack an "object_type" field,
        # such as CablePath.
        if not change.record or "object_type" not in change.record:
            return None

        message = {
            "event":  change.event,
            "model":  change.record["object_type"],
            "record": change.record,
        }

        # In order for a consumer to easily retrieve the record from Nautobot,
        # include the absolute URL.
        if "url" in change.record:
            message["@url"] = change.record["url"]

        if change.event == "update":
            detail = self.diff(initial, change.record)

            if not detail:
                return None

            message["detail"] = detail

        return message

    # Attempt to publish the message, retrying if necessary with an increasing
    # delay between attempts. Called with the lock held.
    def publish(self, message: bytes) -> None:
        attempts = 10

        for n in range(attempts):
            try:
                # Create a client if necessary.
                if not self.client:
                    self.client = NATS(**config)

                self.client.publish(message)

            except Exception as e:
                # Attempt to gracefully disconnect, and then clear the client to
                # ensure the next attempt reconnects.
                self.client.close()
                self.client = None

                # Last attempt? Propagate the exception to the caller.
                if n+1 == attempts:
                    raise e

                # Trying again? Sleep for a bit.
                time.sleep(n)

            else:
                # Success!
                return
