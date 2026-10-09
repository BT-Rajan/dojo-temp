#!/bin/sh
# Creates .env.staging for the review server with random secrets. Run it from the repository folder.
#   sh backend/scripts/make_review_env.sh review.example.com          Docker, domain with HTTPS through CloudPanel
#   sh backend/scripts/make_review_env.sh 169.58.13.213               Docker, server IP over HTTP (quick look only)
#   sh backend/scripts/make_review_env.sh review.example.com native   no Docker: CloudPanel Python site + its MySQL
# It asks for the shared password the reviewers will use (and, for "native", the CloudPanel database details).
set -e
ADDRESS="$1"; MODE="$2"
if [ -z "$ADDRESS" ]; then echo "Give the domain or IP address, e.g.: sh $0 review.example.com"; exit 1; fi
if [ -f .env.staging ]; then echo ".env.staging already exists; delete it first if you really want new secrets."; exit 1; fi
case "$ADDRESS" in
  *[a-zA-Z]*) HTTPS=true; ORIGIN="https://$ADDRESS"; BIND=127.0.0.1:8090 ;;
  *) HTTPS=false; ORIGIN="http://$ADDRESS:8090"; BIND=0.0.0.0:8090 ;;
esac
ask() { printf "%s" "$1"; stty -echo 2>/dev/null || true; read -r REPLY; stty echo 2>/dev/null || true; echo; }
ask "Password for the test accounts on this server (min 12 characters, no ' quote): "
REVIEW="$REPLY"
if [ ${#REVIEW} -lt 12 ]; then echo "Too short."; exit 1; fi
case "$REVIEW" in *"'"*) echo "Please choose a password without the ' character."; exit 1 ;; esac
rand() { openssl rand -base64 "$1" | tr -d '\n/+=' ; }
umask 077
{
  echo "DJANGO_ALLOWED_HOSTS=$ADDRESS"
  echo "CSRF_TRUSTED_ORIGINS=$ORIGIN"
  echo "STAGING_HTTPS=$HTTPS"
  echo "DJANGO_SECRET_KEY=$(rand 64)"
  echo "BLIND_INDEX_KEY=$(rand 48)"
  echo "FIELD_ENCRYPTION_KEYS=$(openssl rand -base64 32 | tr '+/' '-_')"
  echo "REVIEW_PASSWORD='$REVIEW'"
} > .env.staging
if [ "$MODE" = "native" ]; then
  printf "CloudPanel database name: "; read -r DBNAME
  printf "CloudPanel database user: "; read -r DBUSER
  ask "CloudPanel database user password: "; DBPASS="$REPLY"
  URL=$(DBUSER="$DBUSER" DBPASS="$DBPASS" DBNAME="$DBNAME" python3 -c "import os, urllib.parse as u; q=lambda k: u.quote(os.environ[k], safe=''); print(f'mysql://{q(\"DBUSER\")}:{q(\"DBPASS\")}@127.0.0.1:3306/{q(\"DBNAME\")}')")
  {
    echo "DATABASE_URL='$URL'"
    echo "REDIS_URL="
  } >> .env.staging
else
  {
    echo "ELITE_BIND=$BIND"
    echo "MYSQL_ROOT_PASSWORD=$(rand 32)"
    echo "MYSQL_PASSWORD=$(rand 32)"
  } >> .env.staging
fi
echo "Written .env.staging (readable only by you). Address: $ORIGIN"
