from sqlmodel import Field, SQLModel


class Message(SQLModel):
    content: str = Field(max_length=1024)
