# arcconf exporter

Currently tested and working for the following models
* MSCC Adaptec SmartRAID 3101-4i
* Adaptec ASR8405


# slave status exporter

* requires a user that can read slave status
* fetches socket files from /var/run/mysqld
* in case of backups from slave, backup script should create and remove a <socket>.backup file in /var/run/mysqld to show that backup is running on instance
