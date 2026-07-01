#!/bin/bash

# ========================================================================
# ================= SETUP SCRIPT BASH CONFIGS ============================
# ========================================================================

# Common options
set -e
# Uncomment for debugging - shows each command as it's executed
# set -x 
# Uncomment for debugging - shows each command as it's executed
# set -x 
set -o pipefail
shopt -s compat31

# Find our current directory
CURDIR="${BASH_SOURCE[0]}";RL="readlink";([[ `uname -s`=='Darwin' ]] || RL="$RL -f")
while([ -h "${CURDIR}" ]) do CURDIR=`$RL "${CURDIR}"`; done
N="/dev/null";pushd .>$N;cd `dirname ${CURDIR}`>$N;CURDIR=`pwd`;popd>$N


# ========================================================================
# ========================= SETUP OF PORTS OFFSETS  ======================
# ========================================================================

# get the number parameter (ex: ./run-container.sh 1), uses like ID of container.
# if no parameter is passed, use 1 as default
NODE_ID=${1:-1}

# Check if the parameter is a number, if not, show an error and exit
if ! [[ "$NODE_ID" =~ ^[0-9]+$ ]]; then
    echo "---------------------------------------------------------"
    echo "| ERRO FATAL: O parametro NODE_ID precisa ser um numero!|"
    echo "| Voce digitou: '$NODE_ID'                                     |"
    echo "| Exemplo de uso correto: ./run-container.sh 2          |"
    echo "---------------------------------------------------------"
    exit 1
fi

# create offsets for the ports based on the node ID, so that we can run multiple containers on the same host without port conflicts 
# (Ex: Node 1 = Zato in 11221 | Node 2 = Zato in 11222)
HOST_ZATO_PORT=$((11220 + NODE_ID))
HOST_MQTT_PORT=$((1880 + NODE_ID))
HOST_MQTT_WS_PORT=$((9000 + NODE_ID))
HOST_ADMIN_PORT=$((8180 + NODE_ID))
HOST_ADMIN_PORT_SSL=$((8181 + NODE_ID))
HOST_SSH_PORT=$((22020 + NODE_ID))

# Name the container
container_name="zato-node-$NODE_ID"

# ========================================================================
# ======== ENVIRONMENT VARIABLES AND CONFIGS INTERNAL OF ZATO ============
# ========================================================================

# What environment this is
export env_name=myproject

# What password to use when logging in to the dashboard
export zato_password=123456

# How much of the logging details to show, e.g. "-v" or "-vvvvv"
export zato_build_verbosity=${Zato_Build_Verbosity:-""}

# Absolute path to where to install code in the container
export target=/opt/hot-deploy

# IMPORTANT -> THIS INDICATES THE ADDRESS OF THE DOCKER IMAGE TO USE FOR THE CONTAINER.
# name of the docker image to use for the container
# export package_address=rhianpablo11/zato-base-congelada:v1
export package_address=rhianpablo11/zato-teste-att-se-ta-att
# export package_address=rhianpablo11/zato-ubuntu-limpo:v2

# Absolute path to our source code on host
# ATENÇÃO: Esse script assume que ele está dentro de uma pasta 'bin' ou similar
# e que seus arquivos de config estão duas pastas acima.
export host_root_dir=`readlink -f $CURDIR/../../`

# Directory on host pointing to the git clone with our project
export zato_project_root=$host_root_dir

# Our enmasse file to use
export enmasse_file=enmasse.yaml
export enmasse_file_full_path=$host_root_dir/config/enmasse/$enmasse_file

# Directory for auto-generated environment variables
mkdir -p $host_root_dir/config/auto-generated

# Populate environment variables for the server
echo '[env]'                               > $host_root_dir/config/auto-generated/env.ini
echo My_API_Password_1=$My_API_Password_1 >> $host_root_dir/config/auto-generated/env.ini
echo My_API_Password_2=$My_API_Password_2 >> $host_root_dir/config/auto-generated/env.ini
echo Zato_Project_Root=$target/$env_name  >> $host_root_dir/config/auto-generated/env.ini

