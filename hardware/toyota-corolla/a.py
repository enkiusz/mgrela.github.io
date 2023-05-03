from enum import Enum, auto


class E(Enum):
	V1 = auto()
	V2 = auto()


print(list(E))
