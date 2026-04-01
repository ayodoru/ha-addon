ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
ARG DEHYDRATED_VERSION
RUN \
  apk add --no-cache \
    openssh-client bash curl openssl coreutils python3 py3-pip autossh \
  && curl -s -o /usr/bin/dehydrated \
    "https://raw.githubusercontent.com/dehydrated-io/dehydrated/${DEHYDRATED_VERSION}/dehydrated" \
  && chmod a+x /usr/bin/dehydrated

RUN pip3 install flask cryptography waitress requests --break-system-packages

# Copy data for add-on
COPY rootfs /

RUN chmod +x /root/renew_certs.sh
RUN chmod +x /root/hooks.sh
RUN chmod +x /etc/periodic/daily/check_certificate_renewal
