# CineRadarBot

CineRadarBot es un bot de Telegram en Python que avisa de estrenos de cine en España y novedades de películas en plataformas de streaming. Está pensado para ejecutarse sin servidor propio mediante GitHub Actions, con una tarea programada diaria o manual.

## Qué envía

Cada aviso incluye:

- título;
- origen del estreno: Cine, Netflix, Prime Video, Disney+, Max, Movistar Plus+, Filmin, Apple TV+, SkyShowtime u otra plataforma devuelta por la API;
- fecha;
- nota si existe;
- sinopsis breve;
- enlace a TMDb cuando hay ID de TMDb;
- póster cuando la API lo devuelve.

Por defecto está activado `ONLY_MAJOR_RELEASES=true`, para evitar avisos de títulos muy pequeños. En cine se usa `MIN_TMDB_POPULARITY=8.0`; si quieres ser más exigente, sube a `15` o `20`. Si quieres ver todo, pon `ONLY_MAJOR_RELEASES=false`.

## APIs necesarias

### Telegram

1. Abre Telegram y habla con `@BotFather`.
2. Ejecuta `/newbot`, elige nombre y usuario.
3. Copia el token en `TELEGRAM_BOT_TOKEN`.

Para obtener `TELEGRAM_CHAT_ID`:

1. Escribe cualquier mensaje a tu bot.
2. Abre en el navegador:

```text
https://api.telegram.org/bot<TU_TOKEN>/getUpdates
```

3. Busca `chat.id` y copia ese número. Si es un canal o grupo, añade el bot y dale permisos para publicar.

### TMDb

1. Crea una cuenta en [TMDb](https://www.themoviedb.org/).
2. En ajustes de cuenta, solicita acceso a la API.
3. Usa preferiblemente el token Bearer v4 en `TMDB_API_TOKEN`.
4. También puedes usar la API key v3 en `TMDB_API_KEY`.

El bot consulta `movie/now_playing` y `movie/upcoming` con `region=ES` y `language=es-ES`. Para cine, por defecto avisa de películas estrenadas ayer, es decir, cuando ya llevan un día en cartelera. Puedes cambiarlo con `CINEMA_RELEASE_OFFSET_DAYS`.

### Streaming

Proveedor recomendado para novedades: `streamingavailability`.

1. Crea una cuenta en [Streaming Availability API](https://docs.movieofthenight.com/).
2. Copia la clave en `STREAMING_API_KEY`.
3. Configura:

```env
STREAMING_API_PROVIDER=streamingavailability
STREAMING_CATALOGS=netflix,prime,disney,hbo,movistar,filmin,apple,skyshowtime
```

Si usas la clave de RapidAPI, pon el prefijo `rapidapi:`:

```env
STREAMING_API_KEY=rapidapi:TU_CLAVE
```

También existe soporte para `watchmode`. Si usas Watchmode, configura:

```env
STREAMING_API_PROVIDER=watchmode
STREAMING_API_KEY=TU_CLAVE_WATCHMODE
WATCHMODE_SOURCE_IDS=
```

Watchmode funciona con `/v1/list-titles/` y `/v1/title/{id}/sources/`. El bot lo usa como fallback buscando títulos estrenados recientemente y disponibles en plataformas de suscripción en España. Es útil para disponibilidad, pero el listado gratuito filtra por fecha de estreno original de la película o serie, no necesariamente por fecha exacta de alta en catálogo. Por eso, para “novedades añadidas a plataformas”, `streamingavailability` es más honesto y directo.

## Cargar secrets en GitHub de forma segura

No escribas tokens en el repositorio. Si tienes GitHub CLI instalado y autenticado, puedes ejecutar:

```powershell
.\scripts\setup_github_actions.ps1 -Repo TU_USUARIO/CineRadarBot
```

El script te pedirá los valores en modo oculto y los subirá con `gh secret set`. También configurará variables no sensibles para España y Watchmode.

## Configuración local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Rellena `.env` con tus claves:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TMDB_API_TOKEN=...
STREAMING_API_PROVIDER=streamingavailability
STREAMING_API_KEY=...
COUNTRY=ES
LANGUAGE=es-ES
DAYS_AHEAD=7
```

Ejecuta:

```bash
python -m src.main
```

## GitHub Actions

El workflow está en `.github/workflows/notify.yml` y se ejecuta cada día a las 09:00 UTC. También se puede lanzar manualmente desde la pestaña **Actions** con `workflow_dispatch`.

Configura estos **Repository Secrets**:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TMDB_API_TOKEN` o `TMDB_API_KEY`
- `STREAMING_API_KEY`

Opcionalmente, configura **Repository Variables**:

- `STREAMING_API_PROVIDER`
- `COUNTRY`
- `LANGUAGE`
- `DAYS_AHEAD`
- `CINEMA_RELEASE_OFFSET_DAYS`
- `MIN_TMDB_VOTE_COUNT`
- `MAX_ITEMS_PER_MESSAGE`
- `MAX_STREAMING_PAGES`
- `STREAMING_CATALOGS`
- `WATCHMODE_SOURCE_IDS`
- `INCLUDE_SERIES`
- `SEND_STREAMING_STATUS`
- `ONLY_MAJOR_RELEASES`
- `MIN_TMDB_POPULARITY`
- `MIN_STREAMING_VOTE_AVERAGE`

## Persistencia de duplicados

Los avisos enviados se guardan en `data/sent_items.json`.

En GitHub Actions se usa `actions/cache` con una clave nueva por ejecución y `restore-keys`, de modo que el bot restaura el último histórico disponible y guarda uno nuevo al terminar. No es una base de datos perfecta, pero evita la mayoría de duplicados sin mantener un servidor encendido.

El diseño está aislado en `src/storage.py`, así que cambiar a Gist, commit automático, SQLite remota o una base de datos será sencillo.

## Limitaciones reales

- TMDb ofrece estrenos de cine por región, pero las fechas pueden depender de la información disponible en TMDb.
- Las plataformas de streaming no siempre publican “alta exacta en catálogo” con la misma calidad.
- `streamingavailability` tiene endpoint de cambios (`/changes`) y es la opción preferida para novedades.
- `watchmode` ofrece disponibilidad y fuentes, pero su búsqueda de listado público se basa en fecha de estreno original; no conviene venderlo como “añadido hoy” si la API contratada no lo garantiza.
- El bot no hace scraping ni lee HTML de plataformas.

## Añadir plataformas o cambiar proveedor

Para añadir plataformas con Streaming Availability:

1. Consulta el endpoint `/countries` de la API para ver IDs soportados en España.
2. Añade los IDs a `STREAMING_CATALOGS`, separados por coma.

Para añadir otro proveedor:

1. Crea una clase o rama nueva en `src/streaming_client.py`.
2. Devuelve siempre una lista de `MovieItem`.
3. Rellena `platform_names`, `origin`, `tmdb_id`, `poster_url` y `unique_key`.
4. Usa claves de duplicado estables, por ejemplo:

```text
streaming:provider:tmdb_id:date
```

## Estructura

```text
src/
  main.py
  config.py
  telegram_client.py
  tmdb_client.py
  streaming_client.py
  formatter.py
  storage.py
  models.py
data/
  sent_items.json
.github/workflows/notify.yml
requirements.txt
.env.example
README.md
.gitignore
```
