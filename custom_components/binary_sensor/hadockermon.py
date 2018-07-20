'''
A custom binary_sensor platform which allows you get sensor data from ha-dockermon.
https://github.com/philhawthorne/ha-dockermon

For more details about this component, please refer to the documentation at
https://github.com/custom-components/binary_sensor.hadockermon
'''
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from time import sleep
from datetime import timedelta
from homeassistant.core import ServiceCall
from homeassistant.util import slugify
from homeassistant.components.binary_sensor import (PLATFORM_SCHEMA,
    BinarySensorDevice, ENTITY_ID_FORMAT)

__version__ = '0.0.3'

REQUIREMENTS = ['pydockermon==0.0.1']

CONF_HOST = 'host'
CONF_PORT = 'port'
CONF_STATS = 'stats'
CONF_PREFIX = 'prefix'
CONF_EXCLUDE = 'exclude'

ATTR_STATUS = 'status'
ATTR_IMAGE = 'image'
ATTR_MEMORY = 'memory'
ATTR_RX_TOTAL = 'network_rx_total'
ATTR_TX_TOTAL = 'network_tx_total'

ATTR_FRIENDLY_NAME = 'friendly_name'

SCAN_INTERVAL = timedelta(seconds=60)

ICON = 'mdi:docker'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default='8126'): cv.string,
    vol.Optional(CONF_STATS, default='False'): cv.string,
    vol.Optional(CONF_PREFIX, default='None'): cv.string,
    vol.Optional(CONF_EXCLUDE, default=None): 
        vol.All(cv.ensure_list, [cv.string]),
})

def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    from pydockermon import Dockermon
    dm = Dockermon()
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    exclude = config.get(CONF_EXCLUDE)
    stats = config.get(CONF_STATS)
    prefix = config.get(CONF_PREFIX)
    dev = []
    containers = dm.listContainers(host)
    if containers:
        for container in containers:
            containername = container['Names'][0][1:]
            if containername not in exclude:
                dev.append(ContainerBinarySensor(containername,
                    False, stats, host, port , dm, prefix))
        add_devices_callback(dev, True)
    else:
        return False

class ContainerBinarySensor(BinarySensorDevice):
    def __init__(self, name, state, stats, host, port, dm, prefix):
        _slow_reported = True
        if prefix == 'None':
            self.entity_id = ENTITY_ID_FORMAT.format(slugify(name))
        else:
            self.entity_id = ENTITY_ID_FORMAT.format(slugify(prefix + '_' + name))
        self._dm = dm
        self._state = False
        self._name = name
        self._stats = stats
        self._network_stats = None
        self._status = None
        self._image = None
        self._memory_usage = None
        self._network_rx_total = None
        self._network_tx_total = None
        self._host = host
        self._port = port

    def update(self):
        containerstate = self._dm.getContainerState(self._name,
            self._host, self._port)
        if containerstate == False:
            self._state = False
        else:
            state = containerstate['state']
            self._status = containerstate['status']
            self._image = containerstate['image']
            if state == 'running':
                if self._stats == 'True':
                    containerstats = self._dm.getContainerStats(self._name,
                        self._host, self._port)
                    if containerstats == False:
                        return False
                    else:
                        get_memory = containerstats['memory_stats']
                        memory_usage = get_memory['usage']/1024/1024
                        try:
                            containerstats['networks']
                        except Exception:
                            self._network_rx_total = None
                            self._network_tx_total = None
                        else:
                            self._network_stats = 'aviable'
                            netstats = containerstats['networks']['eth0']
                            network_rx_total = netstats['rx_bytes']/1024/1024
                            network_tx_total = netstats['tx_bytes']/1024/1024
                            self._network_rx_total = str(round(
                                network_rx_total, 2)) + ' MB'
                            self._network_tx_total = str(round(
                                network_tx_total, 2)) + ' MB'
                        self._memory_usage = str(round(
                            memory_usage, 2)) + ' MB'
                self._state = True
            else:
                self._state = False

    @property
    def name(self):
        """Return the name of the binary_sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'connectivity'


    @property
    def icon(self):
        """Return a icon for the binary sensor."""
        return ICON

    @property
    def device_state_attributes(self):
        if self._network_stats == 'aviable':
            return {
                ATTR_STATUS: self._status,
                ATTR_IMAGE: self._image,
                ATTR_MEMORY: self._memory_usage,
                ATTR_RX_TOTAL: self._network_rx_total,
                ATTR_TX_TOTAL: self._network_tx_total,
            }
        elif self._stats == 'True':
            return {
                ATTR_STATUS: self._status,
                ATTR_IMAGE: self._image,
                ATTR_MEMORY: self._memory_usage,
            }
        else: 
            return {
                ATTR_STATUS: self._status,
                ATTR_IMAGE: self._image,
            }
