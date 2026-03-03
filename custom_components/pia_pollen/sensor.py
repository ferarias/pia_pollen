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

from .const import DOMAIN, BASE_URL, SCAN_INTERVAL_HOURS, LEVEL_LABELS, TREND_LABELS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    locality = entry.data["locality"]
    lang = entry.data["lang"]
    url = BASE_URL.format(locality=locality, lang=lang)

    coordinator = PIAPollenCoordinator(hass, url, locality)
    await coordinator.async_config_entry_first_refresh()

    entities = [
        PIAPollenSensor(coordinator, taxon_name, locality)
        for taxon_name in coordinator.data
    ]
    async_add_entities(entities, update_before_add=True)


class PIAPollenCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, url: str, locality: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"PIA Polen {locality}",
            update_interval=timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self.url = url
        self.locality = locality

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

        result = {}

        # root.iter("taxon") busca <taxon> en cualquier nivel del árbol,
        # sin importar cómo estén anidados (robusto ante estructura desconocida).
        for taxon in root.iter("taxon"):
            # Intenta estructura por sub-elementos primero; si no, por atributos
            name = (taxon.findtext("name") or taxon.get("name", "")).strip()
            level_raw = (taxon.findtext("level") or taxon.get("level", "0")).strip()
            trend_raw = (taxon.findtext("trend") or taxon.get("trend", "0")).strip()

            if not name:
                continue

            try:
                level_int = int(level_raw)
            except ValueError:
                level_int = 0

            result[name] = {
                "level": level_int,
                "level_label": LEVEL_LABELS.get(level_int, level_raw),
                "trend": trend_raw,
                "trend_label": TREND_LABELS.get(trend_raw, trend_raw),
            }

        if not result:
            # Si esto aparece en los logs, pega el fragmento XML aquí
            # para ajustar los XPath en _parse_xml
            _LOGGER.warning(
                "pia_pollen: no se encontraron <taxon> en el XML. "
                "Fragmento recibido:\n%s", text[:600]
            )

        return result


def _slugify(text: str) -> str:
    """Convierte nombre de taxón a slug válido para unique_id."""
    replacements = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"," ":"_"}
    result = text.lower()
    for src, dst in replacements.items():
        result = result.replace(src, dst)
    return result


class PIAPollenSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:flower-pollen"
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
    def native_value(self) -> int | None:
        data = self.coordinator.data.get(self._taxon)
        return data["level"] if data else None

    @property
    def native_unit_of_measurement(self) -> str:
        return "nivel"

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data.get(self._taxon, {})
        return {
            "level_label": data.get("level_label", ""),
            "trend": data.get("trend", ""),
            "trend_label": data.get("trend_label", ""),
            "locality": self._locality,
            "taxon": self._taxon,
        }
