#!/bin/env python3
from ttp import ttp
from icecream import ic
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile
import subprocess
from os import chown
import pwd
import grp

p = subprocess.Popen("/usr/local/bin/arcconf GETCONFIG 1".split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
data = p.stdout.read().decode('utf-8')

collregistry = CollectorRegistry()
controller_status = Gauge("ARCCONF_Controller_Status", "Status of Controller", ["Controller"], registry=collregistry)
diskstate = Gauge("ARCCONF_Disk_State", "Status of disk in array", ["logicalarray", "devserial"], registry=collregistry)
controller_temp = Gauge("ARCCONF_Controller_Temperature", "Temperature of Controller", ["Controller", "Sensor"], registry=collregistry)
controller_arrays = Gauge("ARCCONF_Controller_Arrays", "Arrays on Controller", ["Controller", "State"], registry=collregistry)
controllerID = 1
enum = {'Present': 1, 'Missing': 0, "Optimal": 1}

init_template = """
Controllers found: 1{{ ignore(".*") }}
----------------------------------------------------------------------{{ ignore(".*") }}
Controller information{{ ignore(".*") }}
----------------------------------------------------------------------{{ ignore(".*") }}
   Controller Status                        : {{ controllerstatus }}
   Controller Mode                          : RAID (Expose RAW){{ ignore(".*") }}
   Channel description                      : SAS/SATA{{ ignore(".*") }}
   Controller Model                         : {{ controllermodel | re(".*") }}
"""
parser = ttp(data=data, template=init_template)
parser.parse()
m = parser.result()
controller_status.labels(controllerID).set(enum[m[0][0]['controllerstatus']])

templates = {
    'MSCC Adaptec SmartRAID 3101-4i': """
<group name="Controller">
----------------------------------------------------------------------{{ ignore(".*") }}
Controller information{{ ignore(".*") }}
----------------------------------------------------------------------{{ ignore(".*") }}
   Temperature                              : {{ ctempc }} C/ {{ ctempf }} F (Normal)
   --------------------------------------------------------{{ ignore(".*") }}
   RAID Properties{{ ignore(".*") }}
   --------------------------------------------------------{{ ignore(".*") }}
   Logical devices/Failed/Degraded          : {{ ldevices }}/{{ ldfailed }}/{{ lddegr }}
   --------------------------------------------------------{{ ignore(".*") }}
   Temperature Sensors Information{{ ignore(".*") }}
   --------------------------------------------------------{{ ignore(".*") }}
</group>
<group name="Controller_temp">
   Sensor ID                                : {{ tsensor_id }}
   Current Value                            : {{ currtempc }} deg C
   Max Value Since Powered On               : {{ maxtempc }} deg C
   Location                                 : {{ tsensor_loc | re(".*") }}
</group>

   --------------------------------------------------------{{ ignore(".*") }}


<group name="LD">
Logical Device number {{ ldnr }}
   Device Type{{ ignore(".*") }}
   Array Physical Device Information{{ ignore(".*") }}
<group name="logicaldevice">
   Device {{ segnr }}{{ ignore("\\s*") }}: {{ segstate }} ({{ sizemb }}MB,{{ ignore(".*") }} Enclosure:{{ encnr }}, Slot:{{ slotnr }}){{ ignore("\\s*") }}{{ serial }}
</group>
Physical Device information{{ ignore(".*") }}
</group>
""",
    'Adaptec ASR8405': """
<group name="Controller">
----------------------------------------------------------------------{{ ignore(".*") }}
Controller information{{ ignore(".*") }}
----------------------------------------------------------------------{{ ignore(".*") }}
   Temperature                              : {{ ctempc }} C/ {{ ctempf }} F (Normal)
</group>
<group name="LD">
Logical Device number {{ ldnr }}
<group name="logicaldevice">
   Segment {{ segnr }}{{ ignore("\\s*") }}: {{ segstate }} ({{ sizemb }}MB, {{ ignore(".*") }} Enclosure:{{ encnr }}, Slot:{{ slotnr }}){{ ignore("\\s*") }}{{ serial }}
</group>
Physical Device information{{ ignore(".*") }}
</group>
"""
}
parser = ttp(data=data, template=templates[m[0][0]['controllermodel']])
parser.parse()
o = parser.result()
promfile = '/tmp/arcconf.prom'


for x in o[0]:
    if 'Controller_temp' in x.keys():
        for c in x['Controller_temp']:
            if 'currtempc' in c.keys():
                controller_temp.labels(controllerID, c['tsensor_loc'] + '_current').set(c['currtempc'])
            if 'maxtempc' in c.keys():
                controller_temp.labels(controllerID, c['tsensor_loc'] + '_max').set(c['maxtempc'])
    if 'Controller' in x.keys():
        for c in x['Controller']:
            if 'ldevices' in c.keys():
                controller_arrays.labels(controllerID, 'Total').set(c['ldevices'])
            if 'lddegr' in c.keys():
                controller_arrays.labels(controllerID, 'Degraded').set(c['lddegr'])
            if 'ldfailed' in c.keys():
                controller_arrays.labels(controllerID, 'Failed').set(c['ldfailed'])
            if 'ctempc' in c.keys():
                controller_temp.labels(controllerID, "Core").set(c['ctempc'])
    if 'LD' in x.keys():
        if 'logicaldevice' in x['LD'].keys():
            for ld in x['LD']['logicaldevice']:
                diskstate.labels(x['LD']['ldnr'], ld['serial']).set(enum[ld['segstate']])
write_to_textfile(promfile, collregistry)
chown(promfile, pwd.getpwnam('prometheus').pw_uid, grp.getgrnam('prometheus').gr_gid)
