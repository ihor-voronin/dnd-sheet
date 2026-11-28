-- Початкова схема: ті самі таблиці, що й у SQLite (characters/infrastructure/sqlite_store.py,
-- identity/infrastructure/sqlite_identity.py, identity/infrastructure/sqlite_oauth.py).
--
-- Персонаж і чернетка — один документ `jsonb`: схема не дублює модель агрегата, тож нове поле
-- в JSON (аватар, власні риси) не потребує міграції. Строки дії й моменти, які порти передають
-- числом секунд (`expires_at`, `saved_at`, ...), лишаються `double precision`; позначки часу,
-- які ставить сама база, — `timestamptz`.
--
-- Таблиці створюються в першій схемі `search_path` (на сервері — `public` бази проєкту, у тестах —
-- тимчасова схема): міграції не знають, у якій базі й під якою роллю їх запускають.

CREATE TABLE users (
    id text PRIMARY KEY,
    telegram_id bigint NOT NULL UNIQUE,
    first_name text NOT NULL DEFAULT '',
    last_name text NOT NULL DEFAULT '',
    username text NOT NULL DEFAULT '',
    photo_url text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE TABLE sessions (
    token_hash text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    expires_at double precision NOT NULL
);
CREATE INDEX sessions_user ON sessions (user_id);

-- Власник — стовпець поруч із документом, а не поле агрегата; зовнішнього ключа на users немає,
-- як і в SQLite: без входу (DNDSHEET_AUTH=off) власник — локальний гравець, якого немає в users.
CREATE TABLE characters (
    id text PRIMARY KEY,
    owner_id text,
    version integer NOT NULL,
    record jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX characters_owner ON characters (owner_id, updated_at DESC);

CREATE TABLE drafts (
    id text PRIMARY KEY,
    owner_id text,
    record jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX drafts_owner ON drafts (owner_id, updated_at DESC);

CREATE TABLE shares (
    token text PRIMARY KEY,
    character_id text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- `info` — JSON застосунку рівно в тому вигляді, в якому його записав і читає SDK MCP: `text`,
-- а не `jsonb`, щоб рядок повертався байт у байт.
CREATE TABLE oauth_clients (
    client_id text PRIMARY KEY,
    info text NOT NULL,
    kind text NOT NULL,
    saved_at double precision NOT NULL
);

CREATE TABLE oauth_requests (
    id text PRIMARY KEY,
    client_id text NOT NULL,
    redirect_uri text NOT NULL,
    redirect_uri_explicit boolean NOT NULL,
    scopes text NOT NULL,
    code_challenge text NOT NULL,
    state text,
    resource text NOT NULL,
    expires_at double precision NOT NULL
);

CREATE TABLE oauth_codes (
    code_hash text PRIMARY KEY,
    client_id text NOT NULL,
    user_id text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    redirect_uri text NOT NULL,
    redirect_uri_explicit boolean NOT NULL,
    scopes text NOT NULL,
    code_challenge text NOT NULL,
    resource text NOT NULL,
    expires_at double precision NOT NULL
);

CREATE TABLE oauth_tokens (
    token_hash text PRIMARY KEY,
    kind text NOT NULL,
    family text NOT NULL,
    user_id text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    client_id text NOT NULL,
    scopes text NOT NULL,
    resource text NOT NULL,
    expires_at double precision NOT NULL,
    created_at double precision NOT NULL,
    used boolean NOT NULL DEFAULT false,
    last_used_at double precision
);
CREATE INDEX oauth_tokens_family ON oauth_tokens (family);
CREATE INDEX oauth_tokens_owner ON oauth_tokens (user_id, client_id);
