# gh-runner-wwf — the ONE self-hosted GitHub Actions runner (kvm4-wwf).
#
# Base: the filesystem of the pre-migration runner container, recovered from
# the VM backup (`docker export` → /opt/restore/gh-runner-wwf.tar) and imported
# as wwf-gh-runner:2.335.1-restored. That is deliberate: it carries the Ubuntu
# 24.04 userland, sudo, the docker CLI and the hosted toolcache that CI already
# depends on, none of which was ever written down anywhere. Only the runner
# package itself is replaced, because 2.335.1 is two releases behind and a
# runner registered with --disableupdate must be upgraded by hand (this file).
ARG BASE=wwf-gh-runner:2.335.1-restored
FROM ${BASE}

ARG RUNNER_VERSION=2.337.0
ARG RUNNER_SHA256=70920811a4f8ad4328818682bca5c6469c1c942fab52448868071d0063816613

USER root
# Drop the old registration (.runner, .runner_migrated, .credentials*) and the
# old package, including the bin.<ver>/externals.<ver> copies an earlier
# self-update left behind, then install the pinned release, verified against
# the SHA-256 GitHub publishes in the release notes.
RUN set -eux; \
    cd /home/runner/actions-runner; \
    rm -rf bin bin.* externals externals.* .runner .runner_migrated \
           .credentials .credentials_rsaparams .credentials_migrated .env .path _diag; \
    curl -fsSL -o /tmp/runner.tgz \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"; \
    echo "${RUNNER_SHA256}  /tmp/runner.tgz" | sha256sum -c -; \
    tar xzf /tmp/runner.tgz; \
    rm -f /tmp/runner.tgz; \
    chown -R runner:runner /home/runner/actions-runner

COPY entrypoint.sh /home/runner/entrypoint.sh
RUN chmod 755 /home/runner/entrypoint.sh

USER runner
WORKDIR /home/runner/actions-runner
ENTRYPOINT ["/home/runner/entrypoint.sh"]
