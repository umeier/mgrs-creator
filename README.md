Die Datenbankverbindung wird in `database.ini` unter `[database]` als `url`
konfiguriert. Alembic verwendet diese Datei für Online- und Offline-Migrationen.
Für eine spätere SQLAlchemy-Engine kann dieselbe Konfiguration genutzt werden:

```python
from sqlalchemy import create_engine
from database import get_database_url

engine = create_engine(get_database_url())
```

Sonderzeichen in Benutzername und Passwort müssen in der URL prozentkodiert sein.