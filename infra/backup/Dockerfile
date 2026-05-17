# SwarmOS backup image (Phase 6.E).
#
# Minimal alpine carrying pg_dump + gnupg + tini. Built once and pushed
# to GHCR so the CronJob (and compose-prod backup sidecar) doesn't have
# to `apk add` at every boot — clusters that block egress from CronJobs
# would otherwise fail.
#
# Runtime: runs the script mounted from a ConfigMap (k8s) or the host
# (compose-prod) so updating the script is a config-only change.

# alpine:3.20
FROM alpine@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc

RUN apk add --no-cache \
        postgresql16-client \
        gnupg \
        tini \
        coreutils \
 && addgroup -S -g 10001 swarm \
 && adduser -S -u 10001 -G swarm -s /sbin/nologin -h /home/swarm swarm \
 && install -d -o swarm -g swarm /backups /home/swarm/.gnupg \
 && chmod 700 /home/swarm/.gnupg

# pg_dump uses the standard pg locale; pin LC_ALL for reproducible output.
ENV LC_ALL=C \
    PGSSLMODE=require \
    GNUPGHOME=/home/swarm/.gnupg

USER swarm
WORKDIR /home/swarm

# `tini` reaps zombies if pg_dump|gpg pipes need it; the script is the
# real entrypoint, mounted at /usr/local/bin/backup_postgres.sh.
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/usr/local/bin/backup_postgres.sh"]
