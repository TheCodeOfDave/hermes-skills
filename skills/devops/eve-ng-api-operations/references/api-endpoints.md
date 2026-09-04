# EVE-NG API Endpoint Catalog

Source: <https://www.eve-ng.net/index.php/how-to-eve-ng-api/>

Use this catalog to select a candidate route. Confirm methods and payload fields against the installed appliance because the official page warns that some request documentation may lag product changes.

`{lab}` means the segment-encoded lab path including `.unl`. `{path}` means an encoded folder or object path. `{id}` and `{username}` must come from live discovery.

## Authentication and status

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | Create an authenticated session. |
| `GET` | `/api/auth` | Read current session identity. |
| `GET` | `/api/auth/logout` | End the session. |
| `GET` | `/api/status` | Read appliance statistics and version data. |

## Discovery

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/list/templates/` | List node templates. |
| `GET` | `/api/list/templates/{template}` | Read template options and available images. |
| `GET` | `/api/list/networks` | List network types. |
| `GET` | `/api/list/roles` | List user roles. |

## Folders

| Method | Route | Purpose | Class |
|---|---|---|---|
| `GET` | `/api/folders/{path}` | List folders and labs under a path. | Read-only |
| `POST` | `/api/folders` | Create a folder. | Side effect |
| `PUT` | `/api/folders/{path}` | Move or rename a folder. | Side effect |
| `DELETE` | `/api/folders/{path}` | Delete a folder. | Destructive |

## Users

| Method | Route | Purpose | Class |
|---|---|---|---|
| `GET` | `/api/users/` | List users. | Security-sensitive read |
| `GET` | `/api/users/{username}` | Read one user. | Security-sensitive read |
| `POST` | `/api/users` | Create a user. | Security-sensitive write |
| `PUT` | `/api/users/{username}` | Edit a user or permissions. | Security-sensitive write |
| `DELETE` | `/api/users/{username}` | Delete a user. | Destructive/security-sensitive |

## Labs

| Method | Route | Purpose | Class |
|---|---|---|---|
| `GET` | `/api/labs/{lab}` | Read lab metadata. | Read-only |
| `POST` | `/api/labs` | Create a lab. | Side effect |
| `PUT` | `/api/labs/{lab}` | Edit lab metadata. | Side effect |
| `PUT` | `/api/labs/{lab}/move` | Move a lab. | Side effect |
| `DELETE` | `/api/labs/{lab}` | Delete a lab. | Destructive |

## Networks and links

| Method | Route | Purpose | Class |
|---|---|---|---|
| `GET` | `/api/labs/{lab}/networks` | List lab networks. | Read-only |
| `GET` | `/api/labs/{lab}/networks/{id}` | Read one network. | Read-only |
| `POST` | `/api/labs/{lab}/networks` | Add a network. | Side effect |
| `GET` | `/api/labs/{lab}/links` | List available Ethernet and serial endpoints. | Read-only |

The installed version may expose additional network edit/delete routes. Discover them from live `GET` responses and authorized Web UI traffic rather than inventing a method.

## Nodes

| Method | Route | Purpose | Class |
|---|---|---|---|
| `GET` | `/api/labs/{lab}/nodes` | List nodes. | Read-only |
| `GET` | `/api/labs/{lab}/nodes/{id}` | Read one node. | Read-only |
| `POST` | `/api/labs/{lab}/nodes` | Add a node. | Side effect |
| `GET` | `/api/labs/{lab}/nodes/start` | Start every node. | Broad side effect |
| `GET` | `/api/labs/{lab}/nodes/{id}/start` | Start one node. | Side effect |
| `GET` | `/api/labs/{lab}/nodes/stop` | Stop every node. | Broad side effect |
| `GET` | `/api/labs/{lab}/nodes/{id}/stop` | Stop one node. | Side effect |
| `GET` | `/api/labs/{lab}/nodes/wipe` | Wipe every node. | Broad destructive |
| `GET` | `/api/labs/{lab}/nodes/{id}/wipe` | Wipe one node. | Destructive |
| `GET` | `/api/labs/{lab}/nodes/export` | Export startup configurations for every node. | Side effect |
| `GET` | `/api/labs/{lab}/nodes/{id}/export` | Export one node startup configuration. | Side effect |
| `GET` | `/api/labs/{lab}/nodes/{id}/interfaces` | Read node interfaces. | Read-only |

EVE-NG uses `GET` for several operational actions. Treat a route by its effect, not by HTTP-method folklore.

Some installed versions can reject this documented route for exact-node stop with a request-shape error even though exact-node start and node readback work. Treat that as installed-version API drift: preserve the sanitized response, confirm current state, inspect authorized Web UI traffic, and never substitute a broad collection stop. If an appliance-local wrapper is the only recovery path, require exact semantic ownership proof and API readback.

## Topology and pictures

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/labs/{lab}/topology` | Read the lab topology. |
| `GET` | `/api/labs/{lab}/pictures` | List pictures. |
| `GET` | `/api/labs/{lab}/pictures/{id}` | Read picture metadata. |
| `GET` | `/api/labs/{lab}/pictures/{id}/data/{width}/{height}` | Read resized picture data. |

## Route-selection checks

Before using any route:

1. Resolve one exact appliance and authenticated identity.
2. Confirm the route exists on the installed version.
3. Resolve every path and ID through read-only discovery.
4. Classify the effect independently of the HTTP method.
5. Use the narrowest route that satisfies the request.
6. Read the exact target back after any action.
