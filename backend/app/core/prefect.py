from prefect.events import Event, Resource
from pydantic import BaseModel, Field


class SynapseMessage(BaseModel):
    ...


class Message(BaseModel):
    resource: str
    payload: SynapseMessage = Field(discriminator="message_type")

    @staticmethod
    def from_event(event: Event) -> "Message":
        return Message.model_validate(
            {"resource": event.resource.id, "payload": event.payload}
        )

    def to_event(self) -> Event:
        return Event(
            event="actors.synapse.message",
            resource=Resource(
                {
                    "prefect.resource.id": self.resource,
                }
            ),
            payload=self.payload.model_dump(),
        )
