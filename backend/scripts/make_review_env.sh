#!/bin/sh
# Creates .env.staging for the review server with random secrets.
#   sh backend/scripts/make_review_env.sh review.example.com      (a domain with HTTPS through CloudPanel)
#   sh backend/scripts/make_review_env.sh 169.58.13.213           (the server IP, plain HTTP, quick look only)
# It asks for the shared password the reviewers will use. Run it from the repository folder.
set -e
ADDRESS="$1"
if [ -z "$ADDRESS" ]; then echo "Give the domain or IP address, e.g.: sh $0 review.example.com"; exit 1; fi
if [ -f .env.staging ]; then echo ".env.staging already exists; delete it first if you really want new secrets."; exit 1; fi
case "$ADDRESS" in
  *[a-zA-Z]*) HTTPS=true; ORIGIN="https://$ADDRESS"; BIND=127.0.0.1:8090 ;;
  *) HTTPS=false; ORIGIN="http://$ADDRESS:8090"; BIND=0.0.0.0:8090 ;;
esac
printf "Password for the test accounts on this server (min 12 characters): "
stty -echo 2>/dev/null || true; read -r REVIEW; stty echo 2>/dev/null || true; echo
if [ ${#REVIEW} -lt 12 ]; then echo "Too short."; exit 1; fi
rand() { openssl rand -base64 "$1" | tr -d '\n/+=' ; }
umask 077
cat > .env.staging <<ENV
DJANGO_ALLOWED_HOSTS=$ADDRESS
CSRF_TRUSTED_ORIGINS=$ORIGIN
STAGING_HTTPS=$HTTPS
ELITE_BIND=$BIND
DJANGO_SECRET_KEY=$(rand 64)
MYSQL_ROOT_PASSWORD=$(rand 32)
MYSQL_PASSWORD=$(rand 32)
BLIND_INDEX_KEY=$(rand 48)
FIELD_ENCRYPTION_KEYS=$(openssl rand -base64 32 | tr '+/' '-_')
REVIEW_PASSWORD=$REVIEW
ENV
echo "Written .env.staging (readable by root only). Address: $ORIGIN"
