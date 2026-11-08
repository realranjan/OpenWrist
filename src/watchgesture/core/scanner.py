"""
BLE Device Scanner and Smartwatch Discovery for WatchGesture.

Automatically discovers nearby Fire-Boltt, DaFit, and compatible smartwatches
advertising the vendor-specific 0xFEEA service or recognized manufacturer names.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from watchgesture.core.protocol import SERVICE_FEEA

logger = logging.getLogger(__name__)

KNOWN_WATCH_KEYWORDS = [
    "fire-boltt",
    "fireboltt",
    "boltt",
    "dafit",
    "realtek",
    "184",
    "watch",
    "smart",
    "band",
]


@dataclass
class DiscoveredDevice:
    """Detailed summary of a discovered Bluetooth Low Energy peripheral."""
    address: str
    name: str
    rssi: int
    is_supported_watch: bool
    service_uuids: List[str] = field(default_factory=list)
    ble_device: Optional[BLEDevice] = None

    def __str__(self) -> str:
        badge = " [MATCH ⌚]" if self.is_supported_watch else ""
        return f"{self.name or 'Unknown'} ({self.address}) RSSI: {self.rssi}dBm{badge}"


def is_candidate_watch(device: BLEDevice, adv: AdvertisementData) -> bool:
    """Checks whether device advertisements match known Fire-Boltt/DaFit profiles."""
    # Check 1: Advertised service UUIDs
    adv_services = [str(uuid).lower() for uuid in (adv.service_uuids or [])]
    if any("feea" in s for s in adv_services):
        return True

    # Check 2: Device name matching
    name = (device.name or adv.local_name or "").lower()
    return any(keyword in name for keyword in KNOWN_WATCH_KEYWORDS)


async def scan_for_devices(timeout_sec: float = 6.0) -> List[DiscoveredDevice]:
    """
    Performs an active BLE scan and returns all discovered peripherals,
    flagging detected smartwatches.
    """
    logger.info("Scanning for Bluetooth devices for %.1f seconds...", timeout_sec)
    results: List[DiscoveredDevice] = []

    discovered = await BleakScanner.discover(timeout=timeout_sec, return_adv=True)

    for address, (dev, adv) in discovered.items():
        is_watch = is_candidate_watch(dev, adv)
        results.append(
            DiscoveredDevice(
                address=address,
                name=dev.name or adv.local_name or "Unknown Device",
                rssi=adv.rssi,
                is_supported_watch=is_watch,
                service_uuids=[str(u) for u in (adv.service_uuids or [])],
                ble_device=dev,
            )
        )

    # Sort matching watches first, then by RSSI signal strength
    results.sort(key=lambda d: (d.is_supported_watch, d.rssi), reverse=True)
    return results


async def find_target_watch(
    target_address: Optional[str] = None,
    timeout_sec: float = 8.0,
) -> Optional[BLEDevice]:
    """
    Locates the target smartwatch by MAC address or automatically discovers
    the closest matching watch peripheral in a single active scan pass.
    """
    clean_addr = target_address.strip().upper() if target_address else None
    if clean_addr:
        logger.info("Scanning for target watch MAC: %s...", clean_addr)
    else:
        logger.info("Scanning for any nearby smartwatch candidate...")

    discovered = await BleakScanner.discover(timeout=timeout_sec, return_adv=True)

    # 1. Exact MAC match if specified
    if clean_addr:
        for address, (dev, adv) in discovered.items():
            if address.upper() == clean_addr:
                logger.info("Found target watch by address: %s (%s)", dev.name, address)
                return dev

    # 2. Match by watch heuristics
    candidate_watches: List[Tuple[BLEDevice, int]] = []
    for address, (dev, adv) in discovered.items():
        if is_candidate_watch(dev, adv):
            candidate_watches.append((dev, adv.rssi))

    if candidate_watches:
        candidate_watches.sort(key=lambda item: item[1], reverse=True)
        best_dev = candidate_watches[0][0]
        logger.info("Auto-selected best smartwatch candidate: %s (%s)", best_dev.name, best_dev.address)
        return best_dev

    return None

