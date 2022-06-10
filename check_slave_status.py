#!/bin/env python3
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile
import pymysql
import os
import re

sockets = os.walk('/var/run/mysqld')
collregistry = CollectorRegistry()
seconds_behind = Gauge("Seconds_Behind_Master", "Seconds Behind Master", ["socket"], registry=collregistry)
slave_io = Gauge("Slave_IO_Running", "Slave IO Running", ["socket"], registry=collregistry)
slave_sql = Gauge("Slave_SQL_Running", "Slave SQL Running", ["socket"], registry=collregistry)
last_errno = Gauge("Last_Errno", "Last Errno", ["socket"], registry=collregistry)

enum = {'Yes': 1, 'No': 0, 'Preparing': 3, 'Connecting': 2}

for item in sockets:
    for s in item[2]:
        if '.sock' in s:
            if '.backup' in s:
                continue
            if not re.match(r"mysqld\d{2,3}.sock", s):
                continue
            try:
                cs = os.path.join('/var/run/mysqld', s)
                seconds_behind.labels(s).set(-1)
                slave_io.labels(s).set(-1)
                slave_sql.labels(s).set(-1)
                last_errno.labels(s).set(-1)
                if os.path.exists('/var/run/mysqld/%s.backup_running' % s):
                    seconds_behind.labels(s).set(-3)
                    slave_io.labels(s).set(-3)
                    slave_sql.labels(s).set(-3)
                    last_errno.labels(s).set(-3)
                    continue
                try:
                    con = pymysql.connect(user=os.getenv('MYSQLUSER'), unix_socket=cs)
                except Exception as e:
                    try:
                        con = pymysql.connect(password=os.getenv('MYSQLPW'), user=os.getenv('MYSQLUSER'), unix_socket=cs)
                    except Exception as e:
                        raise Exception(str(e))
                cur = con.cursor(pymysql.cursors.DictCursor)
                cur.execute("show slave status")
                res = cur.fetchall()
                if len(res) > 0:

                    if res[0]['Seconds_Behind_Master'] is not None:
                        seconds_behind.labels(s).set(int(res[0]['Seconds_Behind_Master']))
                    else:
                        seconds_behind.labels(s).set(-1)

                    slave_io.labels(s).set(enum[res[0]['Slave_IO_Running']])
                    slave_sql.labels(s).set(enum[res[0]['Slave_SQL_Running']])
                    last_errno.labels(s).set(enum[res[0]['Last_Errno']])
            except Exception as e:
                print(str(e))
                seconds_behind.labels(s).set(-2)
                slave_io.labels(s).set(-2)
                slave_sql.labels(s).set(-2)
                last_errno.labels(s).set(-2)

write_to_textfile('/home/prometheus/data/slave.prom', collregistry)
