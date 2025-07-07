import uuid
import typing
import dataclasses

@dataclasses.dataclass
class Request:
    id: uuid.UUID = uuid.uuid4()
    metadata: dict[str, typing.Any] = {}
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["chat", "text"]