# ========================================================================
# ============= ENVIRONMENT VARIABLES AND CONFIGS OF PROJECT =============
# ========================================================================

#variable to enable or disable the saving of data in the database
#precisa no env passar como q eh Zato_nome do env
export SAVE_DATA_ENABLED=True

# set of time intervals for collecting and publishing data for new devices that are not yet configured
export COLLECTION_TIME=2
export PUBLISH_TIME=6

# set the time window size for data aggregation, in minutes.
export AGGREGATION_WINDOW_MINUTES=10

# indicates the retention time for data that is in the database
# the time must be greater than the data aggregation time
# data that exceeds this retention time is deleted
export DATA_RETENTION_SECONDS=1200

export GATEWAY_REAL_IP=10.0.0.14

# Directory on host with data archives to be sent to the container
export host_data_dir_archives_to_send='../../impl/src/archives/'
export container_data_dir=/home/ubuntu/mapping_archives/devices_config/



# Config about MQTT -> if not passed, connections will be allowed without authentication (allow_anonymous true)
export Zato_MQTT_USER=meu_usuario_iot
export Zato_MQTT_PASS=minha_senha_super_segura

# ========================================================================
# ========= END ENVIRONMENT VARIABLES AND CONFIGS OF PROJECT =============
# ========================================================================

# ========================================================================
# ============================ (OPTIMIZATION) ============================
# ========================================================================
export Zato_Workers=1                    # se nao passar nada ele deixa para o proprio Zato verificar a quantidade de Workers q irá subir
export Zato_Start_Web_Admin=False        # aciona o dashboard web
export Zato_Start_Load_Balancer=False    # aciona o load balancer dele -> ALTERA AS PORTAS: sem ele (17010) e com ele (11223)
export Zato_Start_File_Listener=False    # verifica as pastas de arquivos para verificar sem tem arquivos novos
export Zato_Start_Queue_Bridge=False     # fica vigiando conexões com IBM MQ, AMQP (RabbitMQ) e JMS


# ========================================================================
# ========================= STARTING THE CONTAINER =======================
# ========================================================================

# Log what we're about to do
echo Starting container $container_name

# removing old container if it exists, ignoring errors if it doesn't
docker rm --force $container_name || true &&

docker run -d \
    --name $container_name \
    --restart unless-stopped \
    -p $HOST_SSH_PORT:22 \
    -p $HOST_ADMIN_PORT:8183 \
    -p $HOST_ADMIN_PORT_SSL:8184 \
    -p $HOST_ZATO_PORT:11223 \
    -p 11225:11225 \
    -p 3000:3000 \
    -p 15672:15672 \
    -p $HOST_MQTT_PORT:1883 \
    -p $HOST_MQTT_WS_PORT:9001 \
    -e Zato_Dashboard_Password=$zato_password \
    -e ZATO_SSH_PASSWORD=$zato_password \
    -e Zato_IDE_Password=$zato_password \
    -e Zato_Log_Env_Details=true \
    -e Zato_Build_Verbosity="$zato_build_verbosity" \
    -e Zato_SAVE_DATA_ENABLED=$SAVE_DATA_ENABLED \
    -e Zato_TANGLE_API_IP="$TANGLE_API_IP" \
    -e Zato_TANGLE_API_PORT="3001" \
    -e Zato_ZMQ_IP="$ZMQ_IP" \
    -e Zato_ZMQ_PORT="5556" \
    -e Zato_GATEWAY_REAL_IP="$GATEWAY_REAL_IP" \
    -e Zato_COLLECTION_TIME=$COLLECTION_TIME                       \
    -e Zato_PUBLISH_TIME=$PUBLISH_TIME                             \
    -e Zato_AGGREGATION_WINDOW_MINUTES=$AGGREGATION_WINDOW_MINUTES \
    -e Zato_SAVE_DATA_ENABLED=$SAVE_DATA_ENABLED                   \
    -e Zato_DATA_RETENTION_SECONDS=$DATA_RETENTION_SECONDS         \
    -e Zato_Workers=$Zato_Workers \
    -e Zato_Start_Web_Admin=$Zato_Start_Web_Admin \
    -e Zato_Start_Load_Balancer=$Zato_Start_Load_Balancer \
    -e Zato_Start_File_Listener=$Zato_Start_File_Listener \
    -e Zato_Start_Queue_Bridge=$Zato_Start_Queue_Bridge \
    $package_address


