import asyncio
import logging
from functools import partial
import requests

logger = logging.getLogger(__name__)


async def async_request(method, *args, **kwargs):
    loop = asyncio.get_running_loop()
    func = partial(
        getattr(requests, method),
        *args,
        **kwargs,
    )
    result = await loop.run_in_executor(None, func)
    return result


class HomeAssistantLight:
    def __init__(self, ha_host, ha_token, ha_entity, on_update) -> None:
        self.on_update = on_update
        self.connected = False
        self.current_state = None

        self.ha_host = ha_host
        self.ha_token = ha_token
        self.ha_entity = ha_entity
        self.ha_domain = "switch"

    async def set_state(self, state):
        service = "turn_on" if state else "turn_off"
        data = {
            "entity_id": self.ha_entity,
        }
        endpoint = f"/api/services/{self.ha_domain}/{service}"
        resp = await self._http_post(endpoint, data)
        updated_state = self._state_after_service(resp)
        if updated_state is not None:
            self.current_state = updated_state
            self.on_update()

    async def get_state(self):
        endpoint = f"/api/states/{self.ha_entity}"
        resp = await self._http_get(endpoint)
        return resp["state"]

    def disconnect(self):
        self.connected = False

    def connect(self):
        self.connected = True
        asyncio.get_running_loop().create_task(self.state_polling())

    async def state_polling(self):
        while self.connected:
            try:
                state = await self.get_state()
            except:
                state = "error"

            self.current_state = state
            self.on_update()

            await asyncio.sleep(60)

    def _state_after_service(self, resp):
        for change in resp:
            if change["entity_id"] == self.ha_entity:
                return change["state"]
        return None

    def _http_headers(self):
        return {
            "Authorization": f"Bearer {self.ha_token}",
            "content-type": "application/json",
        }

    async def _http_get(self, endpoint):
        resp = await async_request(
            "get",
            f"{self.ha_host}{endpoint}",
            headers=self._http_headers(),
            timeout=2,
        )
        resp.raise_for_status()
        return resp.json()

    async def _http_post(self, endpoint, data):
        resp = await async_request(
            "post",
            f"{self.ha_host}{endpoint}",
            json=data,
            headers=self._http_headers(),
            timeout=2,
        )
        resp.raise_for_status()
        return resp.json()
