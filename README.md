# MGRS-Creator

Tool zur Erzeugung eines globalen MGRS-Koordinatengitters in einer PostGIS-Datenbank.

Diese Gitter kann anschliessend beispielsweise für die Erstellung eines WMS oder zur Erzeugung von Vectorkacheln verwendet werden.

## Datenbankmodell

```mermaid
classDiagram
    direction RL
class bands {
   varchar(1) designator
   integer crs
   geometry(polygon,4326) geom
   integer zone_id
   integer id
}
class gridsquares {
   varchar(2) designator
   geometry(polygon,4326) geom
   integer band_id
   integer id
}
class lines {
   integer val
   boolean is_0
   boolean is_10
   geometry(linestring,4326) geom
   integer gridsquare_id
   integer id
}
class zones {
   integer number
   geometry(polygon,4326) geom
   integer id
}

bands "*"  -->  "1" zones : zone_id#58;id
gridsquares "*" -->  "1" bands : band_id#58;id
lines "*"  -->  "1"gridsquares : gridsquare_id#58;id
```

## Datenbankverbindung

Die Datenbankverbindung wird in `database.ini` unter `[database]` als `url`
konfiguriert. Alembic verwendet diese Datei für Online- und Offline-Migrationen.
Die SQLAlchemy-Engine verwendet dieselbe Konfiguration.

Sonderzeichen in Benutzername und Passwort müssen in der URL prozentkodiert sein.

Die Datenbank muss vor der ersten Migration erstellt werden.

Die PostGIS-Extension muss in der Datenbank installiert sein.

```postgresql
create extension postgis;
```
Die Migrationen werden mit `alembic upgrade head` durchgeführt.