#!/usr/bin/with-contenv bashio
# vim: ft=bash
# shellcheck shell=bash

STAGING=false
ALGO=$(bashio::config 'lets_encrypt.algo')
SYS_CERTFILE=$(bashio::config 'lets_encrypt.certfile')
RENEW_DAYS=$(bashio::config 'lets_encrypt.renew_days')
DOMAINS_TXT="${WORK_DIR}/domains.txt"
EMAIL=$(bashio::config 'email')
WEBROOT="/data/acme-webroot"
FORCE=""
# if RENEW_DAYS is greater than 32, force renewal. Because in dehydrated RENEW_DAYS=32
if [ "${RENEW_DAYS}" -gt 32 ]; then
  FORCE="--force "
fi

# shellcheck disable=SC2120
parse_domains_txt() {
  local inputs=("${DOMAINS_TXT}")
  cat "${inputs[@]}" |
      tr -d '\r' |
      awk '{print tolower($0)}' |
      sed -r "${@}" -e 's/^[[:space:]]*//g' -e 's/[[:space:]]*$//g' -e 's/[[:space:]]+/ /g' -e 's/([^ ])>/\1 >/g' -e 's/> />/g' |
      (grep -vE '^(#|$)' || true)
}

# Function that performs a renew
function renew_certs() {
  local CERT_DIR="${1}" WORK_DIR="${2}"
  # shellcheck disable=SC2119
  for DOMAIN in $(parse_domains_txt); do
    if [ ! -d "${CERT_DIR}/live" ] && ( ! cert_is_valid "${DOMAIN}" ); then

      echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Create dehydrated config..."
      cp /root/dehydrated.config "${WORK_DIR}/config"

      sed -i "s|^CONTACT_EMAIL=.*|CONTACT_EMAIL=\"$EMAIL\"|" "${WORK_DIR}/config"
      if [ "$STAGING" = true ]; then
          sed -i 's#https://acme-v02.api.letsencrypt.org/directory#https://acme-staging-v02.api.letsencrypt.org/directory#g' "${WORK_DIR}/config"
      fi

      mkdir -p "$WEBROOT/.well-known/acme-challenge"

      echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Register in Let's Encrypt"
      dehydrated --register --accept-terms --config "${WORK_DIR}/config"
      # shellcheck disable=SC1091
      # Do the certificate renewals
      echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Renew certificate for ${DOMAIN}"
      lets_encrypt_renew "$CERT_DIR" "$WORK_DIR"
    fi
  done

}

lets_encrypt_renew() {
  local CERT_DIR="${1}" WORK_DIR="${2}"

  echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Start dehydrated"
  dehydrated --cron --algo "${ALGO}" "${FORCE}"--hook /root/hooks.sh --challenge http-01 --domains-txt "${DOMAINS_TXT}" --out "${CERT_DIR}" --config "${WORK_DIR}/config"
}

function cert_is_valid() {
  local DOMAIN="${1}"
  echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Check domain ${DOMAIN}..."

  SYS_CERTFILE=$(bashio::config 'lets_encrypt.certfile')

  if [ ! -d "/ssl" ] || [ -z "$( ls -A "/ssl" )" ]; then
    echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Cert is not exist"
    #return false
    return 1
  fi

  cert="/ssl/${SYS_CERTFILE}"
  if [ -e "${cert}" ] && (openssl x509 -checkend $((RENEW_DAYS * 86400)) -noout -in "${cert}" 2>&1 | grep -q "will not expire"); then
    valid="$(openssl x509 -enddate -noout -in "${cert}" | cut -d= -f2- )"
    echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Certificate for ${DOMAIN} valid longer than ${RENEW_DAYS} days. "
    echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Valid till ${valid}. Skipping renew!"
    echo ""
    #return true
    return 0
  fi
  echo " Ⓐ [$(date +'%d-%m-%Y %H:%M:%S')] Cert is not valid"
  #return false
  return 1
}