echo "Criando snapshot dos arquivos locais para dentro do container isolado..."

# ====================================================================
# =============== COPYING FILES TO INSIDE CONTAINER ==================
# ====================================================================

# grantse that the base folders exist inside the newly created container
docker exec $container_name mkdir -p $target/$env_name $target/enmasse $target/python-reqs $container_data_dir

# inject the source code and the .yaml files into the container
docker cp $zato_project_root/. $container_name:$target/$env_name/
docker cp $enmasse_file_full_path $container_name:$target/enmasse/enmasse.yaml
docker cp $host_root_dir/config/auto-generated/env.ini $container_name:$target/enmasse/env.ini
docker cp $host_root_dir/config/python-reqs/requirements.txt $container_name:$target/python-reqs/requirements.txt
docker cp $host_data_dir_archives_to_send/. $container_name:$container_data_dir/

echo "Container $container_name configurado com sucesso e 100% isolado!"


# ========================================================================
# ========================= SHOWING CONTAINER INFO =======================
# ========================================================================

echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Container Info" "Value"
echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Node ID" "$NODE_ID"
printf "| %-32s | %-31s |\n" "Container name" "$container_name"
echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Port Description" "External Host Port"
echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Zato REST API" "$HOST_ZATO_PORT"
printf "| %-32s | %-31s |\n" "MQTT TCP" "$HOST_MQTT_PORT"
printf "| %-32s | %-31s |\n" "MQTT WebSocket" "$HOST_MQTT_WS_PORT"
printf "| %-32s | %-31s |\n" "Dashboard Admin" "$HOST_ADMIN_PORT"
printf "| %-32s | %-31s |\n" "Dashboard Admin (SSL)" "$HOST_ADMIN_PORT_SSL"
printf "| %-32s | %-31s |\n" "SSH" "$HOST_SSH_PORT"
echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Variable" "Value"
echo "----------------------------------------------------------------------"
printf "| %-32s | %-31s |\n" "Zato_Dashboard_Password" "$zato_password"
printf "| %-32s | %-31s |\n" "ZATO_SSH_PASSWORD" "$zato_password"
printf "| %-32s | %-31s |\n" "Zato_Save_Data" "$SAVE_DATA_ENABLED"
printf "| %-32s | %-31s |\n" "Zato_TANGLE_API_IP" "$TANGLE_API_IP"
printf "| %-32s | %-31s |\n" "Zato_TANGLE_API_PORT" "3001"
printf "| %-32s | %-31s |\n" "Zato_ZMQ_IP" "$ZMQ_IP"
printf "| %-32s | %-31s |\n" "Zato_ZMQ_PORT" "5556"
printf "| %-32s | %-31s |\n" "Zato_GATEWAY_REAL_IP" "$GATEWAY_REAL_IP"
printf "| %-32s | %-31s |\n" "Zato_COLLECTION_TIME" "$COLLECTION_TIME"
printf "| %-32s | %-31s |\n" "Zato_PUBLISH_TIME" "$PUBLISH_TIME"
printf "| %-32s | %-31s |\n" "Zato_AGGREGATION_WINDOW_MINUTES" "$AGGREGATION_WINDOW_MINUTES"
printf "| %-32s | %-31s |\n" "Zato_DATA_RETENTION_SECONDS" "$DATA_RETENTION_SECONDS"
echo "----------------------------------------------------------------------"

sleep 3
# Exibe os logs do container em tempo real para você acompanhar a inicialização
docker logs -f $container_name