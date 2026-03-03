from __future__ import annotations
import logging
import xml.etree.ElementTree as ET
from datetime import timedelta

import aiohttp
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    BASE_URL,
    LEVEL_PREFIX,
    SCAN_INTERVAL_HOURS,
    LEVEL_LABELS,
    TREND_LABELS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    locality = entry.data["locality"]
    lang = entry.data["lang"]
    url = BASE_URL.format(locality=locality, lang=lang)

    coordinator = PIAPollenCoordinator(hass, url, locality, lang)
    await coordinator.async_config_entry_first_refresh()

    entities = [
        PIAPollenSensor(coordinator, taxon_name, locality)
        for taxon_name in coordinator.data
    ]
    async_add_entities(entities, update_before_add=False)


# ──────────────────────────────────────────────────────────────
#  Coordinator
# ──────────────────────────────────────────────────────────────


class PIAPollenCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, url: str, locality: str, lang: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"PIA Polen {locality}",
            update_interval=timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self.url = url
        self.locality = locality
        self.lang = lang

    async def _async_update_data(self) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.url, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        raise UpdateFailed(f"HTTP {resp.status} desde {self.url}")
                    text = await resp.text()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error de red: {err}") from err

        _LOGGER.debug("PIA XML recibido (%d bytes) para %s", len(text), self.locality)
        return self._parse_xml(text)

    def _parse_xml(self, text: str) -> dict:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as err:
            raise UpdateFailed(f"Error parseando XML: {err}") from err

        # 1. Mapa código → nombre común + tipo (pollens/spores)
        code_to_info: dict[str, dict] = {}
        for group in root.findall("./taxons/"):  # <pollens> y <spores>
            for elem in group:
                code = elem.tag  # "URTI", "GRAM", etc.
                common_name = elem.get(self.lang) or elem.get("es") or code
                scientific = (elem.text or "").strip()
                code_to_info[code] = {
                    "name": common_name,
                    "scientific": scientific,
                    "type": group.tag,  # "pollens" o "spores"
                }

        _LOGGER.debug("Taxons definidos: %s", list(code_to_info.keys()))

        # 2. Niveles: texto de cada elemento en <report><current><pollens|spores>
        levels: dict[str, int] = {}
        for group in root.findall("./report/current/"):  # <pollens> y <spores>
            for elem in group:
                try:
                    levels[elem.tag] = int((elem.text or "0").strip())
                except ValueError:
                    levels[elem.tag] = 0

        # 3. Tendencias: texto de cada elemento en <report><forecast><pollens|spores>
        trends: dict[str, str] = {}
        for group in root.findall("./report/forecast/"):
            for elem in group:
                trends[elem.tag] = (elem.text or "=").strip()

        # 4. Metadatos de la estación y período
        station_name = root.findtext("./report/station/name", default="")
        date_start = root.findtext("./report/date/start", default="")
        date_end = root.findtext("./report/date/end", default="")

        _LOGGER.debug(
            "Estación: %s | Período: %s → %s | Niveles: %s",
            station_name,
            date_start,
            date_end,
            levels,
        )

        # 5. Combinar todo en el resultado final
        result = {}
        for code, info in code_to_info.items():
            if code not in levels:
                continue  # taxón definido pero sin datos
            level_int = levels[code]
            trend_raw = trends.get(code, "=")
            result[info["name"]] = {
                "level": level_int,
                "level_label": LEVEL_LABELS.get(level_int, str(level_int)),
                "trend": trend_raw,
                "trend_label": TREND_LABELS.get(trend_raw, trend_raw),
                "code": code,
                "scientific": info["scientific"],
                "type": info["type"],
                "station": station_name,
                "period_start": date_start,
                "period_end": date_end,
            }

        if not result:
            _LOGGER.warning("pia_pollen: sin datos de nivel. XML:\n%s", text[:3000])
        else:
            _LOGGER.debug(
                "pia_pollen: %d sensores listos: %s", len(result), list(result.keys())
            )
        _LOGGER.debug("pia_pollen coordinator.data keys: %s", list(result.keys()))
        return result


# ──────────────────────────────────────────────────────────────
#  Sensor entity
# ──────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        " ": "_",
        "(": "",
        ")": ",",
        "/": "_",
    }
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


class PIAPollenSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PIAPollenCoordinator,
        taxon_name: str,
        locality: str,
    ) -> None:
        super().__init__(coordinator)
        self._taxon = taxon_name
        self._locality = locality
        self._attr_unique_id = f"pia_pollen_{locality}_{_slugify(taxon_name)}"
        self._attr_name = taxon_name

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._locality)},
            "name": f"Polen PIA – {self._locality.capitalize()}",
            "manufacturer": "Xarxa Aerobiològica de Catalunya",
            "model": "PIA API v0",
            "configuration_url": "https://aerobiologia.cat/pia/es/api",
        }

    @property
    def icon(self) -> str:
        data = self.coordinator.data.get(self._taxon, {})
        if data.get("type") == "spores":
            return "mdi:flower-pollen-outline"
        return "mdi:flower-pollen"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data.get(self._taxon)
        if not data:
            return None
        level = data["level"]
        prefix = LEVEL_PREFIX.get(self.coordinator.lang, "Nivel")
        return f"{prefix} {level}"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self._taxon, {})
        return {
            "level": data.get("level"),
            "level_label": data.get("level_label", ""),
            "trend": data.get("trend", ""),
            "trend_label": data.get("trend_label", ""),
            "scientific": data.get("scientific", ""),
            "type": data.get("type", ""),
            "code": data.get("code", ""),
            "locality": self._locality,
            "station": data.get("station", ""),
            "period_start": data.get("period_start", ""),
            "period_end": data.get("period_end", ""),
        }
