# reqresin_clone

## what it is

a local, offline copy of the public REST practice API https://reqres.in/ (classic `/api/users`, `/api/login`, ... contract). one python file, standard library only, no install, no database, no internet. it listens on **port 40000**.

it mimics the live service closely, including its quirks:

- the data is frozen (12 users, 6 colors, 3 products) and nothing is stored: `POST /api/users` always answers id `4`, `DELETE` does not delete, `PUT/PATCH` only echo your body plus `updatedAt`.
- login and register accept any non-empty email and password and answer the same fixed token.
- CORS is wide open (`Access-Control-Allow-Origin: *`).
- the avatar images are served from this repo (`/img/faces/<id>-image.jpg`), so the avatar URLs in the responses work offline.

because it is stateless, tests against it are repeatable: every run starts from the same state and there is nothing to clean up.

## when to use it

- as the target for API tests and API practice: you get a fast, always-up, rate-limit-free API on your own machine.
- in CI or on a plane, where https://reqres.in/ is slow, blocked or requires an API key.

when not to use it:

- you need to test a real service with real persistence: this clone forgets everything by design.
- you need the exact current behavior of the live site: the data was captured once and the clone does not track later changes.
- you want to practice web UI automation: use the sibling clone https://github.com/ClasherGeek77/saucedemo_clone instead.

repos that use it as their target:

| repo | how it uses the clone |
| --- | --- |
| https://github.com/ClasherGeek77/pytest_api_boilerplate | `BASE_URL=http://localhost:40000` in `test.env`; can start the clone itself via `REQRESIN_CLONE_DIR` |
| https://github.com/ClasherGeek77/katalon_api_boilerplate | `Profiles/default.glbl` points at `http://localhost:40000/` |
| https://github.com/ClasherGeek77/locust_boilerplate | load target, default `HOST_URL=http://localhost:40000` |
| https://github.com/ClasherGeek77/bruno_collection | `base_url` in the `local` environment |
| https://github.com/ClasherGeek77/postman_collection | `base_url` collection variable |

## what you need

- python 3.8 or newer (stated in `server.py`; checked here on 3.8.2). nothing else, no pip install.
- git.

## quick start

```bash
git clone https://github.com/ClasherGeek77/reqresin_clone.git
cd reqresin_clone
python3 server.py
```

you should see:

```
reqres clone on http://localhost:40000/api  (Ctrl-C to stop)
```

in a second terminal:

```bash
curl http://localhost:40000/api/users/2
```

you should see a JSON object with `"data"` holding Janet Weaver (`"id": 2`) and a `"support"` block.

or open http://localhost:40000/ in a browser: a small API explorer page where you click an endpoint and see the request and response.

### start on another port

```bash
python3 server.py --port 8000
```

`--host` is also available (default `localhost`). if you change the port, the clients above must be told: set `BASE_URL` (pytest), the `base_url` variable (bruno, postman), `HOST_URL` (locust) or the Katalon profile value. note the avatar URLs inside the data stay on `localhost:40000`.

### run it in the background and stop it

```bash
python3 server.py > /tmp/reqres.log 2>&1 &
echo $! > /tmp/reqres.pid
# later
kill "$(cat /tmp/reqres.pid)"
```

in the foreground, stop with Ctrl-C.

### reset state

there is no state to reset: the server keeps nothing between requests, and restarting it changes nothing. if a test passes on the first run and fails on the second, the cause is not this server.

## endpoints

all under `http://localhost:40000`.

| method and path | answer |
| --- | --- |
| `GET /` | the explorer page |
| `GET /api` | small JSON index of the endpoints |
| `GET /api/users?page=1` | users 1-6; `page=2` users 7-12; `total` 12, `total_pages` 2; page 3 or higher: empty `data`; a non-numeric page counts as 1 |
| `GET /api/users?delay=2` | same list after a 2 second sleep (capped at 30) |
| `GET /api/users?<anything else>` | empty `data` list |
| `GET /api/users/1` .. `/12` | `{"data": {...}, "support": {...}}` |
| `GET /api/users/23` (any other id) | 404 with `{}` |
| `POST /api/users` | 201, echoes your JSON plus `"id": "4"` and `createdAt` |
| `PUT` or `PATCH /api/users/{id}` | 200, echoes your JSON plus `updatedAt` (any id) |
| `DELETE /api/users/{id}` | 204, empty body (any id) |
| `GET /api/user-list?delay=2` | users 1-10 (`per_page` 10, `total_pages` 2) after the delay |
| `GET /api/unknown` | 6 colors |
| `GET /api/unknown/1` .. `/6` | one color; other ids 404 with `{}` |
| `GET /api/products` | 3 products (cap, hammer, lead) |
| `GET /api/support` | the support text and url |
| `POST /api/register` | `{"email", "password"}` -> 200 `{"id": 4, "token": "QpwL5tke4Pnpja7X4"}`; missing email: 400 `{"error": "Missing email"}`; missing password: 400 `{"error": "Missing password"}` |
| `POST /api/login` | same rules, answers `{"token": "QpwL5tke4Pnpja7X4"}` |
| `GET /img/faces/1-image.jpg` .. `12-image.jpg` | avatar JPEG |
| anything else under the API | 404 with `{}` |

accounts: there are no real accounts. the live docs use `eve.holt@reqres.in` with `cityslicka`; any non-empty pair works here too, the clone does not compare passwords.

## how to read the code

- `server.py`: the whole HTTP server (`ReqResHandler`), routing in `do_GET`, `do_POST`, `do_PUT`, `do_DELETE`. the docstring at the top lists the endpoints.
- `data.py`: the frozen users, colors, products, the support text and the fixed token.
- `ui.html`: the explorer page served at `/`.
- `img/faces/`: the 12 avatars. `static/`: fonts used by the explorer page.

## if it breaks

| symptom | cause | fix |
| --- | --- | --- |
| `OSError: [Errno 48] Address already in use` (Linux: `Errno 98`) | something already listens on 40000, often a previous copy of this server | find it with `lsof -iTCP:40000 -sTCP:LISTEN`, stop it, or start with `--port` |
| `curl: (7) Failed to connect` | the server is not running | start it with `python3 server.py` |
| a client says `ECONNREFUSED` | the client uses another port or host than the server | make `BASE_URL` / `base_url` match the port you started |
| the first request after `?delay=2` seems slow | that is the delay feature | drop the parameter |
| `ImportError` or `SyntaxError` on start | python older than 3.8 | use a newer python3 |

## next

- API tests in python: https://github.com/ClasherGeek77/pytest_api_boilerplate
- API tests in Katalon: https://github.com/ClasherGeek77/katalon_api_boilerplate
- load test: https://github.com/ClasherGeek77/locust_boilerplate
- request collections: https://github.com/ClasherGeek77/bruno_collection and https://github.com/ClasherGeek77/postman_collection
- the web UI twin of this clone: https://github.com/ClasherGeek77/saucedemo_clone
