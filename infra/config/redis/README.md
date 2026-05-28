# Redis TLS Material

Compose-prod expects the following files here, provisioned by your secret
manager and never committed:

- `ca.crt`
- `server.crt`
- `server.key`
- `client.crt`
- `client.key`

The backend mounts this directory read-only and authenticates to Redis with the
client certificate. The Redis container uses the server certificate and requires
client certificates.
