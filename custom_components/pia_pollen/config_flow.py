import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOCALITIES, LANGUAGES, DEFAULT_LANG


class PIAPollenConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(f"pia_pollen_{user_input['locality']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Polen PIA – {user_input['locality'].capitalize()}",
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required("locality", default="palma"): vol.In(LOCALITIES),
            vol.Required("lang", default=DEFAULT_LANG): vol.In(LANGUAGES),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
