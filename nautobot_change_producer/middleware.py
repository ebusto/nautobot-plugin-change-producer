import dictdiffer
import orjson
import re
import socket
import time

from django.conf                  import settings
from django.db.models             import signals
from django.utils.module_loading  import import_string
from nautobot.utilities.api       import get_serializer_for_model

from .log import log


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

config = settings.PLUGINS_CONFIG["nautobot_change_producer"]


# Change describe a per-instance change. The "model" is the serialized instance
# prior to any updates. The "instance" is the last (unserialized) instance.
class Change:
    def __init__(self, event, model):
        self.event = event
        self.model = model

        self.complete = None
        self.instance = None


# Transaction stores a request and the changes that occurred.
class Transaction:
    def __init__(self, request):
        self.request = request
        self.changes = dict()

    def change(self, instance, event):
        if not self.ignore(instance):
            self.changes[id(instance)] = Change(event, self.serialize(instance))

    def commit(self, instance):
        if not self.ignore(instance):
            change = self.changes[id(instance)]

            change.complete = True
            change.instance = instance

    def ignore(self, instance):
        return IGNORE.match(
            instance.__class__.__module__ + "." + instance.__class__.__qualname__
        )

    def serialize(self, instance, prefix=""):
        if not instance.present_in_database:
            return None

        # Requests performed through the UI don"t have the version attribute,
        # which the Nautobot custom fields serializer uses to determine the
        # format.
        if not hasattr(self.request, "version"):
            setattr(self.request, "version", settings.REST_FRAMEWORK["DEFAULT_VERSION"])

        try:
            sender = instance.__class__
            record = sender.objects.get(pk=instance.pk)
        except Exception:
            record = instance

        try:
            fn = get_serializer_for_model(record, prefix)

            model = fn(record, context={"request": self.request})
            model = model.data

            # Prevent dictdiffer from trying to recurse infinitely.
            if "tags" in model:
                model["tags"] = list(model["tags"])

            return model
        except Exception as err:
            return None

    def signal_pre_delete(self, instance, **kwargs):
        self.change(instance, "delete")

    def signal_pre_save(self, instance, **kwargs):
        action = "create"

        if hasattr(instance, "present_in_database") and instance.present_in_database:
            action = "update"

        self.change(instance, action)

    def signal_post_delete(self, instance, **kwargs):
        self.commit(instance)

    def signal_post_save(self, instance, **kwargs):
        self.commit(instance)


# Tracking changes is accomplished by observing signals emitted for models
# created, updated, or deleted during a request.
class Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # GET requests will not result in changes.
        if request.method == "GET":
            return self.get_response(request)

        tx = Transaction(request)

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
        client = import_string(config["client"])(**config["config"])

        for _, change in tx.changes.items():
            if change.complete:
                message = self.message(tx, change)

                if message:
                    client.send(orjson.dumps({**common, **message}))

        client.flush()
        client.close()

        return response

    # Common metadata from the request, to be included with each message.
    def common(self, request):
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
                "host": socket.gethostname(),
            },
        }

    # Returns the difference between two models.
    def diff(self, a, b):
        detail = {}

        for diff in dictdiffer.diff(a, b, expand=True):
            field = diff[1]

            # Array change.
            if isinstance(field, list):
                field = field[0]

            detail[field] = [
                dictdiffer.dot_lookup(a, field),
                dictdiffer.dot_lookup(b, field),
            ]

        return detail

    # Returns the message to be published for the change.
    def message(self, tx, change):
        # Track the initial model for diffing.
        initial = None

        if change.event != "delete":
            initial, change.model = change.model, tx.serialize(change.instance)

        message = {
            "class": change.instance.__class__.__name__,
            "event": change.event,
            "model": change.model,
        }

        # In order for a consumer to easily retrieve the record from Nautobot,
        # include the absolute URL.
        if change.event != "delete":
            nested = tx.serialize(change.instance, "Nested")

            if nested and "url" in nested:
                message["@url"] = nested["url"]

        if change.event == "update":
            detail = self.diff(initial, change.model)

            if not detail:
                return None

            message["detail"] = detail

        return message
