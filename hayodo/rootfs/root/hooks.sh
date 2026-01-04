#!/usr/bin/with-contenv bashio
# shellcheck shell=bash

API_URL="https://api.ayodo.ru/v1"

SYS_TOKEN=$(bashio::config 'token')
SYS_CERTFILE=$(bashio::config 'lets_encrypt.certfile')
SYS_KEYFILE=$(bashio::config 'lets_encrypt.keyfile')

deploy_challenge() {
    local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

	  echo " Ⓐ $(date +'%d-%m-%Y %H:%M:%S') Prepare challenge for $DOMAIN"

    # This hook is called once for every domain that needs to be
    # validated, including any alternative names you may have listed.
    #
    # Parameters:
    # - DOMAIN
    #   The domain name (CN or subject alternative name) being
    #   validated.
    # - TOKEN_FILENAME
    #   The name of the file containing the token to be served for HTTP
    #   validation. Should be served by your web server as
    #   /.well-known/acme-challenge/${TOKEN_FILENAME}.
    # - TOKEN_VALUE
    #   The token value that needs to be served for validation. For DNS
    #   validation, this is what you want to put in the _acme-challenge
    #   TXT record. For HTTP validation it is the value that is expected
    #   be found in the $TOKEN_FILENAME file.

    curl -X POST -L "$API_URL/connect/acme-challenge" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json" \
    -d "{\"token\":\"${SYS_TOKEN}\", \"domain\":\"${DOMAIN}\",
          \"challenge_token\":\"${TOKEN_FILENAME}\",
          \"challenge_value\":\"${TOKEN_VALUE}\",
          \"action\":\"add\"
    }"
}

clean_challenge() {
  local DOMAIN="${1}" TOKEN_FILENAME="${2}" TOKEN_VALUE="${3}"

  # This hook is called after attempting to validate each domain,
  # whether or not validation was successful. Here you can delete
  # files or DNS records that are no longer needed.
  #
  # The parameters are the same as for deploy_challenge.

  echo " Ⓐ $(date +'%d-%m-%Y %H:%M:%S') Rollback challenge for $DOMAIN"
  curl -X POST -L "$API_URL/connect/acme-challenge" \
      -H "Content-Type: application/json" \
      -H "Accept: application/json" \
      -d "{\"token\":\"${SYS_TOKEN}\", \"domain\":\"${DOMAIN}\",
            \"challenge_token\":\"${TOKEN_FILENAME}\",
            \"challenge_value\":\"${TOKEN_VALUE}\",
            \"action\":\"clean\"
      }"
}

deploy_cert() {
    local DOMAIN="${1}" KEYFILE="${2}" CERTFILE="${3}" FULLCHAINFILE="${4}" CHAINFILE="${5}" TIMESTAMP="${6}"

    # This hook is called once for each certificate that has been
    # produced. Here you might, for instance, copy your new certificates
    # to service-specific locations and reload the service.
    #
    # Parameters:
    # - DOMAIN
    #   The primary domain name, i.e. the certificate common
    #   name (CN).
    # - KEYFILE
    #   The path of the file containing the private key.
    # - CERTFILE
    #   The path of the file containing the signed certificate.
    # - FULLCHAINFILE
    #   The path of the file containing the full certificate chain.
    # - CHAINFILE
    #   The path of the file containing the intermediate certificate(s).
    # - TIMESTAMP
    #   Timestamp when the specified certificate was created.

    echo " Ⓐ $(date +'%d-%m-%Y %H:%M:%S') Deploying certificate for $DOMAIN"

    mkdir -p "/ssl/$DOMAIN"
    chmod 755 "/ssl"

    cp -f "$FULLCHAINFILE" "/ssl/$DOMAIN/$SYS_CERTFILE"
    cp -f "$KEYFILE" "/ssl/$DOMAIN/$SYS_KEYFILE"

    echo " Ⓐ $(date +'%d-%m-%Y %H:%M:%S') Certificate for $DOMAIN deployed!"
}

HANDLER="$1"; shift
if [[ "${HANDLER}" =~ ^(deploy_challenge|clean_challenge|deploy_cert)$ ]]; then
  "$HANDLER" "$@"
fi
