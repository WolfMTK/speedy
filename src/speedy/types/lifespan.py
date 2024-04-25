from typing import (Callable,
                    AsyncContextManager,
                    TypeVar,
                    Mapping,
                    Any,
                    Union)

AppType = TypeVar('AppType')

StatelessLifespan = Callable[[AppType], AsyncContextManager[None]]
StatefulLifespan = Callable[[AppType], AsyncContextManager[Mapping[str, Any]]]
Lifespan = Union[StatelessLifespan[AppType], StatefulLifespan[AppType]]
